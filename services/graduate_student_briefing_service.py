from __future__ import annotations

import html
import json
import logging
import re

import requests

from core.config_loader import get_settings_section
from services.llm_backend import create_llm_backend


logger = logging.getLogger(__name__)

LLM_FILTER_CONFIG = get_settings_section("llm_filter")


class GraduateStudentBriefingService:
    def __init__(self, config: dict[str, object] | None = None, request_timeout: int = 20):
        self.config = config or LLM_FILTER_CONFIG
        self.request_timeout = request_timeout
        self.backend = create_llm_backend(self.config, purpose="review")

    def enrich_papers(self, papers: list[dict[str, object]]) -> list[dict[str, object]]:
        return [self.enrich_paper(dict(paper)) for paper in papers]

    def enrich_paper(self, paper: dict[str, object]) -> dict[str, object]:
        abs_text = ""
        html_text = ""
        abs_url, html_url = self._resolve_arxiv_urls(str(paper.get("Link", "") or ""))

        if abs_url:
            abs_text = self._fetch_text(abs_url)
        if html_url:
            html_text = self._fetch_text(html_url)

        abstract = str(paper.get("AbstractCN") or paper.get("Abstract") or "暂无摘要")
        contribution_points = self._extract_key_points(
            self._extract_section(html_text, ["introduction", "overview", "method"])
            or abstract,
            fallback_prefix="核心贡献",
        )
        conclusion_points = self._extract_key_points(
            self._extract_section(html_text, ["conclusion", "discussion"])
            or abstract,
            fallback_prefix="主要结论",
        )
        experiment_points = self._extract_key_points(
            self._extract_section(html_text, ["experiment", "evaluation", "result"])
            or abstract,
            fallback_prefix="实验结果",
        )

        institutions = self._extract_institutions(abs_text) or str(
            paper.get("Affiliation") or "见原文"
        )

        paper["BriefingInstitutions"] = institutions
        paper["BriefingContributionPoints"] = contribution_points
        paper["BriefingConclusionPoints"] = conclusion_points
        paper["BriefingExperimentPoints"] = experiment_points
        paper["BriefingImportance"] = str(
            paper.get("PotentialHelp") or paper.get("RelevanceReason") or "值得进一步阅读"
        )

        if str(self.config.get("backend", "")) == "openclaw":
            self._refine_with_review_agent(paper, html_text or abstract)
        return paper

    def _resolve_arxiv_urls(self, url: str) -> tuple[str, str]:
        if not url or "arxiv.org" not in url:
            return "", ""
        normalized = url.strip()
        if "/pdf/" in normalized:
            paper_id = normalized.split("/pdf/")[-1].replace(".pdf", "")
            return (f"https://arxiv.org/abs/{paper_id}", f"https://arxiv.org/html/{paper_id}")
        if "/abs/" in normalized:
            paper_id = normalized.split("/abs/")[-1]
            return normalized, f"https://arxiv.org/html/{paper_id}"
        if "/html/" in normalized:
            paper_id = normalized.split("/html/")[-1]
            return f"https://arxiv.org/abs/{paper_id}", normalized
        return "", ""

    def _fetch_text(self, url: str) -> str:
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "daliy_paper_openclaw/1.0"},
                timeout=self.request_timeout,
            )
            response.raise_for_status()
            return self._strip_html(response.text)
        except Exception as exc:
            logger.debug(f"获取页面失败 {url}: {exc}")
            return ""

    def _strip_html(self, content: str) -> str:
        cleaned = re.sub(r"<script[\s\S]*?</script>", " ", content, flags=re.I)
        cleaned = re.sub(r"<style[\s\S]*?</style>", " ", cleaned, flags=re.I)
        cleaned = re.sub(r"</(p|div|section|h1|h2|h3|h4|li|br|tr)>", "\n", cleaned)
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = html.unescape(cleaned)
        cleaned = re.sub(r"\r", "", cleaned)
        cleaned = re.sub(r"\n{2,}", "\n", cleaned)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        return cleaned.strip()

    def _extract_section(self, text: str, keywords: list[str]) -> str:
        if not text:
            return ""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            lower = line.lower()
            if any(keyword in lower for keyword in keywords):
                section_lines = [line]
                for next_line in lines[index + 1 : index + 12]:
                    if re.fullmatch(r"\d+(\.\d+)*\s+[A-Z].*", next_line):
                        break
                    if len(next_line.split()) <= 2:
                        continue
                    section_lines.append(next_line)
                return " ".join(section_lines)
        return ""

    def _extract_key_points(self, text: str, fallback_prefix: str) -> list[str]:
        sentences = self._split_sentences(text)
        points: list[str] = []
        blocked_terms = ["license", "arxiv:", "footnotemark", "creativecommons"]
        for sentence in sentences:
            cleaned = sentence.strip(" -•")
            if len(cleaned) < 20:
                continue
            lowered = cleaned.lower()
            if any(term in lowered for term in blocked_terms):
                continue
            points.append(cleaned)
            if len(points) == 3:
                break
        if points:
            return points
        return [f"{fallback_prefix}：暂无更多细节，建议查看原文。"]

    def _split_sentences(self, text: str) -> list[str]:
        if not text:
            return []
        parts = re.split(r"(?<=[。！？.!?])\s+|\n+", text)
        return [part.strip() for part in parts if part.strip()]

    def _extract_institutions(self, text: str) -> str:
        if not text:
            return ""
        matches = re.findall(
            r"([A-Z][A-Za-z&,.\- ]{3,}(?:University|Institute|Laboratory|Lab|College|School|Center|Centre))",
            text,
        )
        unique: list[str] = []
        for item in matches:
            cleaned = item.strip(" ,.;")
            lowered = cleaned.lower()
            if "arxivlab" in lowered or "about arxivlab" in lowered:
                continue
            if cleaned and cleaned not in unique:
                unique.append(cleaned)
            if len(unique) == 3:
                break
        return "; ".join(unique)

    def _refine_with_review_agent(self, paper: dict[str, object], source_text: str) -> None:
        if not source_text.strip():
            return
        prompt = f"""请基于以下论文内容生成精读简报信息。只输出 JSON：
{{
  "institutions": ["机构1", "机构2"],
  "contribution_points": ["贡献1", "贡献2"],
  "conclusion_points": ["结论1", "结论2"],
  "experiment_points": ["实验1", "实验2"],
  "importance": "一句话说明为什么重要"
}}

论文标题：{paper.get("Title") or paper.get("TitleCN")}
论文摘要：{paper.get("Abstract") or paper.get("AbstractCN")}

论文内容：
{source_text[:12000]}
"""
        try:
            raw = self.backend.generate(
                model=str(self.config.get("model", "")),
                messages=[
                    {"role": "system", "content": "你是 Graduate Student 论文精读助手。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=2000,
            )
            parsed = self._parse_review_json(raw)
            institutions = self._ensure_str_list(parsed.get("institutions"))
            contribution_points = self._ensure_str_list(parsed.get("contribution_points"))
            conclusion_points = self._ensure_str_list(parsed.get("conclusion_points"))
            experiment_points = self._ensure_str_list(parsed.get("experiment_points"))
            importance = str(parsed.get("importance", "")).strip()
            if institutions:
                paper["BriefingInstitutions"] = "; ".join(institutions)
            if contribution_points:
                paper["BriefingContributionPoints"] = contribution_points
            if conclusion_points:
                paper["BriefingConclusionPoints"] = conclusion_points
            if experiment_points:
                paper["BriefingExperimentPoints"] = experiment_points
            if importance:
                paper["BriefingImportance"] = importance
        except Exception as exc:
            logger.debug(f"精读 agent 增强失败: {exc}")

    def _parse_review_json(self, text: str) -> dict[str, object]:
        content = text.strip()
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            content = content[start:end].strip()
        data = json.loads(content)
        return {
            "institutions": self._ensure_str_list(data.get("institutions")),
            "contribution_points": self._ensure_str_list(data.get("contribution_points")),
            "conclusion_points": self._ensure_str_list(data.get("conclusion_points")),
            "experiment_points": self._ensure_str_list(data.get("experiment_points")),
            "importance": str(data.get("importance", "")).strip(),
        }

    def _ensure_str_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]
