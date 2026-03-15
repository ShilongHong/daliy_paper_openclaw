# Installation

## For Humans

Paste this into your llm agent session:

```text
根据这个文档安装 daliy_paper_openclaw，并询问用户协助进行相关配置:
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

**在开始安装之前，你必须按以下顺序向用户询问所有配置问题。**

**提问策略补充（非常重要）：**

- 这是给 LLM agent 的安装说明，不是给用户看的教学文档。
- 对于常规配置，不要一上来展开长篇解释；先结合上下文给出一个**可运行的默认方案**，直接问用户 `这样可以吗？`
- 只有当用户不同意、犹豫、或明确追问时，再解释某个配置项是做什么的。
- 特别是 `database`、`openclaw.session_key`、`schedule` 这类配置，优先采用“默认方案 -> 用户确认 -> 必要时再展开”的流程。

**Step 0 执行蓝图（推荐严格遵守）：**

1. 先收集用户的 `research_description`
2. 根据这段描述自动生成 `scoring_anchors` 和推荐的 `arxiv.keywords`
3. 把“锚点 + 分类推荐”作为一版默认方案给用户确认
4. 再对数据库、LLM 后端、投递目标、精读模式、定时任务依次给出默认建议，而不是逐项空问
5. 只有用户拒绝默认方案时，才展开解释或追问细节
6. 在 Step 0 结束时，把最终确认结果汇总成一份明确的配置草案，再进入实际安装步骤

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

在用户给出研究方向描述之后，**不要立刻进入 Q2**。先基于这段描述自动生成两样内容：

1. `scoring_anchors` - 后续 LLM 评分时使用的评分锚点
2. 推荐的 arXiv 分类/关键词 - 作为 `arxiv.keywords` 的建议初稿

这里同样不要把过程问得太碎。LLM agent 应该先自己理解用户的研究方向，然后直接给出一版**生成结果 + 默认建议**，再让用户确认。

然后把这两部分结果展示给用户确认：

- 先展示生成的评分锚点
- 再展示推荐的 arXiv 分类（例如 `cs.CV`、`cs.CL`、`stat.ML`）
- 默认表达方式应当类似：`我先按你的研究方向生成了一版评分锚点，并推荐这些 arXiv 分类作为默认抓取范围。这样可以吗？`
- 只有当用户不同意时，再进入“重新生成 / 手动修改分类 / 解释为什么推荐这些分类”的分支

**只有在用户确认之后，才继续后面的问题。**

建议交互：

- `这版锚点和分类我先按默认方案这样配置，可以吗？` - 可以 / 不可以
- 如果不可以，再细分为：重新生成锚点、手动修改分类、解释推荐理由

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

如果在 Q1 之后已经自动生成了推荐分类，这里应当：

- 以用户刚刚确认过的推荐分类作为默认值
- 如果用户拒绝推荐分类，再回退到通用默认值
- 不要忽略用户刚刚确认过的结果，重新从头追问一遍

---

#### Q3. 数据库类型

> **为什么重要**：SQLite 零配置、单文件，适合个人在一台机器上使用。MySQL 只在需要远程访问、多用户共享或已有 MySQL 实例的情况下才需要。

对 LLM agent 的推荐交互方式：

- 先直接给默认建议：`我建议先用 sqlite，数据库文件放在 data/paper2data.db，这样可以零配置启动。这样可以吗？`
- 如果用户接受：直接记录 `database.engine = sqlite` 和 `database.sqlite_path = data/paper2data.db`
- 如果用户拒绝或说自己有 MySQL：再继续追问 MySQL 连接信息，并简要解释差异

选项：
- `sqlite` — 推荐大多数用户使用。无需额外配置，数据存在本地文件中。
- `mysql` — 适合需要远程/共享数据库访问的高级用户。

如果选 `sqlite`：询问文件路径，默认 `data/paper2data.db`

如果选 `mysql`：询问 host、port、user、password、database

---

#### Q4. LLM 后端

> **为什么重要**：系统需要 LLM 来（1）给论文打相关度分数，（2）将标题和摘要翻译成中文，（3）可选地生成更深度的论文分析。你需要选择如何调用 LLM。

对 LLM agent 的推荐交互方式：

- 先给默认建议：`我建议先用 openai_compatible，这样配置最少、最容易跑通。这样可以吗？`
- 如果用户接受：只追问最小必要字段 `api_key`、`base_url`、`model`
- 如果用户明确希望走 OpenClaw agent：再进入 `openclaw` 分支，补充 agent 相关配置

选项：
- `openai_compatible` — 使用任意 OpenAI 兼容 API（SiliconFlow、DeepSeek、OpenAI 等）。配置简单，只需要一个 API key。
- `openclaw` — 通过 OpenClaw agent 路由 LLM 调用。可以为不同任务分配不同模型（例如便宜的模型翻译、更强的模型打分）。更灵活，但需要配置 OpenClaw agent。

如果选 `openai_compatible`，询问：
- `api_key` — API 密钥
- `base_url` — API 地址（默认：`https://openrouter.ai/api/v1`）
- `model` — 模型名称（默认：`google/gemini-3.1-flash-lite-preview`）

