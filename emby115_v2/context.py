from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4


DEFAULT_VIDEO_EXTENSIONS = (
    ".mkv",
    ".iso",
    ".ts",
    ".mp4",
    ".avi",
    ".rmvb",
    ".wmv",
    ".m2ts",
    ".mpg",
    ".flv",
    ".rm",
    ".m4v",
    ".mov",
    ".vob",
    ".webm",
    ".divx",
    ".3gp",
)


@dataclass(frozen=True)
class PathPair:
    """A source folder and the local symlink workspace it maps into."""

    name: str
    source: Path
    target: Path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PathPair":
        return cls(
            name=str(data.get("name") or "default"),
            source=Path(str(data["source"])).expanduser(),
            target=Path(str(data["target"])).expanduser(),
        )


@dataclass(frozen=True)
class SymlinkOptions:
    video_extensions: tuple[str, ...] = DEFAULT_VIDEO_EXTENSIONS
    thread_count: int = 4
    report_broken_links: bool = True
    auto_clear_workspace: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SymlinkOptions":
        if not data:
            return cls()
        extensions = data.get("video_extensions", DEFAULT_VIDEO_EXTENSIONS)
        return cls(
            video_extensions=tuple(str(ext).lower() for ext in extensions),
            thread_count=max(1, min(int(data.get("thread_count", 4)), 32)),
            report_broken_links=bool(data.get("report_broken_links", True)),
            auto_clear_workspace=bool(data.get("auto_clear_workspace", True)),
        )


@dataclass(frozen=True)
class ReportConfig:
    output_dir: Path = Path("reports")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ReportConfig":
        if not data:
            return cls()
        return cls(output_dir=Path(str(data.get("output_dir", "reports"))).expanduser())


@dataclass(frozen=True)
class LoggingConfig:
    log_level: str = "INFO"
    log_dir: Path = Path("logs")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "LoggingConfig":
        if not data:
            return cls()
        return cls(
            log_level=str(data.get("log_level", "INFO")).upper(),
            log_dir=Path(str(data.get("log_dir", "logs"))).expanduser(),
        )


@dataclass(frozen=True)
class TmdbConfig:
    api_key: str = ""
    language: str = "zh-CN"
    fallback_language: str = "en-US"
    image_language_priority: tuple[str, ...] = ("zh-CN", "en-US", "null")
    timeout: float = 10.0
    rate_limit_per_second: float = 4.0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TmdbConfig":
        if not data:
            return cls()
        image_languages = data.get("image_language_priority", ("zh-CN", "en-US", "null"))
        if isinstance(image_languages, str):
            image_languages = [item.strip() for item in image_languages.split(",") if item.strip()]
        return cls(
            api_key=str(data.get("api_key", "")),
            language=str(data.get("language") or "zh-CN"),
            fallback_language=str(data.get("fallback_language") or "en-US"),
            image_language_priority=tuple(str(item) for item in image_languages),
            timeout=max(1.0, float(data.get("timeout", 10.0))),
            rate_limit_per_second=max(0.1, float(data.get("rate_limit_per_second", 4.0))),
        )


@dataclass(frozen=True)
class LlmConfig:
    enabled: bool = True
    provider: str = "openai_compatible"
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.0
    timeout: float = 30.0
    max_candidates_per_decision: int = 5

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "LlmConfig":
        if not data:
            return cls()
        return cls(
            enabled=bool(data.get("enabled", True)),
            provider=str(data.get("provider") or "openai_compatible"),
            base_url=str(data.get("base_url", "")),
            api_key=str(data.get("api_key", "")),
            model=str(data.get("model", "")),
            temperature=float(data.get("temperature", 0.0)),
            timeout=max(1.0, float(data.get("timeout", 30.0))),
            max_candidates_per_decision=max(1, min(int(data.get("max_candidates_per_decision", 5)), 20)),
        )


@dataclass(frozen=True)
class MetadataOutputConfig:
    media_type: str = "movies"
    library_path: Path = Path("")
    write_nfo: bool = True
    download_images: bool = True
    download_episode_thumbs: bool = True
    download_season_posters: bool = True
    overwrite_existing: bool = False
    auto_rename: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "MetadataOutputConfig":
        if not data:
            return cls()
        media_type = str(data.get("media_type") or "movies")
        if media_type not in {"movies", "tvshows"}:
            media_type = "movies"
        return cls(
            media_type=media_type,
            library_path=Path(str(data.get("library_path", ""))).expanduser(),
            write_nfo=bool(data.get("write_nfo", True)),
            download_images=bool(data.get("download_images", True)),
            download_episode_thumbs=bool(data.get("download_episode_thumbs", True)),
            download_season_posters=bool(data.get("download_season_posters", True)),
            overwrite_existing=bool(data.get("overwrite_existing", False)),
            auto_rename=bool(data.get("auto_rename", True)),
        )


