"""Explicit CLI for previewing and applying historical Jellyfin field protection."""

import argparse
import json
import os
from urllib.parse import urlsplit

from media_server.client import MediaServerClient
from media_server.metadata_protection import FIELDS, apply_plan, create_plan


def main(argv=None):
    parser = argparse.ArgumentParser(description='预览和补充 Jellyfin 历史字段锁（不翻译或重读 NFO）')
    parser.add_argument('--server-url', required=True)
    parser.add_argument('--username', required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    preview = commands.add_parser('plan', help='只读取并导出备份及操作清单')
    scope = preview.add_mutually_exclusive_group(required=True)
    scope.add_argument('--item-id', action='append', default=[])
    scope.add_argument('--library-id', action='append', default=[])
    preview.add_argument('--fields', choices=FIELDS, nargs='+', required=True)
    preview.add_argument('--output', required=True)
    apply = commands.add_parser('apply', help='执行已审阅清单；再次执行同一清单和报告可重试失败项')
    apply.add_argument('--plan', required=True)
    apply.add_argument('--report', required=True)
    args = parser.parse_args(argv)
    url = urlsplit(args.server_url)
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
        parser.error('服务器地址必须为 HTTP(S)，不含凭据、查询参数或片段')
    key = os.environ.get('JELLYFIN_API_KEY')
    if not key:
        parser.error('请通过 JELLYFIN_API_KEY 环境变量提供 API Key，不放入命令行或清单')
    client = MediaServerClient(server_url=args.server_url, username=args.username, api_key=key, server_type='jellyfin')
    try:
        if args.command == 'plan':
            plan = create_plan(client, args.output, args.fields, args.item_id, args.library_id)
            print(json.dumps({'mode': 'read-only', 'items': len(plan['items']), 'plan': args.output}, ensure_ascii=False))
            return 0
        report = apply_plan(client, args.plan, args.report)
        print(json.dumps(report['summary'], ensure_ascii=False))
        return 0 if not report['cancelled'] and all(
            not count for status, count in report['summary'].items() if status != 'confirmed'
        ) else 1
    except KeyboardInterrupt:
        print('已停止；请使用原清单和原报告恢复，执行前会重新核对服务器当前值。')
        return 130
    except (ValueError, FileExistsError) as error:
        print(f'操作未完成：{error}')
        return 1
    except Exception as error:
        # Do not expose credentials or server response bodies through CLI exception details.
        print(f'操作未完成（{type(error).__name__}）；检查服务器、清单与报告，未确认的写入不能视为成功。')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
