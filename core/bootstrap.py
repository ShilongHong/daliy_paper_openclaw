import json
import subprocess
import shutil
from pathlib import Path

from core.config_loader import load_settings
from storage.factory import create_store


def _prompt_bool(prompt: str, default: bool) -> bool:
    default_label = "Y/n" if default else "y/N"
    answer = input(f"{prompt}（{default_label}）: ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes", "true", "1"}


def _prompt_int(prompt: str, default: int) -> int:
    answer = input(f"{prompt}（默认 {default}）: ").strip()
    if not answer:
        return default
    try:
        return int(answer)
    except ValueError:
        return default


def _prompt_list(prompt: str, default: list[str]) -> list[str]:
    answer = input(f"{prompt}（默认 {', '.join(default)}）: ").strip()
    if not answer:
        return default
    values = [item.strip() for item in answer.split(",")]
    return [item for item in values if item] or default


def _discover_openclaw_models(binary_path: str) -> list[str]:
    try:
        result = subprocess.run(
            [binary_path, "models", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            return []
        payload = json.loads(result.stdout or "{}")
        models = payload.get("models", [])
        if not isinstance(models, list):
            return []
        return [
            str(item.get("key"))
            for item in models
            if isinstance(item, dict) and item.get("key")
        ]
    except Exception:
        return []


def _list_openclaw_agents(binary_path: str) -> set[str]:
    try:
        result = subprocess.run(
            [binary_path, "agents", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            return set()
        payload = json.loads(result.stdout or "[]")
        if not isinstance(payload, list):
            return set()
        return {
            str(item.get("id"))
            for item in payload
            if isinstance(item, dict) and item.get("id")
        }
    except Exception:
        return set()


def _discover_openclaw_binary() -> str:
    candidates = [
        shutil.which("openclaw"),
        shutil.which("openclaw.cmd"),
        shutil.which("openclaw.exe"),
    ]
    for candidate in candidates:
        if candidate:
            return candidate
    return "openclaw"


def _prompt_model_choice(prompt: str, models: list[str], default: str) -> str:
    if models:
        print(f"可用模型: {', '.join(models)}")
    answer = input(f"{prompt}（默认 {default}）: ").strip()
    if not answer:
        return default
    if models and answer not in models:
        return default
    return answer


def _ensure_openclaw_agent(
    binary_path: str,
    agent_id: str,
    model_id: str,
    workspace_dir: str,
) -> bool | tuple[bool, str]:
    if agent_id in _list_openclaw_agents(binary_path):
        return True

    command = [
        binary_path,
        "agents",
        "add",
        agent_id,
        "--workspace",
        workspace_dir,
        "--non-interactive",
    ]
    if model_id:
        command.extend(["--model", model_id])

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode == 0:
        return True

    reason = (result.stderr or result.stdout or "未知错误").strip()
    return False, reason


def build_local_config(
    database_engine: str = "sqlite",
    sqlite_path: str = "data/paper2data.db",
    mysql_config: dict[str, object] | None = None,
    session_key: str = "main",
    binary_path: str = "openclaw",
    timeout_seconds: int = 300,
    research_description: str = "",
    arxiv_keywords: list[str] | None = None,
    llm_filter: dict[str, object] | None = None,
    schedule: dict[str, object] | None = None,
) -> dict[str, object]:
    database_config: dict[str, object] = {
        "engine": database_engine,
        "sqlite_path": sqlite_path,
    }
    if database_engine == "mysql" and mysql_config:
        database_config.update(mysql_config)

    return {
        "database": database_config,
        "openclaw": {
            "session_key": session_key,
            "binary_path": binary_path,
            "timeout_seconds": timeout_seconds,
        },
        "research_description": research_description,
        "arxiv": {
            "keywords": arxiv_keywords or ["cs.CL", "cs.CV", "cs.LG", "cs.AI", "cs.IR"],
        },
        "llm_filter": llm_filter or {},
        "schedule": schedule or {},
    }


def write_local_config(target: Path, config: dict[str, object]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def initialize_store(local_config_path: Path) -> None:
    settings = load_settings(local_config_path=str(local_config_path))
    store = create_store(settings)
    store.init_schema()


def run_init_wizard() -> Path:
    database_engine = (
        input("数据库类型（sqlite/mysql，默认 sqlite）: ").strip() or "sqlite"
    )
    sqlite_path = "data/paper2data.db"
    mysql_config: dict[str, object] = {}
    if database_engine == "sqlite":
        sqlite_path = (
            input("SQLite 文件路径（默认 data/paper2data.db）: ").strip() or sqlite_path
        )
    else:
        mysql_config = {
            "host": input("MySQL 主机（默认 localhost）: ").strip() or "localhost",
            "port": _prompt_int("MySQL 端口", 3306),
            "user": input("MySQL 用户（默认 root）: ").strip() or "root",
            "password": input("MySQL 密码（默认空）: ").strip(),
            "database": input("MySQL 数据库名（默认 paper2data）: ").strip()
            or "paper2data",
            "charset": input("MySQL 字符集（默认 utf8mb4）: ").strip()
            or "utf8mb4",
        }

    session_key = input("OpenClaw session key（默认 main）: ").strip() or "main"
    discovered_binary = _discover_openclaw_binary()
    if discovered_binary != "openclaw":
        print(f"检测到 OpenClaw 命令路径: {discovered_binary}")
    else:
        print(
            "未自动探测到 OpenClaw 命令，若默认值不可用，请输入完整路径（例如 ~/.nvm/.../openclaw）"
        )
    binary_path = (
        input(f"OpenClaw 命令路径（默认 {discovered_binary}）: ").strip()
        or discovered_binary
    )
    timeout_seconds = _prompt_int("OpenClaw 超时秒数", 300)

    research_description = input("研究方向描述（可留空，后续在 Web 中填写）: ").strip()
    arxiv_keywords = _prompt_list(
        "ArXiv 关键词/分类（逗号分隔）",
        ["cs.CL", "cs.CV", "cs.LG", "cs.AI", "cs.IR"],
    )

    llm_enabled = _prompt_bool("是否启用 LLM 筛选", True)
    llm_backend = (
        input("LLM 后端（openai_compatible/openclaw，默认 openai_compatible）: ").strip()
        or "openai_compatible"
    )
    llm_filter: dict[str, object] = {
        "enable": llm_enabled,
        "backend": llm_backend,
        "model": input("LLM 模型名（默认 deepseek-ai/DeepSeek-V3.2）: ").strip()
        or "deepseek-ai/DeepSeek-V3.2",
    }
    if llm_backend == "openai_compatible":
        llm_filter.update(
            {
                "api_key": input("LLM API Key（可留空）: ").strip(),
                "base_url": input(
                    "LLM Base URL（默认 https://api.siliconflow.cn/v1/）: "
                ).strip()
                or "https://api.siliconflow.cn/v1/",
            }
        )
    else:
        available_models = _discover_openclaw_models(binary_path)
        default_model = available_models[0] if available_models else ""
        translation_agent_id = (
            input("翻译 Agent ID（默认 daliy_paper-translation）: ").strip()
            or "daliy_paper-translation"
        )
        filter_agent_id = (
            input("筛选 Agent ID（默认 daliy_paper-filter）: ").strip()
            or "daliy_paper-filter"
        )
        review_agent_id = (
            input("精读 Agent ID（默认 daliy_paper-graduate-student）: ").strip()
            or "daliy_paper-graduate-student"
        )
        translation_model = _prompt_model_choice(
            "翻译 Agent 模型",
            available_models,
            default_model,
        )
        filter_model = _prompt_model_choice(
            "筛选 Agent 模型",
            available_models,
            default_model,
        )
        review_model = _prompt_model_choice(
            "精读 Agent 模型",
            available_models,
            default_model,
        )

        workspace_dir = str(Path(__file__).resolve().parents[1])
        for agent_id, model_id in [
            (translation_agent_id, translation_model),
            (filter_agent_id, filter_model),
            (review_agent_id, review_model),
        ]:
            ensure_result = _ensure_openclaw_agent(
                binary_path,
                agent_id,
                model_id,
                workspace_dir,
            )
            if ensure_result is True:
                continue

            reason = ""
            if isinstance(ensure_result, tuple):
                _, reason = ensure_result

            message = f"创建 OpenClaw Agent 失败: {agent_id}"
            if reason:
                message = f"{message}，原因: {reason}"
            raise RuntimeError(message)

        llm_filter["openclaw"] = {
            "binary_path": binary_path,
            "translation_agent_id": translation_agent_id,
            "filter_agent_id": filter_agent_id,
            "review_agent_id": review_agent_id,
            "translation_model": translation_model,
            "filter_model": filter_model,
            "review_model": review_model,
            "timeout_seconds": _prompt_int("LLM OpenClaw 超时秒数", 300),
            "use_local": _prompt_bool("LLM 是否优先使用本地 OpenClaw", False),
        }

    enable_schedule = _prompt_bool("是否启用定时任务", True)
    schedule: dict[str, object] = {
        "enable_schedule": enable_schedule,
        "fetch_papers": {
            "enable": _prompt_bool("是否启用定时抓取", True),
            "time": input("定时抓取时间（默认 02:00）: ").strip() or "02:00",
        },
        "push_papers": {
            "enable": _prompt_bool("是否启用定时推送", True),
            "times": _prompt_list("定时推送时间（逗号分隔）", ["09:00"]),
        },
    }

    config = build_local_config(
        database_engine=database_engine,
        sqlite_path=sqlite_path,
        mysql_config=mysql_config,
        session_key=session_key,
        binary_path=binary_path,
        timeout_seconds=timeout_seconds,
        research_description=research_description,
        arxiv_keywords=arxiv_keywords,
        llm_filter=llm_filter,
        schedule=schedule,
    )
    target = Path(__file__).resolve().parents[1] / "config.local.json"
    write_local_config(target, config)
    initialize_store(target)
    return target
