# daliy_paper_openclaw

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

`daliy_paper_openclaw` 是一个把 ArXiv 抓取、LLM 筛选、中文翻译、队列管理和 OpenClaw 投递放在一起的单进程项目。它适合把“每天看论文”这件事自动化：抓论文、按研究方向打分、整理成摘要，再定时发到你的 OpenClaw session。

## What It Does

- 抓取 ArXiv 分类或关键词对应的新论文
- 用研究方向描述做相关度筛选
- 生成中文标题、中文摘要、推荐理由和潜在帮助
- 把结果写入本地数据库并加入推送队列
- 按手动触发或定时任务投递到 OpenClaw

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
python -m venv .venv || uv venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.local.example.json config.local.json
python app.py
```

启动后验证：

```bash
curl http://127.0.0.1:20001/api/health
curl http://127.0.0.1:20001/api/config/all
openclaw sessions --json
```

## Configuration

项目配置分 4 层：默认配置、`config.local.json`、数据库运行时配置、Web/API 配置。

安装时最重要的是这些：

- `research_description`：你的研究方向描述
- `arxiv.keywords`：抓取的分类或关键词
- `llm_filter`：筛选/翻译用的模型后端配置
- `openclaw.session_key`：论文最终投递到哪个 OpenClaw session
- `schedule`：定时抓取和定时推送时间

注意：论文投递不会自动取“当前会话”。后台服务会使用你配置的 `openclaw.session_key`，再在发送时解析成真实 `sessionId`。

如果你把 OpenClaw 也用作 LLM 后端，建议单独使用一个 agent，例如 `paper2data-llm`，不要和接收论文的用户会话混用。

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
├── config.py
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
