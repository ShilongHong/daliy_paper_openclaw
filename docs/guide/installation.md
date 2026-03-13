# Installation

## For Humans

Paste this into your llm agent session:

```text
Install and configure daliy_paper_openclaw by following the instructions here:
https://raw.githubusercontent.com/ShilongHong/daliy_paper_openclaw/main/docs/guide/installation.md
```

Alternative, not recommended: do it by yourself.

## For LLM Agents

Use `curl` to fetch this file:

```bash
curl -fsSL https://raw.githubusercontent.com/ShilongHong/daliy_paper_openclaw/main/docs/guide/installation.md
```

Follow these steps.

### Step 0: 询问用户配置

**在开始安装之前，按以下顺序向用户询问所有配置问题。**

---

#### Q1. 研究方向描述

> **为什么重要**：这是整个系统的核心。LLM 会根据这段描述来给每篇论文打相关度分数。描述越模糊，推荐噪音越大；描述越精确（包含核心方向、支撑技术、排除方向），筛选效果越好。

请用户提供一段自然语言描述他们的研究方向，建议包含：
- 核心研究主题（最高相关度）
- 支撑/相关技术（中等相关度）
- 明确排除的方向（减少噪音）

示例：

```text
我的研究方向是图表数据提取与多模态信息理解。
核心主题：Chart-to-Table、图表QA、视觉语言模型在图表任务上的应用。
相关技术：OCR、表格识别、文档智能。
排除方向：纯图表生成/可视化（不涉及提取）、纯NLP任务。
```

---

#### Q2. ArXiv 关键词 / 分类

> **为什么重要**：这些分类决定了从 arXiv 抓取哪些领域的论文。分类定义的是 LLM 筛选之前的原始论文池——选太少会漏掉相关论文，选太多会在不相关论文上浪费 LLM token。

常用分类参考：
- `cs.CL` — 计算语言学（NLP）
- `cs.CV` — 计算机视觉
- `cs.LG` — 机器学习
- `cs.AI` — 人工智能
- `cs.IR` — 信息检索
- `cs.RO` — 机器人学
- `cs.SE` — 软件工程
- `stat.ML` — 统计机器学习

默认值：`["cs.CL", "cs.CV", "cs.LG", "cs.AI", "cs.IR"]`

---

#### Q3. 数据库类型

> **为什么重要**：SQLite 零配置、单文件，适合个人在一台机器上使用。MySQL 只在需要远程访问、多用户共享或已有 MySQL 实例的情况下才需要。

选项：
- `sqlite` — 推荐大多数用户使用。无需额外配置，数据存在本地文件中。
- `mysql` — 适合需要远程/共享数据库访问的高级用户。

如果选 `sqlite`：询问文件路径，默认 `data/paper2data.db`

如果选 `mysql`：询问 host、port、user、password、database

---

#### Q4. LLM 后端

> **为什么重要**：系统需要 LLM 来（1）给论文打相关度分数，（2）将标题和摘要翻译成中文，（3）可选地生成更深度的论文分析。你需要选择如何调用 LLM。

选项：
- `openai_compatible` — 使用任意 OpenAI 兼容 API（SiliconFlow、DeepSeek、OpenAI 等）。配置简单，只需要一个 API key。
- `openclaw` — 通过 OpenClaw agent 路由 LLM 调用。可以为不同任务分配不同模型（例如便宜的模型翻译、更强的模型打分）。更灵活，但需要配置 OpenClaw agent。

如果选 `openai_compatible`，询问：
- `api_key` — API 密钥
- `base_url` — API 地址（默认：`https://openrouter.ai/api/v1`）
- `model` — 模型名称（默认：`google/gemini-3.1-flash-lite-preview`）

如果选 `openclaw`，安装阶段只询问最小必要配置：
- `binary_path` — openclaw 可执行文件路径（先自动探测；探测失败时再手动输入完整路径）
- `translation_agent_id` — 翻译任务的 agent（默认：`translation`）
- `filter_agent_id` — 论文打分的 agent（默认：`filter`）
- `review_agent_id` — 深度分析的 agent（默认：`graduate-student`，可留默认）
- `timeout_seconds` — LLM 响应超时时间（默认：`300`）

