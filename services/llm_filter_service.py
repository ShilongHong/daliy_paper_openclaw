"""
LLM论文筛选服务
"""

import json
import logging
from typing import List, Dict, Any, Optional, cast
from concurrent.futures import ThreadPoolExecutor, as_completed

# 从父目录导入配置
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config_loader import get_settings_section, get_string_setting
from services.llm_backend import create_llm_backend

logger = logging.getLogger(__name__)

LLM_FILTER_CONFIG = cast(Dict[str, Any], get_settings_section("llm_filter"))
DEFAULT_RESEARCH_DESCRIPTION = get_string_setting(
    "research_description", "请在这里填写你的研究方向描述"
)


def get_research_description() -> str:
    """获取研究方向描述（优先使用运行时配置）"""
    try:
        from services.storage_service import get_all_configs_from_db

        configs = get_all_configs_from_db()
        if configs and "research_description" in configs:
            return str(configs["research_description"])
    except Exception as e:
        logger.warning(f"从数据库获取研究方向失败: {e}")
    return DEFAULT_RESEARCH_DESCRIPTION


def get_scoring_anchors() -> str:
    try:
        from services.storage_service import get_all_configs_from_db

        configs = get_all_configs_from_db()
        llm_filter = configs.get("llm_filter", {}) if configs else {}
        if isinstance(llm_filter, dict):
            scoring_anchors = llm_filter.get("scoring_anchors", "")
            if isinstance(scoring_anchors, str) and scoring_anchors.strip():
                return scoring_anchors.strip()
    except Exception as e:
        logger.warning(f"从数据库获取评分锚点失败: {e}")

    scoring_anchors = LLM_FILTER_CONFIG.get("scoring_anchors", "")
    if isinstance(scoring_anchors, str) and scoring_anchors.strip():
        return scoring_anchors.strip()
    return ""


class LLMFilterService:
    """LLM论文筛选服务类"""

    # Few-shot 示例
    FEW_SHOT_EXAMPLES = """
## 评分示例

### 示例1（高分论文）
标题：ChartLlama: A Multimodal LLM for Chart Understanding and Generation
摘要：We present ChartLlama, a multi-modal large language model for chart understanding...

评估结果：
```json
{
  "dimensions": {
    "problem_relevance": {"score": 24, "note": "直接解决图表理解核心问题"},
    "method_transferability": {"score": 23, "note": "多模态LLM方法可直接应用"},
    "data_resource": {"score": 20, "note": "提供图表理解数据集"},
    "technical_depth": {"score": 22, "note": "技术栈高度匹配"}
  },
  "total_score": 89,
  "reason": "直接解决图表理解核心问题，方法和数据均可借鉴",
  "action_items": ["复现其图表解析pipeline", "使用其数据集做基准测试"]
}
```

### 示例2（中等分数论文）
标题：DocParser: End-to-end Document Parsing with Transformers
摘要：We propose DocParser for structured document understanding using vision transformers...

评估结果：
```json
{
  "dimensions": {
    "problem_relevance": {"score": 18, "note": "文档解析相关，但非图表专用"},
    "method_transferability": {"score": 16, "note": "Transformer架构可参考，需适配"},
    "data_resource": {"score": 12, "note": "通用文档数据，需筛选科学文献"},
    "technical_depth": {"score": 15, "note": "技术深度适中"}
  },
  "total_score": 61,
  "reason": "文档解析方法可参考，但需针对科学图表场景改造",
  "action_items": ["参考其layout理解模块"]
}
```

### 示例3（低分论文）
标题：A Survey of Sentiment Analysis in Social Media
摘要：This survey reviews sentiment analysis methods for Twitter and social media platforms...

评估结果：
```json
{
  "dimensions": {
    "problem_relevance": {"score": 3, "note": "情感分析与科学文献IE无关"},
    "method_transferability": {"score": 5, "note": "NLP基础方法有微弱参考性"},
    "data_resource": {"score": 2, "note": "社交媒体数据不适用"},
    "technical_depth": {"score": 4, "note": "研究深度方向不匹配"}
  },
  "total_score": 14,
  "reason": "研究方向不相关，无直接参考价值",
  "action_items": []
}
```
"""

    # 评分锚点关键词
    DEFAULT_SCORING_ANCHORS = """
## 评分参考锚点

### 高分信号（每项可得20-25分）
**问题相关关键词**：chart understanding, table extraction, figure parsing, scientific document, 
materials science, multimodal information extraction, knowledge graph construction, 
chart-to-table, formula recognition, scientific literature mining

**方法相关关键词**：vision-language model, multimodal LLM, document layout analysis, 
OCR, curve detection, data extraction, end-to-end parsing

**数据/资源关键词**：chart dataset, scientific figure benchmark, materials database, 
open-source implementation, reproducible

### 中等分数信号（每项10-19分）
- 通用多模态方法（需要适配才能用于科学图表）
- 相邻领域（如医学图像分析、通用文档理解）
- 基础技术组件（如目标检测、OCR改进）

### 低分信号（每项0-9分）
- 纯文本NLP任务（无视觉/多模态成分）
- 不相关领域（社交媒体、推荐系统、语音等）
- 过时方法（2019年前的非深度学习方法，除非是经典基准）
- 纯理论工作（无实验验证或实际应用）
"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = cast(Dict[str, Any], config or LLM_FILTER_CONFIG)
        self.research_description = get_research_description()
        logger.info(f"LLMFilterService 接收到的配置键: {list(self.config.keys())}")

        self.backend = create_llm_backend(self.config, purpose="filter")

        self.model = str(self.config.get("model", "gpt-3.5-turbo"))
        self.temperature = float(self.config.get("temperature", 0.1))
        self.max_tokens = int(self.config.get("max_tokens", 500))
        config_scoring_anchors = self.config.get("scoring_anchors", "")
        if isinstance(config_scoring_anchors, str) and config_scoring_anchors.strip():
            self.scoring_anchors = config_scoring_anchors.strip()
        else:
            self.scoring_anchors = (
                get_scoring_anchors() or self.DEFAULT_SCORING_ANCHORS.strip()
            )

        logger.info("LLMFilterService初始化完成")

    def generate_scoring_anchors(self, research_description: str) -> str:
        prompt = f"""你是一位科研论文评审专家。