如果选 `openclaw`，安装阶段只询问最小必要配置：
- `binary_path` — openclaw 可执行文件路径（先自动探测；探测失败时再手动输入完整路径）
- `translation_agent_id` — 翻译任务的 agent（默认：`daliy_paper-translation`）
- `filter_agent_id` — 论文打分的 agent（默认：`daliy_paper-filter`）
- `review_agent_id` — 深度分析的 agent（默认：`daliy_paper-graduate-student`，可留默认）
- `timeout_seconds` — LLM 响应超时时间（默认：`300`）

安装阶段**不要强制询问**每个 agent 的模型，也不要一开始就展开高级 OpenClaw 路由配置。优先先让系统跑起来，再在后续高级配置里调整。

建议：使用三个独立 agent 而不是一个共享 agent，这样可以为不同任务分配不同模型；默认建议使用带项目前缀的名称，避免和用户现有 agent 冲突。

---

#### Q5. 论文投递目标

> **为什么重要**：论文打分和翻译完成后，会被推送到一个 OpenClaw session。后台服务运行时并没有“当前对话”这个概念，所以最终必须把一个明确的 `session_key` 写进配置里。

安装阶段建议这样做：
- 先运行 `openclaw sessions --json`
- 如果能列出 session，就把**最近一个候选 session**展示给用户确认
- 询问：`我找到一个最近使用的 session，建议先用它作为默认接收会话。这样可以吗？`
- 如果用户不同意，再让用户手动输入 `session_key`

重要：不要无确认地直接假定“当前对话”就是最终投递目标。可以把候选 session 作为默认建议值，但必须让用户确认。

---

#### Q6. 研究生精读模式（Graduate Student Briefing）

> **为什么重要**：标准摘要包含标题、分数、推荐理由和摘要。研究生精读模式会额外生成更丰富的分析：机构提取、贡献点、结论点、实验要点和重要性总结。每篇论文消耗更多 LLM token，但能给出更有价值的每日推送。

对 LLM agent 的推荐交互方式：

- 先给默认建议：`我建议先关闭研究生精读模式，先把主流程跑通、控制 token 成本。这样可以吗？`
- 如果用户接受：写入 `openclaw.enable_graduate_student_briefing = false`
- 如果用户明确需要更详细的每日分析：再打开该选项并说明会增加 LLM 消耗

选项：
- `false`（默认）— 标准摘要，token 消耗较低
- `true` — 深度精读分析，信息更丰富

---

#### Q7. 定时任务配置

> **为什么重要**：调度器控制系统何时自动从 arXiv 抓取新论文、何时将打分后的论文投递到你的 session。不配置调度的话，所有操作都需要手动通过 API 触发。

对 LLM agent 的推荐交互方式：

- 先直接给默认方案：`我建议先开启定时任务，抓取时间用 02:00，推送时间用 ["09:00"]。这样可以吗？`
- 如果用户接受：直接写入默认调度配置
- 如果用户不同意：再继续问要不要关闭调度，或改成哪些具体时间

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
- 优先使用三个独立 agent：`daliy_paper-translation`、`daliy_paper-filter`、`daliy_paper-graduate-student`。
- 如果用户没有提供完整的 LLM 配置，仍然以最小可运行配置完成安装。
- 投递使用配置的 `openclaw.session_key`，运行时通过 `openclaw sessions --json` 解析实际 sessionId。

