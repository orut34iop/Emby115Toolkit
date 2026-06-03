from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


CONFIG_FILENAME = "emby115_v2.config.json"


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def default_config_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / CONFIG_FILENAME
    return Path(__file__).resolve().parents[1] / CONFIG_FILENAME


def default_metadata_config() -> dict[str, Any]:
    return {
        "tmdb": {
            "api_key": "",
            "language": "zh-CN",
            "fallback_language": "en-US",
            "image_language_priority": ["zh-CN", "en-US", "null"],
            "timeout": 10,
            "rate_limit_per_second": 4,
        },
        "llm": {
            "enabled": True,
            "provider": "openai_compatible",
            "base_url": "",
            "api_key": "",
            "model": "",
            "temperature": 0,
            "timeout": 30,
            "max_candidates_per_decision": 5,
        },
        "metadata_output": {
            "media_type": "movies",
            "library_path": "C:\\working-emby\\movies",
            "write_nfo": True,
            "download_images": True,
            "download_episode_thumbs": True,
            "download_season_posters": True,
            "overwrite_existing": False,
            "auto_rename": True,
        },
        "metadata_libraries": [
            {"enabled": True, "media_type": "movies", "library_path": "C:\\working-emby\\movies"},
            {"enabled": True, "media_type": "tvshows", "library_path": "C:\\working-emby\\tvshows"},
        ],
        "cloud_library_output": {
            "wait_minutes": 60,
            "move_videos_after_wait": True,
            "overwrite_metadata": False,
            "overwrite_videos": False,
            "upload_wait_strategy": "fixed",
        },
        "clouddrive2": {
            "endpoint": "127.0.0.1:19798",
            "api_token": "",
            "timeout": 10,
            "poll_interval_seconds": 0.5,
            "settle_seconds": 30,
            "max_wait_minutes": 60,
            "page_size": 100,
            "max_pages": 50,
        },
        "report": {"output_dir": "reports"},
        "logging": {"log_dir": "logs", "log_level": "INFO"},
    }


def load_metadata_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or default_config_path()
    if not config_path.exists():
        return default_metadata_config()
    with config_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("V2 配置文件根节点必须是 JSON object")
    return deep_merge(default_metadata_config(), data)


def save_metadata_config(data: dict[str, Any], path: Path | None = None) -> Path:
    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return config_path