请根据以下研究方向，生成一套论文相关度评分锚点。

研究方向：{research_description}

请生成以下格式的锚点（参考示例格式，但内容必须完全针对上述研究方向）：

## 评分参考锚点

### 高分信号（每项可得20-25分）
**问题相关关键词**：...（列出10-15个与该研究方向直接相关的英文关键词）

**方法相关关键词**：...（列出8-12个该研究方向常用的方法/技术关键词）

**数据/资源关键词**：...（列出5-8个该方向常见的数据集类型或资源形式）

### 中等分数信号（每项10-19分）
- ...（列出3-5条相邻领域、通用方法或需适配后才有参考价值的方向）

### 低分信号（每项0-9分）
- ...（列出3-5条明确不相关、帮助很弱或偏题的方向）

要求：
1. 只输出锚点内容，不要解释。
2. 保持 Markdown 标题和列表结构完整。
3. 内容必须贴合给定研究方向，不能复用通用示例。"""

        return self.backend.generate(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=800,
        ).strip()

    def evaluate_paper(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """评估单篇论文的相关度"""
        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                prompt = self._build_evaluation_prompt(paper)

                raw_content = self.backend.generate(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一个学术论文评估专家，需要评估论文与给定研究方向的相关度。请使用100分制评分。",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )

                result = self._parse_response(raw_content)

                # 记录成功的响应（调试用）
                if len(raw_content) > 200:
                    debug_preview = raw_content[:200] + "..."
                else:
                    debug_preview = raw_content
                logger.debug(f"LLM响应预览: {debug_preview}")

                logger.debug(
                    f"论文 '{paper['Title'][:50]}...' 评分: {result['score']}分"
                )
                return result

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"LLM评估失败（尝试 {attempt + 1}/{max_retries}），{retry_delay}秒后重试: {str(e)}"
                    )
                    import time

                    time.sleep(retry_delay)
                else:
                    logger.error(f"评估论文时出错: {str(e)}")
                    return {
                        "score": 50,
                        "stars": 50,
                        "reason": "评估失败，使用默认评分",
                        "help": "需要进一步人工评估",
                        "raw_response": "",
                    }

        return {
            "score": 50,
            "stars": 50,
            "reason": "评估失败，使用默认评分",
            "help": "需要进一步人工评估",
            "raw_response": "",
        }

    def filter_papers(
        self, papers: List[Dict[str, Any]]
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """批量筛选论文，返回 (成功评估的论文列表, 失败的论文列表)"""
        if not papers:
            return [], []

        max_workers = int(self.config.get("max_workers", 16))
        logger.info(f"开始LLM筛选，共 {len(papers)} 篇论文，使用 {max_workers} 个线程")

        min_stars = self.config.get("min_stars", 3)
        filtered_papers = []
        failed_papers = []  # 评估失败的论文
        completed_count = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_paper = {
                executor.submit(self.evaluate_paper, paper): paper for paper in papers
            }

            for future in as_completed(future_to_paper):
                paper = future_to_paper[future]
                completed_count += 1

                try:
                    evaluation = future.result()

                    paper["Stars"] = evaluation["stars"]
                    paper["RelevanceReason"] = evaluation["reason"]
                    paper["PotentialHelp"] = evaluation.get("help", "可作为研究参考")

                    # 检查是否评估失败（50分且原因包含"评估失败"）
                    if evaluation["score"] == 50 and "评估失败" in evaluation["reason"]:
                        failed_papers.append(paper)
                        logger.warning(
                            f"  [{completed_count}/{len(papers)}] ⚠️ {paper['Title'][:50]}... -> 评估失败，标记为未处理"
                        )
                    else:
                        filtered_papers.append(paper)
                        logger.info(
                            f"  [{completed_count}/{len(papers)}] ✅ {paper['Title'][:50]}... -> {evaluation['score']}分"
                        )

                except Exception as e:
                    logger.error(
                        f"  [{completed_count}/{len(papers)}] ❌ {paper['Title'][:50]}... -> 错误: {str(e)}"
                    )
                    paper["Stars"] = 50
                    paper["RelevanceReason"] = "评估失败，使用默认评分"
                    paper["PotentialHelp"] = "需要进一步人工评估"
                    failed_papers.append(paper)

        filtered_papers.sort(key=lambda x: x["Stars"], reverse=True)

        high_relevance = [p for p in filtered_papers if p["Stars"] >= min_stars]
        logger.info(
            f"筛选完成: {len(high_relevance)}/{len(papers)} 篇论文达到 {min_stars}星及以上"
        )

        return filtered_papers, failed_papers

    def _build_evaluation_prompt(self, paper: Dict[str, Any]) -> str:
        """构建评估提示词"""
        prompt = f"""你是一位专业的科研论文评审专家。请评估以下论文与给定研究方向的相关度。