### Step 0.5: 把用户回答映射成实际配置

安装时问到的内容，最终要落到这些配置键上：

- `Q1 研究方向描述` -> `research_description`
- `Q1 自动生成的评分锚点` -> `llm_filter.scoring_anchors`
- `Q2 推荐/确认后的 arXiv 分类` -> `arxiv.keywords`
- `Q3 数据库选择` -> `database.engine` + `database.sqlite_path` 或 MySQL 连接字段
- `Q4 LLM 后端选择` -> `llm_filter.backend` 及其子字段
- `Q5 投递目标` -> `openclaw.session_key`
- `Q6 精读模式` -> `openclaw.enable_graduate_student_briefing`
- `Q7 定时任务` -> `schedule.enable_schedule`、`schedule.fetch_papers.*`、`schedule.push_papers.*`

运行链路也要心里有数：

- `arxiv.keywords` 用于抓取论文原始候选集
- `research_description` + `llm_filter.scoring_anchors` 一起进入论文相关度评分 prompt
- `openclaw.session_key` 决定论文最终投递到哪个 session
- `schedule.*` 决定抓取和推送何时自动执行

其中 `scoring_anchors` 的场景最容易被忽略：它不是给用户看的展示字段，而是给 LLM 打分时用的“评分参考”。系统会把它和 `research_description` 一起拼进评分 prompt，帮助模型稳定地区分高相关 / 中相关 / 低相关论文。

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

