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

### Step 0: Ask user about configuration

Ask the user these questions before installation:

1. Database type?
   - `sqlite`
   - `mysql`

2. If using SQLite, what file path should be used?
   - Default: `data/paper2data.db`

3. Which OpenClaw session should receive pushed papers?
   - Default: `main`
   - This is an explicit delivery target, not the "current" interactive session
   - Do not auto-infer the current session for a background service

4. Which LLM backend should be used?
   - `openai_compatible`
   - `openclaw`

5. If `openai_compatible`, ask for:
   - `api_key`
   - `base_url`
   - `model`

6. If `openclaw`, ask for:
   - `binary_path` (default: `openclaw`)
   - `translation_agent_id` (recommended: `translation`)
   - `filter_agent_id` (recommended: `filter`)
   - `review_agent_id` (recommended: `graduate-student`)
   - model for each agent, discovered from `openclaw models list --json`
   - `timeout_seconds` (default: `120`)
   - `use_local` (`true` or `false`)

7. Should timed fetch and timed delivery be enabled now?
   - If yes, ask for fetch time and push time
   - If no, finish installation first and verify manually

8. What research direction should be used for relevance scoring?
   - Ask for a short natural language description

9. Which ArXiv keywords/categories should be tracked?
   - Default: `cs.CL, cs.CV, cs.LG, cs.AI, cs.IR`

Important:

- Do not default OpenClaw LLM to the same user-facing session used for paper delivery.
- Prefer three dedicated agents: `translation`, `filter`, `graduate-student`.
- If the user does not provide full LLM config, still complete installation with a minimal runnable setup.
- Delivery uses configured `openclaw.session_key`, then resolves it against `openclaw sessions --json` at send time.

### Step 1: Install OpenClaw CLI

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

```bash
python -m venv .venv || uv venv .venv
source .venv/bin/activate
```

### Step 4: Install Python dependencies

```bash
pip install -r requirements.txt
```

### Step 5: Write local configuration

At minimum, create `config.local.json`.

Minimal SQLite + OpenClaw delivery config:

```json
{
  "database": {
    "engine": "sqlite",
    "sqlite_path": "data/paper2data.db"
  },
  "research_description": "请在这里填写你的研究方向描述",
  "arxiv": {
    "keywords": ["cs.CL", "cs.CV", "cs.LG"]
  },
  "openclaw": {
    "session_key": "main",
    "binary_path": "openclaw",
    "timeout_seconds": 120
  }
}
```

If the user wants OpenClaw as the LLM backend too, also configure runtime settings after startup through `/api/config/llm_filter`.
Create missing agents during setup with `openclaw agents add <name> --model <id> --workspace <repo> --non-interactive`.

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

If port `20001` is already in use, stop the old process first.

### Step 8: Verify setup

```bash
curl http://127.0.0.1:20001/api/health
curl http://127.0.0.1:20001/api/config/all
```

### Step 9: Optional runtime configuration

If the user chose OpenClaw as the LLM backend, configure it after startup:

```bash
curl -X PUT http://127.0.0.1:20001/api/config/llm_filter \
  -H 'Content-Type: application/json' \
  --data '{
    "config": {
      "enable": true,
      "backend": "openclaw",
      "api_key": "",
      "base_url": "https://api.siliconflow.cn/v1/",
      "model": "deepseek-ai/DeepSeek-V3.2",
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
        "timeout_seconds": 120,
        "use_local": false
      }
    }
  }'
```

### Step 10: Manual verification

Run at least one of these after install:

```bash
curl -X POST http://127.0.0.1:20001/api/actions/process-now
curl -X POST http://127.0.0.1:20001/api/actions/deliver-now
```