# 我的研究方向
{self.research_description}

# 待评估论文
**标题**：{paper.get("Title", "N/A")}
**摘要**：{paper.get("Abstract", "N/A")}

{self.scoring_anchors}

{self.FEW_SHOT_EXAMPLES}

# 评估任务

请从以下4个维度分别评分（每项0-25分），然后计算总分：

1. **problem_relevance（问题相关性）**：论文解决的问题与我的研究问题是否相关
2. **method_transferability（方法可迁移性）**：论文方法是否可直接借鉴或改造应用到我的研究
3. **data_resource（数据/资源价值）**：论文是否提供可用的数据集、代码、基准测试
4. **technical_depth（技术深度匹配）**：技术栈和研究深度是否与我的研究匹配

请严格按以下JSON格式输出（不要有其他内容）：

**重要格式要求**：
- 所有键名必须用双引号包裹（例如："total_score"）
- 所有字符串值必须用双引号包裹（例如："reason"）
- 不要使用单引号，不要使用无引号的键名
- 不要添加注释（// 或 /* */）
- 尾部不要有多余的逗号

```json
{{
  "dimensions": {{
    "problem_relevance": {{"score": 0-25, "note": "一句话说明"}},
    "method_transferability": {{"score": 0-25, "note": "一句话说明"}},
    "data_resource": {{"score": 0-25, "note": "一句话说明"}},
    "technical_depth": {{"score": 0-25, "note": "一句话说明"}}
  }},
  "total_score": 四项之和（0-100）,
  "reason": "一句话总结相关性（20字以内）",
  "action_items": ["具体可借鉴的内容1", "具体可借鉴的内容2"]
}}
```