@dataclass(frozen=True)
class CloudLibraryOutputConfig:
    wait_minutes: int = 60
    move_videos_after_wait: bool = True
    overwrite_metadata: bool = False
    overwrite_videos: bool = False
    upload_wait_strategy: str = "fixed"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "CloudLibraryOutputConfig":
        if not data:
            return cls()
        upload_wait_strategy = str(data.get("upload_wait_strategy") or "fixed")
        if upload_wait_strategy not in {"fixed", "clouddrive2", "clouddrive2_or_fixed"}:
            upload_wait_strategy = "fixed"
        return cls(
            wait_minutes=max(0, int(data.get("wait_minutes", 60))),
            move_videos_after_wait=True,
            overwrite_metadata=bool(data.get("overwrite_metadata", False)),
            overwrite_videos=bool(data.get("overwrite_videos", False)),
            upload_wait_strategy=upload_wait_strategy,
        )


@dataclass(frozen=True)
class CloudDrive2Config:
    endpoint: str = "127.0.0.1:19798"
    api_token: str = ""
    timeout: float = 10.0
    poll_interval_seconds: float = 0.5
    settle_seconds: float = 30.0
    max_wait_minutes: int = 60
    page_size: int = 100
    max_pages: int = 50

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "CloudDrive2Config":
        if not data:
            return cls()
        return cls(
            endpoint=str(data.get("endpoint") or "127.0.0.1:19798"),
            api_token=str(data.get("api_token", "")),
            timeout=max(1.0, float(data.get("timeout", 10.0))),
            poll_interval_seconds=max(0.5, float(data.get("poll_interval_seconds", 0.5))),
            settle_seconds=max(0.0, float(data.get("settle_seconds", 30.0))),
            max_wait_minutes=max(0, int(data.get("max_wait_minutes", 60))),
            page_size=max(1, int(data.get("page_size", 100))),
            max_pages=max(1, int(data.get("max_pages", 50))),
        )


@dataclass(frozen=True)
class AppContext:
    """Unified context object consumed by V2 core services."""

    action: str
    run_id: str = field(default_factory=lambda: uuid4().hex)
    workflow_id: str = "manual"
    dry_run: bool = False
    non_interactive: bool = False
    path_pairs: tuple[PathPair, ...] = ()
    symlink: SymlinkOptions = field(default_factory=SymlinkOptions)
    tmdb: TmdbConfig = field(default_factory=TmdbConfig)
    llm: LlmConfig = field(default_factory=LlmConfig)
    metadata_output: MetadataOutputConfig = field(default_factory=MetadataOutputConfig)
    cloud_library_output: CloudLibraryOutputConfig = field(default_factory=CloudLibraryOutputConfig)
    clouddrive2: CloudDrive2Config = field(default_factory=CloudDrive2Config)
    report: ReportConfig = field(default_factory=ReportConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppContext":
        path_pairs = tuple(PathPair.from_dict(item) for item in data.get("path_pairs", []))
        return cls(
            action=str(data.get("action") or "build_symlink_workspace"),
            run_id=str(data.get("run_id") or uuid4().hex),
            workflow_id=str(data.get("workflow_id") or "manual"),
            dry_run=bool(data.get("dry_run", False)),
            non_interactive=bool(data.get("non_interactive", False)),
            path_pairs=path_pairs,
            symlink=SymlinkOptions.from_dict(data.get("symlink")),
            tmdb=TmdbConfig.from_dict(data.get("tmdb")),
            llm=LlmConfig.from_dict(data.get("llm")),
            metadata_output=MetadataOutputConfig.from_dict(data.get("metadata_output")),
            cloud_library_output=CloudLibraryOutputConfig.from_dict(data.get("cloud_library_output")),
            clouddrive2=CloudDrive2Config.from_dict(data.get("clouddrive2")),
            report=ReportConfig.from_dict(data.get("report")),
            logging=LoggingConfig.from_dict(data.get("logging")),
            raw=dict(data),
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["path_pairs"] = [
            {"name": pair.name, "source": str(pair.source), "target": str(pair.target)}
            for pair in self.path_pairs
        ]
        result["report"]["output_dir"] = str(self.report.output_dir)
        result["logging"]["log_dir"] = str(self.logging.log_dir)
        result["metadata_output"]["library_path"] = str(self.metadata_output.library_path)
        return result
