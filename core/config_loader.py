import json
from copy import deepcopy
from pathlib import Path
from typing import Protocol, cast

from core.settings import DEFAULT_SETTINGS


JsonValue = object
JsonDict = dict[str, JsonValue]


class RuntimeStore(Protocol):
    def get_all_configs(self) -> JsonDict: ...


def deep_merge(base: JsonDict, override: JsonDict) -> JsonDict:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            nested_base = cast(JsonDict, base[key])
            nested_value = cast(JsonDict, value)
            _ = deep_merge(nested_base, nested_value)
        else:
            base[key] = value
    return base


def load_settings(
    local_config_path: str = "config.local.json",
    runtime_store: RuntimeStore | None = None,
) -> JsonDict:
    settings = cast(JsonDict, deepcopy(DEFAULT_SETTINGS))
    local_path = Path(local_config_path)

    if local_path.exists():
        local_data = cast(JsonDict, json.loads(local_path.read_text(encoding="utf-8")))
        _ = deep_merge(settings, local_data)

    if runtime_store is not None:
        runtime_config = runtime_store.get_all_configs()
        _ = deep_merge(settings, runtime_config)

    return settings


def get_settings_section(
    name: str,
    default: JsonDict | None = None,
    *,
    local_config_path: str = "config.local.json",
) -> JsonDict:
    settings = load_settings(local_config_path=local_config_path)
    value = settings.get(name)
    if isinstance(value, dict):
        return cast(JsonDict, deepcopy(value))
    return cast(JsonDict, deepcopy(default or {}))


def get_string_setting(
    name: str,
    default: str = "",
    *,
    local_config_path: str = "config.local.json",
) -> str:
    settings = load_settings(local_config_path=local_config_path)
    value = settings.get(name, default)
    if isinstance(value, str):
        return value
    return default
