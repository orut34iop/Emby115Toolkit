# Jellyfin 历史字段补锁与已合并副版本

更新日期：2026-10-19。英文版：[Historical Jellyfin field protection and merged versions](metadata-protection.md)。

此流程保护**数据库当前值**，包括中文值、未知值和明确保留的空列表。不翻译、不恢复旧值、不读取 NFO 元数据、不刷新媒体库，也不合并／拆分版本。预览只读，执行经审阅清单是独立的明确命令；安装和测试不会修改真实媒体库。

## 范围与版本发现

必须选择条目 ID **或**媒体库 ID，并明确指定 `Genres`、`ProductionLocations` 或两者。ID 为 Jellyfin GUID；没有隐式全库模式，也不凭中文文本推断已人工整理。

- 条目范围包含选定条目及其 `MediaSources` 公布的所有版本。选中 Series ID 不会隐式包含其季和单集。
- 媒体库范围递归选取 Movie、Series、Season、Episode、Video，再展开对应版本；不保护无关音频、照片、人物实体。
- 发现过程逐项读取完整详情，沿媒体源条目 ID 继续展开并去重，能处理循环关系。不调用 PlaybackInfo 或 ffprobe。每个成员保留自身值，不复制主版本元数据给副版本。
- 已合并组可能跨媒体库。即使副版本不显示在所选库的普通列表中，也会纳入预览；执行前必须审阅其 ID、类型、路径及跨库范围。
- 成员缺失、不可读、类型不支持、源 ID 不是 GUID，或源数量大于已发现成员数时，中止预览，不生成可执行的残缺清单。不具备持久条目 ID 的提供者特殊源需要另行适配。

桌面现有“更新流派”和“更新地区”也会请求 `MediaSources`，在筛选翻译候选之前展开已合并版本。任一成员发现失败，本轮 Movie／Series 更新不会开始写入。这两个操作仍只翻译实际变化的值，保持原有 Movie／Series 范围；独立历史补锁流程才覆盖无需翻译的值、已有空列表以及季和单集。

## 预览、审阅、执行

在工具项目目录使用其 Python 环境执行。macOS 通常使用 `.venv/bin/python`，Windows 使用已配置环境的 `python`。本次不改变 GUI，不新增前端。

通过进程环境变量 `JELLYFIN_API_KEY` 提供 API Key，不放入命令参数、清单或报告。使用有权读取和编辑目标条目的账户／Key。服务器经过反向代理时，`--server-url` 应包含基础路径。

先创建私有输出目录 `metadata-protection`（已加入 gitignore），再生成预览。以下示例为虚构服务器和占位 ID，需要有意替换：

```sh
python -m media_server.metadata_protection_cli --server-url https://media.example/jellyfin --username Admin plan --library-id LIBRARY_GUID --fields Genres ProductionLocations --output metadata-protection/library-plan.json
```

明确选择条目时，将 `--library-id LIBRARY_GUID` 替换为 `--item-id ITEM_GUID`。两种选项均可重复来指定多个 ID，但不能混用。示例明确选择两个字段；只补流派锁则写 `--fields Genres`。

预览包含服务器 URL／ID、用户范围、所选根节点、展开后的成员 ID 和关系、身份信息、选定字段当前值、已有字段锁及整项锁状态。执行前审阅每一项，特别是隐藏或跨库成员。已存在的预览文件绝不覆盖。此文件是相关字段值和锁的备份，**不是**完整 Jellyfin 数据库备份或自动回滚脚本；需要时另行备份数据库。

审阅后才明确执行：

```sh
python -m media_server.metadata_protection_cli --server-url https://media.example/jellyfin --username Admin apply --plan metadata-protection/library-plan.json --report metadata-protection/library-report.json
```

执行会拒绝不同服务器 ID、URL 或用户范围。逐项重新读取完整当前详情，对照预览检查身份、版本关系和选定字段值；先把当前值及锁写入报告作为写入前备份，再用当前完整 DTO **仅增加 `LockedFields`**。保留非选定字段的当前值、已有锁及 `LockData`；绝不把预览中的旧值覆盖回数据库。

现有完整 DTO 接口没有条件修订号，重新读取到 POST 之间仍可能与其他写入者竞争；请避免同时管理相同条目。备份和重读可降低风险，不等于跨客户端事务。NFO 保存仍服从服务器现有媒体库配置。

## 验证、失败和重试

| 报告最新状态 | 含义与下一步 |
| --- | --- |
| `confirmed` | 已回读确认当前值和全部提交锁；或经过核对的当前条目原本就具备选定锁。 |
| `failed` | 读取、写入或校验失败；检查条目后，使用**同一清单和同一报告**再次执行。 |
| `conflict` | 选定值、身份、版本成员变化，或曾确认成功后锁被移除；审阅新状态并重新预览，不自动恢复旧值。 |
| `prepared` | 已有写入前备份，但完成确认被中断；用原文件恢复，通过回读判断是否还需写入。 |
| `unprocessed` 计数 | 取消后尚未处理的条目；使用原文件继续。 |

普通超时不会盲目重发旧的完整 DTO。重试会再次读取当前值和锁，保留新出现的无关元数据及锁，并验证结果。已确认项会重新核对，但不重复 POST；如果用户后来明确解锁，报告冲突，不悄悄重新锁定。报告保留每次尝试历史，通过 SHA-256 绑定清单原始内容；恢复期间不要修改预览，也不要改用新报告来绕过历史。

备份及报告检查点先落盘再发送 HTTP 写入，检查点写入失败即停止。文件以原子替换方式保存，在支持的平台创建为私有权限；Windows 还应配置私有目录 ACL。文件包含私人元数据和路径，不要发布。操作系统文件锁阻止同一预览文件被同时执行，进程退出／崩溃会释放锁；不同清单或其他客户端不受此锁协调。

退出码 0 表示全部选定条目已确认。非零表示失败、冲突、取消或未完成，应检查报告。Ctrl+C 会停止；正在发送的请求可能已提交，因此恢复应回读，不能假设已回滚。整批不是整库事务；服务器跨仓储断电原子性，以及恢复已被覆盖的旧值，不在此流程内。

## 验证记录

自动测试覆盖隐藏成员、循环关系、独立值、已有空值、明确范围、已有锁及无关字段当前值保留、值／源变化冲突、部分失败、中断检查点、取消恢复、写入前本地备份失败。HTTP 契约测试覆盖两套受支持的接口快照。不使用用户真实媒体库。

2026-10-19 验证：`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest` **384 项通过**，1 项 Windows 专属界面测试在 macOS 跳过；受影响文件的 `ruff check` 通过。环境仍有既有 urllib3／LibreSSL 警告。

独立 Jellyfin `12.0.0-20261019183458` 实例通过五组验证：① CLI 预览不写服务器，并找到普通列表隐藏的成员；② 保留独立历史值和空值、范围外条目不变、模拟部分失败后恢复及重复执行；③ 完成替换全部刷新及请求 PlaybackInfo 后，两个成员的受保护值仍保留；④ 日常流派／地区更新分别翻译隐藏成员；⑤ 旧预览检测冲突，不恢复旧值。只使用生成的测试电影。系列／季／单集范围及整项锁保留有自动测试覆盖，未进行实际服务器联调；未在 Windows 原生环境执行 CLI／文件锁，也未运行未修改的官方服务器版本。