安装阶段**不要强制询问**每个 agent 的模型，也不要一开始就展开高级 OpenClaw 路由配置。优先先让系统跑起来，再在后续高级配置里调整。

建议：使用三个独立 agent 而不是一个共享 agent，这样可以为不同任务分配不同模型；默认建议使用带项目前缀的名称，避免和用户现有 agent 冲突。

---

#### Q5. 论文投递目标

> **为什么重要**：论文打分和翻译完成后，会被推送到一个 OpenClaw session。后台服务运行时并没有“当前对话”这个概念，所以最终必须把一个明确的 `session_key` 写进配置里。

安装阶段建议这样做：
- 先运行 `openclaw sessions --json`
- 如果能列出 session，就把**最近一个候选 session**展示给用户确认
- 询问：`是否使用这个 session 作为默认接收会话？`
- 如果用户不同意，再让用户手动输入 `session_key`

重要：不要无确认地直接假定“当前对话”就是最终投递目标。可以把候选 session 作为默认建议值，但必须让用户确认。

---

#### Q6. 研究生精读模式（Graduate Student Briefing）

> **为什么重要**：标准摘要包含标题、分数、推荐理由和摘要。研究生精读模式会额外生成更丰富的分析：机构提取、贡献点、结论点、实验要点和重要性总结。每篇论文消耗更多 LLM token，但能给出更有价值的每日推送。

选项：
- `false`（默认）— 标准摘要，token 消耗较低
- `true` — 深度精读分析，信息更丰富

---

#### Q7. 定时任务配置

> **为什么重要**：调度器控制系统何时自动从 arXiv 抓取新论文、何时将打分后的论文投递到你的 session。不配置调度的话，所有操作都需要手动通过 API 触发。

选项：
- 现在启用 — 配置自动抓取和投递时间
- 暂时跳过 — 先完成安装，之后再配置

如果启用：
- 抓取时间 — 什么时候从 arXiv 拉取新论文（默认：`02:00`，建议深夜以避免 arXiv 限流）
- 推送时间 — 什么时候投递打分后的论文（默认：`["09:00"]`，可设置多个时间如 `["09:00", "14:30"]`）

---

**Agent 注意事项：**

- 不要在未确认的情况下把最近 session 直接当成最终投递目标。
- 如果用户明确希望论文就发到当前正在使用的对话，可以把该 session 写入 `openclaw.session_key`。
- 优先使用三个独立 agent：`translation`、`filter`、`graduate-student`。
- 如果用户没有提供完整的 LLM 配置，仍然以最小可运行配置完成安装。
- 投递使用配置的 `openclaw.session_key`，运行时通过 `openclaw sessions --json` 解析实际 sessionId。

### Step 1: 安装 OpenClaw CLI

先检查是否已安装：

```bash
openclaw --version
```

如果命令存在且返回版本号，跳过安装。

安装 agent 应优先自动探测命令路径：

```bash
which openclaw
```

如果能找到，例如返回 `/home/yourname/.nvm/versions/node/vxx/bin/openclaw`，优先把这个完整路径写入 `binary_path`。

如果 `openclaw --version` 或 `which openclaw` 失败，说明常见问题是 **CLI 已安装但不在当前进程的 PATH 中**。这时不要直接假设命令名可用，应让用户提供完整路径。

如果未安装：

```bash
npm install -g openclaw
openclaw --version
```

### Step 2: Clone the repository

```bash
git clone https://github.com/ShilongHong/daliy_paper_openclaw.git
cd daliy_paper_openclaw
```

### Step 3: Create a virtual environment

