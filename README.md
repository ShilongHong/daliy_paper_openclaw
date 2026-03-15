# daliy_paper_openclaw

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

`daliy_paper_openclaw` 是一个把 ArXiv 抓取、LLM 筛选、中文翻译、队列管理、Web 界面和 OpenClaw 投递放在一起的单进程项目。它适合把“每天看论文”这件事自动化：抓论文、按研究方向打分、整理成摘要、在网页里管理，再定时发到你的 OpenClaw session。

> **告别信息过载。** 让 AI 帮你每天读 ArXiv，只把真正值得你看的论文推到面前。

## 核心亮点

- **🧠 懂你的筛选逻辑**：不是简单关键词匹配，而是基于你的自然语言研究方向描述做相关度判断。
- **📊 可视化管理界面**：内置 Web 仪表盘、论文列表、详情页和配置页，不只是后台脚本。
- **⚡ 单进程三合一**：FastAPI、调度器和静态前端一起启动，部署和维护成本很低。
- **💬 OpenClaw 直达**：筛选后的论文可以直接投递到 OpenClaw session，便于继续追问、改写和精读。

## What It Does

- 抓取 ArXiv 分类或关键词对应的新论文
- 用研究方向描述做相关度筛选
- 生成中文标题、中文摘要、推荐理由和潜在帮助
- 把结果写入本地数据库并加入推送队列
- 按手动触发或定时任务投递到 OpenClaw

## 界面概览

### 1. 全局仪表盘
查看系统状态、论文统计和整体运行情况。

![全局仪表盘](docs/images/dashboard.png)

### 2. 智能论文列表
按卡片方式浏览筛选后的论文，直接看到中文标题、推荐理由和相关度分数。

![论文列表](docs/images/paper_list.png)

### 3. 论文详情页
查看中英摘要、推荐理由、潜在帮助和论文链接，适合快速决定要不要深入读。

![论文详情](docs/images/detail.png)

### 4. 配置页面
直接在网页里修改研究方向、ArXiv 关键词和系统配置，不用反复改文件。

![系统配置](docs/images/config.png)

## Installation

优先让 agent 安装，不要手动一点点配。

### For Humans

把这段话直接贴给你的 LLM agent：

```text
Install and configure daliy_paper_openclaw by following the instructions here:
https://raw.githubusercontent.com/ShilongHong/daliy_paper_openclaw/main/docs/guide/installation.md
```

### For LLM Agents

直接拉安装指南：

```bash
curl -fsSL https://raw.githubusercontent.com/ShilongHong/daliy_paper_openclaw/main/docs/guide/installation.md
```

完整安装说明见 `docs/guide/installation.md`。

## Quick Start

最短启动路径：

```bash
npm install -g openclaw
git clone https://github.com/ShilongHong/daliy_paper_openclaw.git
cd daliy_paper_openclaw
uv venv .venv --python 3.11   # 需要 uv，见安装指南 Step 3
source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
cp config.local.example.json config.local.json
python app.py
```

注意：`cp config.local.example.json config.local.json` 只会复制示例配置，不会自动创建 OpenClaw agents；如果你要使用 `daliy_paper-translation`、`daliy_paper-filter`、`daliy_paper-graduate-student`，请运行 init wizard 或手动创建。

启动后验证：

```bash
curl http://127.0.0.1:20001/api/health
curl http://127.0.0.1:20001/api/config/all
openclaw sessions --json
```

## Configuration

项目配置分 4 层：默认配置、`config.local.json`、数据库运行时配置、Web/API 配置。

**注意**：首次启动时 `config.local.json` 会被自动迁移到数据库。此后数据库为唯一配置源，再改 `config.local.json` 不会生效。变更已运行系统的配置请用 Web 界面或 `PUT /api/config/{name}` 接口。

安装时最重要的是这些：

- `research_description`：你的研究方向描述
- `arxiv.keywords`：抓取的分类或关键词
- `llm_filter`：筛选/翻译用的模型后端配置
- `openclaw.delivery_channel` / `openclaw.delivery_target`：论文最终直发到哪个聊天目标
- `openclaw.session_key`：兼容模式下，论文投递到哪个 OpenClaw session
- `schedule`：定时抓取和定时推送时间

注意：论文投递不会自动取“当前会话”。如果配置了 `openclaw.delivery_channel` + `openclaw.delivery_target`，后台会直接调用 `openclaw message send`；否则才会回退到 `openclaw.session_key` 并解析真实 `sessionId`。

如果你把 OpenClaw 也用作 LLM 后端，建议优先使用分用途 agent，例如 `daliy_paper-translation`、`daliy_paper-filter`、`daliy_paper-graduate-student`；如果只想快速跑通，也可以先用单个 `main` 兼容模式，不要和接收论文的用户会话混用。

## Common Endpoints

```bash
curl http://127.0.0.1:20001/api/health
curl http://127.0.0.1:20001/api/config/all
curl -X POST http://127.0.0.1:20001/api/actions/fetch-now
curl -X POST http://127.0.0.1:20001/api/actions/process-now
curl -X POST http://127.0.0.1:20001/api/actions/deliver-now
```

## Project Layout

```text
daliy_paper_openclaw/
├── app.py
├── config.local.example.json
├── docs/guide/installation.md
├── core/
├── services/
├── delivery/
├── storage/
├── cli/
├── static/
└── tools/
```

## Notes

- 默认数据库是 SQLite
- 首次启动会自动建表
- 推送消息现在使用 markdown 摘要格式
- OpenClaw 作为 LLM 后端时支持多 agent 路由

## License

MIT
