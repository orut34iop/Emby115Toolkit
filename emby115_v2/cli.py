from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any

from emby115_v2.app import run_context
from emby115_v2.config_loader import deep_merge, load_env_file, load_json_config
from emby115_v2.context import AppContext
from emby115_v2.logging_setup import setup_run_logger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emby115Toolkit V2 CLI")
    parser.add_argument("--action", help="要执行的动作，例如 build_symlink_workspace")
    parser.add_argument("--config", help="JSON 配置文件路径")
    parser.add_argument("--env", help=".env 配置文件路径")
    parser.add_argument("--dry-run", action="store_true", help="只生成计划和报告，不执行写操作")
    parser.add_argument("--non-interactive", action="store_true", help="非交互模式，禁止等待 stdin")
    parser.add_argument("--json", action="store_true", help="向 stdout 输出 JSON 摘要")
    parser.add_argument("--report-dir", help="报告输出目录")
    parser.add_argument("--log-dir", help="日志输出目录")
    parser.add_argument("--log-level", help="日志级别")
    parser.add_argument("--thread-count", type=int, help="构建 symlink 工作区线程数")
    parser.add_argument("--pair-name", action="append", help="路径对名称，可与 --source/--target 一起重复使用")
    parser.add_argument("--source", action="append", help="源目录，可重复")
    parser.add_argument("--target", action="append", help="目标工作区目录，可重复")
    parser.add_argument("--serve-web", action="store_true", help="启动 V2 WebUI 后端服务")
    parser.add_argument("--host", default="127.0.0.1", help="Web 服务监听地址")
    parser.add_argument("--port", type=int, default=8765, help="Web 服务端口")
    parser.add_argument("--access-token", default="", help="WebUI 访问令牌；局域网监听时必须设置")
    return parser


def context_from_args(args: argparse.Namespace) -> AppContext:
    data: dict[str, Any] = {}
    data = deep_merge(data, load_env_file(args.env))
    data = deep_merge(data, load_json_config(args.config))

    cli_overrides: dict[str, Any] = {}
    if args.action:
        cli_overrides["action"] = args.action
    if args.dry_run:
        cli_overrides["dry_run"] = True
    if args.non_interactive:
        cli_overrides["non_interactive"] = True
    if args.report_dir:
        cli_overrides.setdefault("report", {})["output_dir"] = args.report_dir
    if args.log_dir:
        cli_overrides.setdefault("logging", {})["log_dir"] = args.log_dir
    if args.log_level:
        cli_overrides.setdefault("logging", {})["log_level"] = args.log_level
    if args.thread_count is not None:
        cli_overrides.setdefault("symlink", {})["thread_count"] = args.thread_count

    if args.source or args.target:
        sources = args.source or []
        targets = args.target or []
        if len(sources) != len(targets):
            raise ValueError("--source 和 --target 必须数量一致")
        names = args.pair_name or []
        path_pairs = []
        for index, (source, target) in enumerate(zip(sources, targets)):
            name = names[index] if index < len(names) else f"pair_{index + 1}"
            path_pairs.append({"name": name, "source": source, "target": target})
        cli_overrides["path_pairs"] = path_pairs

    data = deep_merge(data, cli_overrides)
    data.setdefault("action", "build_symlink_workspace")
    return AppContext.from_dict(data)


def run_cli(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.serve_web:
        return serve_web(args.host, args.port, args.access_token)

    context: AppContext | None = None
    logger = None
    try:
        context = context_from_args(args)
        logger = setup_run_logger(
            "emby115_v2",
            context.logging.log_dir,
            context.run_id,
            context.logging.log_level,
        )
        report = run_context(context, logger)
        paths = report.write()
        result = {
            "run_id": context.run_id,
            "action": context.action,
            "dry_run": context.dry_run,
            "reports": paths,
        }
        if args.json:
            sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
        else:
            sys.stdout.write(f"执行完成 run_id={context.run_id}\n")
            sys.stdout.write(f"HTML 报告: {paths['html']}\n")
            sys.stdout.write(f"JSON 报告: {paths['json']}\n")
        return 0
    except Exception as exc:
        message = f"执行失败: {exc}"
        if logger:
            logger.error(message)
            logger.error(traceback.format_exc())
        else:
            fallback_log = Path("logs")
            fallback_log.mkdir(parents=True, exist_ok=True)
            (fallback_log / "v2_cli_bootstrap_error.log").write_text(
                message + "\n" + traceback.format_exc(),
                encoding="utf-8",
            )
        sys.stderr.write(message + "\n")
        if args.json:
            sys.stdout.write(
                json.dumps(
                    {
                        "run_id": context.run_id if context else "",
                        "action": args.action or "",
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        return 1


def serve_web(host: str, port: int, access_token: str = "") -> int:
    if host not in {"127.0.0.1", "localhost", "::1"} and not access_token:
        sys.stderr.write("WebUI 监听非本机地址时必须设置 --access-token。\n")
        return 1
    try:
        import uvicorn

        from emby115_v2.web.api import create_app
    except ImportError as exc:
        sys.stderr.write(f"启动 WebUI 需要安装 fastapi 和 uvicorn: {exc}\n")
        return 1

    uvicorn.run(create_app(access_token=access_token, host=host, port=port), host=host, port=port)
    return 0


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