本项目需要 **Python 3.12**，推荐使用 [uv](https://github.com/astral-sh/uv) 管理虚拟环境（速度更快，且可自动下载指定 Python 版本）。

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

#### 3b. 创建 Python 3.12 虚拟环境

```bash
uv venv .venv --python 3.12
```

> uv 会自动下载 Python 3.12（如果本机尚未安装），无需手动配置。

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

Create `config.local.json` based on the user's answers from Step 0.

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
    "scoring_anchors": "<anchors confirmed from Q1>",
    "api_key": "<if openai_compatible>",
    "base_url": "<if openai_compatible>",
    "model": "<if openai_compatible>",
    "openclaw": {
      "binary_path": "openclaw",
      "translation_agent_id": "daliy_paper-translation",
      "filter_agent_id": "daliy_paper-filter",
      "review_agent_id": "daliy_paper-graduate-student",
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

补充理解：

- `research_description` 描述“你在研究什么”
- `arxiv.keywords` 决定“先从 arXiv 抓哪些论文进来”
- `llm_filter.scoring_anchors` 决定“LLM 用什么标准给这些论文打相关度分数”

三者分工不同，不要混成一个字段。

**配置优先级说明**：首次启动时，`config.local.json` 的内容会被自动迁移到数据库 `system_config` 表。此后数据库成为唯一配置源，再修改 `config.local.json` **不会生效**。如果需要变更已运行系统的配置，必须通过以下方式之一：

- Web 管理界面的配置页面
- API 接口：`PUT /api/config/{name}`
- 删除数据库中 `system_config` 对应行后重启（会重新从文件迁移）

### Step 6: 创建 OpenClaw Agents（仅 openclaw 后端）

如果用户在 Q4 选择了 `openclaw` 作为 LLM 后端，需要在启动前创建三个专用 agent。每个 agent 负责一类任务，可以绑定不同模型。

#### 6a. 检查已有 agents

```bash
openclaw agents list
```

如果输出中已经包含用户指定的三个 agent ID（例如 `daliy_paper-filter`、`daliy_paper-translation`、`daliy_paper-graduate-student`），跳过创建。

#### 6b. 创建 agents

使用用户在 Q4 中确认的 agent ID。默认名称带 `daliy_paper-` 前缀，避免与用户已有 agent 冲突。用户可以自定义名称，只要和 `config.local.json` 中写入的 `filter_agent_id`、`translation_agent_id`、`review_agent_id` 保持一致即可。

`<project_dir>` 替换为项目实际路径（即 `git clone` 后的目录绝对路径）。

```bash
openclaw agents add <filter_agent_id> --workspace <project_dir> --non-interactive
openclaw agents add <translation_agent_id> --workspace <project_dir> --non-interactive
openclaw agents add <review_agent_id> --workspace <project_dir> --non-interactive
```

使用默认名称的示例：

```bash
openclaw agents add daliy_paper-filter --workspace /home/yourname/daliy_paper_openclaw --non-interactive
openclaw agents add daliy_paper-translation --workspace /home/yourname/daliy_paper_openclaw --non-interactive
openclaw agents add daliy_paper-graduate-student --workspace /home/yourname/daliy_paper_openclaw --non-interactive
```

不指定 `--model` 时，agent 默认使用 main agent 的 Primary Model。如果需要为某个 agent 单独指定模型，加 `--model` 参数：

```bash
openclaw agents add daliy_paper-filter --workspace <project_dir> --model <model_id> --non-interactive
```

#### 6c. 验证创建结果

```bash
openclaw agents list
```

确认输出中包含刚创建的三个 agent。

#### 6d. 确保 config.local.json 中的 agent ID 与实际创建的名称一致

如果用户使用了自定义名称（非默认的 `daliy_paper-*`），回到 `config.local.json` 确认 `llm_filter.openclaw` 下的三个 ID 字段与实际创建的 agent 名称完全匹配：

```json
"openclaw": {
  "translation_agent_id": "<实际创建的翻译 agent 名称>",
  "filter_agent_id": "<实际创建的筛选 agent 名称>",
  "review_agent_id": "<实际创建的精读 agent 名称>"
}
```

### Step 7: Verify OpenClaw access

```bash
openclaw sessions --json
```

Optional smoke test:

```bash
openclaw agent --agent main --json --message "Reply with exactly: ok"
```

### Step 8: Start the app

```bash
python app.py
```

If port `20001` is already in use, use other port:

```bash
python app.py --port <new_port>
```

### Step 9: Verify setup

```bash
curl http://127.0.0.1:<new_port>/api/health
curl http://127.0.0.1:<new_port>/api/config/all
```

### Step 10: Optional runtime configuration

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
        "translation_agent_id": "daliy_paper-translation",
        "filter_agent_id": "daliy_paper-filter",
        "review_agent_id": "daliy_paper-graduate-student",
        "translation_model": "",
        "filter_model": "",
        "review_model": "",
        "timeout_seconds": 300,
        "use_local": false
      }
    }
  }'
```

### Step 11: Manual verification

Run at least one of these after install:

```bash
curl -X POST http://127.0.0.1:<new_port>/api/actions/process-now
curl -X POST http://127.0.0.1:<new_port>/api/actions/deliver-now
```

---

## 🎉 安装完成！

恭喜！**daliy_paper_openclaw** 已成功安装并启动。

**Agent 须知：请执行以下命令，并将完整配置内容直接输出给用户，让用户确认配置是否正确：**

```bash
curl http://127.0.0.1:<port>/api/config/all
```

---

### 修改配置

如果需要修改任何配置，有两种方式：

**方式一（推荐）：直接告诉我**

在这个对话中直接说明你想改什么，我会帮你完成修改。例如：
- "把推送时间改成 08:00 和 20:00"
- "把研究方向描述改成……"
- "换一个 LLM 模型"

**方式二：通过后端 API 直接修改**

```bash
curl -X PUT http://127.0.0.1:<port>/api/config/<配置名称> \
  -H 'Content-Type: application/json' \
  --data '{"config": { ... }}'
```

配置名称可以是：`research_description`、`arxiv`、`llm_filter`、`openclaw`、`schedule` 等。

---

如果配置没有问题，系统将按你设置的定时任务自动运行：

- **抓取论文**：每天在设定的 `fetch_papers.time`（默认 `02:00`）从 arXiv 拉取最新论文，并经 LLM 打分筛选
- **推送论文**：在设定的 `push_papers.times`（默认 `["09:00"]`）将打分后的优质论文推送到你的 OpenClaw session

无需任何手动操作，它会在后台安静地为你工作。🚀
