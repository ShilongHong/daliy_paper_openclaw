# daliy_paper_openclaw Skill

> 自动抓取、筛选、翻译、精读、投递论文 - 面向 OpenClaw 的论文助手工作流

This skill describes how to operate `daliy_paper_openclaw` correctly as an agent-driven paper workflow.

## Overview

`daliy_paper_openclaw` is a three-in-one system:

- FastAPI backend
- built-in scheduler
- static frontend

Core workflow:

`arXiv -> raw papers -> filter -> translation -> relevant papers -> queue -> OpenClaw delivery`

## What This Project Can Do

- Discover papers from arXiv categories and keywords
- Score papers against a user-defined research direction
- Translate title and abstract into Chinese
- Optionally generate a richer Graduate Student briefing
- Push curated papers to a configured OpenClaw session
- Run on schedule or through manual API calls

## Required Concepts

There are two different OpenClaw roles in this project.

### 1. Delivery session

Used for final paper delivery.

- Config key: `openclaw.session_key`
- This is not the current interactive session
- The service resolves it against `openclaw sessions --json` at send time

### 2. LLM agents

Used for internal paper processing.

- `translation_agent_id`
- `filter_agent_id`
- `review_agent_id`

Recommended defaults:

- `translation`
- `filter`
- `graduate-student`

## Installation Workflow

Before installation, the agent must ask the user:

1. Database type: `sqlite` or `mysql`
2. Research direction description
3. arXiv keywords/categories
4. Delivery session key
5. LLM backend: `openai_compatible` or `openclaw`
6. If using OpenClaw:
   - binary path
   - translation agent id
   - filter agent id
   - review agent id
   - model for each agent
   - timeout
   - local mode on/off
7. Whether to enable scheduled fetch and scheduled delivery

Use the full guide:

```bash
curl -fsSL https://raw.githubusercontent.com/ShilongHong/daliy_paper_openclaw/main/docs/guide/installation.md
```

## Recommended OpenClaw Agent Layout

Use three dedicated agents instead of one shared agent:

```text
translation        -> title/abstract translation
filter             -> paper relevance scoring
graduate-student   -> deeper briefing enrichment
```

Recommended model split:

```text
translation        -> bailian/qwen3.5-plus
filter             -> bailian/MiniMax-M2.5
graduate-student   -> bailian/glm-5
```

Create agents if missing:

```bash
openclaw agents add translation --model bailian/qwen3.5-plus --workspace /path/to/repo --non-interactive
openclaw agents add filter --model bailian/MiniMax-M2.5 --workspace /path/to/repo --non-interactive
openclaw agents add graduate-student --model bailian/glm-5 --workspace /path/to/repo --non-interactive
```

## Core Runtime Commands

### Start service

```bash
python app.py
```

### Health check

```bash
curl http://127.0.0.1:20001/api/health
```

### Read config

```bash
curl http://127.0.0.1:20001/api/config/all
```

### Trigger fetch

```bash
curl -X POST http://127.0.0.1:20001/api/actions/fetch-now
```

### Trigger process

```bash
curl -X POST http://127.0.0.1:20001/api/actions/process-now
```

### Trigger delivery

```bash
curl -X POST http://127.0.0.1:20001/api/actions/deliver-now
```

## Required Agent Behavior

When operating this project, the agent should:

1. Load current runtime config
2. Confirm delivery session and LLM backend
3. Confirm whether Graduate Student briefing is enabled
4. Use manual APIs before trusting scheduler behavior
5. Verify actual outputs, not just logs

## Briefing Modes

There are two delivery modes.

### Standard digest

Default, lower token cost.

- title
- score
- reason
- help
- author
- affiliation
- abstract
- link

### Graduate Student briefing

Optional, higher token cost.

- richer institution extraction
- contribution points
- conclusion points
- experiment points
- importance summary

Controlled by:

```text
openclaw.enable_graduate_student_briefing
```

Default: `false`

## Configuration Layers

Configuration priority is:

1. `config.py` defaults
2. `config.local.json`
3. runtime config stored by the app
4. Web/API updates through `/api/config/*`

Important runtime groups:

- `arxiv`
- `llm_filter`
- `openclaw`
- `schedule`
- `research_description`

## Manual Verification Checklist

After any significant change, verify:

```bash
curl http://127.0.0.1:20001/api/health
curl http://127.0.0.1:20001/api/config/all
openclaw sessions --json
openclaw agents list --json
openclaw models list --json
```

If OpenClaw is the LLM backend, also verify each route actually works:

- translation service returns Chinese text
- filter service returns a structured score
- graduate-student service returns enriched briefing fields

## Common Failure Modes

### Wrong session assumption

Do not assume the current OpenClaw chat is the delivery target.
Always use configured `openclaw.session_key`.

### Agent name mismatch

If config says `translation` but OpenClaw only has `translator`, calls will fail.
Agent ids in config must match `openclaw agents list --json`.

### Runtime config overrides local config

If `/api/config/all` still shows old values after editing `config.local.json`, the app runtime config may still override them.
Update through API or clear the runtime config source.

### Port already in use

If `20001` is occupied, start a separate instance on another port for testing.

## Files That Matter Most

```text
README.md
docs/guide/installation.md
core/bootstrap.py
core/runtime_config.py
services/llm_backend.py
services/llm_filter_service.py
services/translation_service.py
services/graduate_student_briefing_service.py
delivery/openclaw_notifier.py
app.py
```

## Output Rule

When reporting status, distinguish clearly between:

- delivery session success
- LLM agent routing success
- scheduler success
- richer briefing success

Do not collapse them into a single “works” statement.