评分区间参考：
- 80-100分：高度相关，必读论文
- 60-79分：较相关，值得阅读
- 40-59分：弱相关，可选择性浏览
- 0-39分：不相关，可跳过

只输出JSON，不要有任何其他文字。"""

        return prompt

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """解析LLM响应"""
        try:
            response_text = response_text.strip()

            # 提取JSON部分
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()

            # 清理和标准化JSON（处理LLM返回的非标准格式）
            cleaned_json = self._clean_json_string(response_text)

            result = json.loads(cleaned_json)

            # 新格式：多维度评分
            if "dimensions" in result and "total_score" in result:
                # 验证总分计算（允许小误差）
                dim_sum = sum(d.get("score", 0) for d in result["dimensions"].values())
                total_score = result.get("total_score", dim_sum)
                if abs(dim_sum - total_score) > 2:
                    total_score = dim_sum  # 以维度之和为准

                total_score = max(0, min(100, int(total_score)))

                reason = result.get("reason", "").strip()
                if not reason:
                    reason = f"{total_score}分相关"

                # 从 action_items 提取帮助信息
                action_items = result.get("action_items", [])
                if action_items and isinstance(action_items, list):
                    help_text = "; ".join(action_items[:3])  # 最多取3个
                else:
                    help_text = "可作为研究参考"

                return {
                    "score": total_score,
                    "stars": total_score,
                    "reason": reason,
                    "help": help_text,
                    "dimensions": result["dimensions"],
                    "action_items": action_items,
                    "raw_response": response_text,
                }

            # 兼容旧格式：直接的score/stars
            elif "score" in result:
                score = int(result.get("score", 50))
                score = max(0, min(100, score))
            elif "stars" in result:
                stars = int(result.get("stars", 3))
                score = stars * 20
            else:
                score = 50

            reason = result.get("reason", "").strip()
            if not reason:
                reason = f"{score}分相关"

            help_text = result.get("help", "").strip()
            if not help_text:
                help_text = "可作为研究参考"

            return {
                "score": score,
                "stars": score,
                "reason": reason,
                "help": help_text,
                "raw_response": response_text,
            }

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}")
            # 尝试清理JSON后重新解析
            try:
                cleaned_json = self._clean_json_string(response_text)
                result = json.loads(cleaned_json)
                # 重新进入新格式解析流程
                if "dimensions" in result and "total_score" in result:
                    return self._process_new_format(result, response_text)
                else:
                    return self._process_legacy_format(result, response_text)
            except Exception as clean_error:
                logger.warning(f"清理JSON后仍然解析失败: {clean_error}")
                return self._extract_score_from_text(response_text)
        except Exception as e:
            logger.error(f"解析响应时出错: {e}")
            return {
                "score": 50,
                "stars": 50,
                "reason": "解析失败，使用默认评分",
                "help": "需要进一步人工评估",
                "raw_response": response_text,
            }

    def _clean_json_string(self, json_str: str) -> str:
        """清理和标准化JSON字符串，处理LLM返回的非标准格式"""
        import re

        # 移除注释（// 和 /* */ 风格）
        json_str = re.sub(r"//.*?$", "", json_str, flags=re.MULTILINE)
        json_str = re.sub(r"/\*.*?\*/", "", json_str, flags=re.DOTALL)

        # 移除尾随逗号（在 } 或 ] 之前）
        json_str = re.sub(r",\s*([}\]])", r"\1", json_str)

        # 处理属性名的引号问题：将单引号或无引号的属性名转为双引号
        # 使用更简单的方法：先替换单引号键，再处理无引号键

        # 步骤1: 将单引号包裹的键名转换为双引号（但避免转换字符串值中的单引号）
        # 匹配模式：{ 或 , 后面跟着单引号键名，然后是冒号
        # 使用lookbehind来确保不会匹配字符串内部的内容
        json_str = re.sub(r"([{,]\s*)\'([^\'\n]+)\'(\s*:)", r'\1"\2"\3', json_str)

        # 步骤2: 处理无引号的键名（只包含字母、数字、下划线）
        # 使用更精确的模式来避免误匹配字符串值
        def quote_unquoted_keys(match):
            # 只在键名不是字符串值的一部分时才添加引号
            return f'{match.group(1)}"{match.group(2)}"{match.group(3)}'

        # 匹配：{ 或 , + 可选空白 + 字母开头的标识符 + 可选空白 + :
        # 这个模式需要小心处理，避免误匹配字符串值
        # 使用否定lookbehind来确保前面不是 :（避免匹配字符串值）
        json_str = re.sub(
            r"(?<!:)([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)",
            quote_unquoted_keys,
            json_str,
        )

        # 步骤3: 移除所有不使用引号包裹的字符串值（简单方法：在需要的地方添加引号）
        # 这个比较复杂，暂时不做，依赖后续的正则提取

        return json_str.strip()

    def _process_new_format(self, result: Dict, raw_response: str) -> Dict[str, Any]:
        """处理新格式（多维度评分）"""
        # 验证总分计算（允许小误差）
        dim_sum = sum(d.get("score", 0) for d in result["dimensions"].values())
        total_score = result.get("total_score", dim_sum)
        if abs(dim_sum - total_score) > 2:
            total_score = dim_sum  # 以维度之和为准

        total_score = max(0, min(100, int(total_score)))

        reason = result.get("reason", "").strip()
        if not reason:
            reason = f"{total_score}分相关"

        # 从 action_items 提取帮助信息
        action_items = result.get("action_items", [])
        if action_items and isinstance(action_items, list):
            help_text = "; ".join(action_items[:3])  # 最多取3个
        else:
            help_text = "可作为研究参考"

        return {
            "score": total_score,
            "stars": total_score,
            "reason": reason,
            "help": help_text,
            "dimensions": result["dimensions"],
            "action_items": action_items,
            "raw_response": raw_response,
        }

    def _process_legacy_format(self, result: Dict, raw_response: str) -> Dict[str, Any]:
        """处理旧格式（直接的score/stars）"""
        if "score" in result:
            score = int(result.get("score", 50))
        elif "stars" in result:
            stars = int(result.get("stars", 3))
            score = stars * 20
        else:
            score = 50

        score = max(0, min(100, score))

        reason = result.get("reason", "").strip()
        if not reason:
            reason = f"{score}分相关"

        help_text = result.get("help", "").strip()
        if not help_text:
            help_text = "可作为研究参考"

        return {
            "score": score,
            "stars": score,
            "reason": reason,
            "help": help_text,
            "raw_response": raw_response,
        }

    def _extract_score_from_text(self, text: str) -> Dict[str, Any]:
        """从文本中提取分数（降级处理）"""
        import re

        # 尝试提取 total_score
        total_match = re.search(r'["\']?total_score["\']?\s*[:：]\s*(\d{1,3})', text)
        if total_match:
            score = int(total_match.group(1))
            score = max(0, min(100, score))
        else:
            # 尝试提取维度分数并求和
            dim_pattern = r'["\']?(?:problem_relevance|method_transferability|data_resource|technical_depth)["\']?\s*[:：]\s*\{[^}]*["\']?score["\']?\s*[:：]\s*(\d{1,2})'
            dim_scores = re.findall(dim_pattern, text)
            if dim_scores:
                score = sum(min(25, int(s)) for s in dim_scores)
                score = max(0, min(100, score))
            else:
                # 尝试提取普通 score
                score_match = re.search(r'["\']?score["\']?\s*[:：]\s*(\d{1,3})', text)
                if score_match:
                    score = int(score_match.group(1))
                    score = max(0, min(100, score))
                else:
                    score = 50

        reason_match = re.search(
            r'["\']?reason["\']?\s*[:：]\s*["\']([^"\']+)["\']', text
        )
        if reason_match:
            reason = reason_match.group(1).strip()
        else:
            reason = f"{score}分相关"

        return {
            "score": score,
            "stars": score,
            "reason": reason,
            "help": "解析异常，建议人工审查",
            "raw_response": text,
        }


def filter_papers_with_llm(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """使用LLM筛选论文的便捷函数"""
    service = LLMFilterService()
    return service.filter_papers(papers)[0]
