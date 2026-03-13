"""
配置兼容层（shim）
将旧版 `from config import XXX` 的调用桥接到新版 core/config_loader.py。
新代码请直接使用 core.config_loader.load_settings()。
"""

from typing import Any
from core.config_loader import load_settings

# 加载完整配置（不依赖数据库，仅读取本地文件）
_settings: dict[str, Any] = load_settings()  # type: ignore[assignment]


def _get(key: str, default: Any = None) -> Any:
    """从加载后的设置中安全取值"""
    return _settings.get(key, default)


# ----------------------------------------------------------------
# 研究方向描述
# ----------------------------------------------------------------
RESEARCH_DESCRIPTION: str = str(
    _get("research_description", "请在这里填写你的研究方向描述")
)

# ----------------------------------------------------------------
# arXiv 抓取配置
# ----------------------------------------------------------------
_db_cfg: dict[str, Any] = _get("database", {})  # type: ignore[assignment]

ARXIV_CONFIG: dict[str, Any] = {
    "keywords": _get("arxiv", {}).get("keywords", ["cs.CL", "cs.CV", "cs.LG"]),  # type: ignore[union-attr]
    "max_results": _get("arxiv", {}).get("max_results", 100),  # type: ignore[union-attr]
    "days_back": _get("arxiv", {}).get("days_back", 1),  # type: ignore[union-attr]
    "database": {
        "engine": _db_cfg.get("engine", "sqlite"),
        "sqlite_path": _db_cfg.get("sqlite_path", "data/paper2data.db"),
        "host": _db_cfg.get("host", "localhost"),
        "port": _db_cfg.get("port", 3306),
        "user": _db_cfg.get("user", "root"),
        "password": _db_cfg.get("password", ""),
        "database": _db_cfg.get("database", "paper2data"),
        "charset": _db_cfg.get("charset", "utf8mb4"),
        "table_raw": _db_cfg.get("table_raw", "papers_raw"),
        "table_relevant": _db_cfg.get("table_relevant", "papers_relevant"),
        "table_queue": _db_cfg.get("table_queue", "paper_queue"),
        "table_config": _db_cfg.get("table_config", "system_config"),
    },
}

# ----------------------------------------------------------------
# LLM 筛选 / 翻译配置
# ----------------------------------------------------------------
LLM_FILTER_CONFIG: dict[str, Any] = dict(_get("llm_filter", {}) or {})  # type: ignore[arg-type]

# ----------------------------------------------------------------
# OpenClaw 推送配置
# ----------------------------------------------------------------
OPENCLAW_CONFIG: dict[str, Any] = dict(_get("openclaw", {}) or {})  # type: ignore[arg-type]

# ----------------------------------------------------------------
# 调度配置
# ----------------------------------------------------------------
SCHEDULE_CONFIG: dict[str, Any] = dict(_get("schedule", {}) or {})  # type: ignore[arg-type]

# ----------------------------------------------------------------
# 输出 / 日志配置（仅供遗留服务使用）
# ----------------------------------------------------------------
OUTPUT_CONFIG: dict[str, Any] = dict(_get("output", {}) or {})  # type: ignore[arg-type]

LOGGING_CONFIG: dict[str, Any] = dict(
    _get(
        "logging",
        {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
    )
    or {}  # type: ignore[arg-type]
)