本项目需要 **Python 3.11**，推荐使用 [uv](https://github.com/astral-sh/uv) 管理虚拟环境（速度更快，且可自动下载指定 Python 版本）。

#### 3a. 安装 uv（如果尚未安装）

检查是否已安装：

```bash
uv --version
```

如果命令不存在，按对应平台安装：

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

安装完成后重新确认：

```bash
uv --version
```

#### 3b. 创建 Python 3.11 虚拟环境

```bash
uv venv .venv --python 3.11
```

> uv 会自动下载 Python 3.11（如果本机尚未安装），无需手动配置。

#### 3c. 激活虚拟环境

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (CMD)
.venv\Scripts\activate.bat
```

### Step 4: Install Python dependencies

```bash
uv pip install -r requirements.txt
```

### Step 5: Write local configuration

#### 5a. Generate `config.py` from the template

```bash
cp config.demo.py config.py
```

`config.demo.py` is the canonical template committed to the repository. Copying it produces the required `config.py` compatibility shim that bridges legacy `from config import ...` imports to the new `core/config_loader.py`. Do not edit `config.py` manually — all runtime values come from `config.local.json`.

#### 5b. Create `config.local.json` based on the user's answers from Step 0.

Minimal SQLite + OpenClaw delivery config:

```json
{
  "database": {
    "engine": "sqlite",
    "sqlite_path": "data/paper2data.db"
  },
  "research_description": "<user's research direction from Q1>",
  "arxiv": {
    "keywords": ["<categories from Q2>"]
  },
  "llm_filter": {
    "enable": true,
    "backend": "<backend from Q4>",
    "api_key": "<if openai_compatible>",
    "base_url": "<if openai_compatible>",
    "model": "<if openai_compatible>",
    "openclaw": {
      "binary_path": "openclaw",
      "translation_agent_id": "translation",
      "filter_agent_id": "filter",
      "review_agent_id": "graduate-student",
      "translation_model": "",
      "filter_model": "",
      "review_model": "",
      "timeout_seconds": 300,
      "use_local": false
    }
  },
  "openclaw": {
    "session_key": "<session_key from Q5>",
    "binary_path": "openclaw",
    "timeout_seconds": 300,
    "enable_graduate_student_briefing": false
  },
  "schedule": {
    "enable_schedule": true,
    "fetch_papers": {
      "enable": true,
      "time": "02:00"
    },
    "push_papers": {
      "enable": true,
      "times": ["09:00"]
    }
  }
}
```

Adapt the template above based on the user's actual answers. Remove unused fields (e.g. if using `openai_compatible`, the `openclaw` block inside `llm_filter` can use defaults).

### Step 6: Verify OpenClaw access

```bash
openclaw sessions --json
```

Optional smoke test:

```bash
openclaw agent --agent main --json --message "Reply with exactly: ok"
```

### Step 7: Start the app

```bash
python app.py
```

If port `20001` is already in use, use other port:

```bash
python app.py --port <new_port>
```

### Step 8: Verify setup

```bash
curl http://127.0.0.1:<new_port>/api/health
curl http://127.0.0.1:<new_port>/api/config/all
```

### Step 9: Optional runtime configuration

If the user chose OpenClaw as the LLM backend, configure it after startup:

```bash
curl -X PUT http://127.0.0.1:<new_port>/api/config/llm_filter \
  -H 'Content-Type: application/json' \
  --data '{
    "config": {
      "enable": true,
      "backend": "openclaw",
      "api_key": "",
      "base_url": "https://openrouter.ai/api/v1",
      "model": "google/gemini-3.1-flash-lite-preview",
      "temperature": 0.5,
      "max_tokens": 4096,
      "min_score": 60,
      "min_stars": 60,
      "save_all_papers": true,
      "max_workers": 16,
      "openclaw": {
        "binary_path": "openclaw",
        "translation_agent_id": "translation",
        "filter_agent_id": "filter",
        "review_agent_id": "graduate-student",
        "translation_model": "",
        "filter_model": "",
        "review_model": "",
        "timeout_seconds": 300,
        "use_local": false
      }
    }
  }'
```

### Step 10: Manual verification

Run at least one of these after install:

```bash
curl -X POST http://127.0.0.1:<new_port>/api/actions/process-now
curl -X POST http://127.0.0.1:<new_port>/api/actions/deliver-now
```
