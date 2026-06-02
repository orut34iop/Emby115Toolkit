from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_json_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    with config_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("配置文件根节点必须是 JSON object")
    return data


def load_env_file(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    env_path = Path(path)
    if not env_path.exists():
        raise FileNotFoundError(f".env 文件不存在: {env_path}")

    values: dict[str, str] = {}
    with env_path.open("r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")

    mapped: dict[str, Any] = {}
    if "EMBY115_ACTION" in values:
        mapped["action"] = values["EMBY115_ACTION"]
    if "EMBY115_REPORT_DIR" in values:
        mapped.setdefault("report", {})["output_dir"] = values["EMBY115_REPORT_DIR"]
    if "EMBY115_LOG_DIR" in values:
        mapped.setdefault("logging", {})["log_dir"] = values["EMBY115_LOG_DIR"]
    if "EMBY115_LOG_LEVEL" in values:
        mapped.setdefault("logging", {})["log_level"] = values["EMBY115_LOG_LEVEL"]
    return mapped

