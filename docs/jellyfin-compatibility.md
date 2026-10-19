# Jellyfin 10.11.11 / 12.0 兼容说明

Windows tkinter 和 macOS PyQt5 共用 `MediaServerClient`。选择 Jellyfin，填写服务地址、API Key 和用户名即可，代码自动读取服务端版本，不提供版本选择器。反向代理的基础路径应包含在服务地址中，例如 `https://media.example/jellyfin`。

两个版本使用相同的正式 API。12.0 的关键变化是默认禁用旧认证方式；因此所有 Jellyfin 请求统一使用 `Authorization: MediaBrowser Token="…"`，不发送旧 Token 请求头和 URL 中的 API Key，也不要求服务器开启旧认证。Emby 保留原有认证和路径。

| 操作 | 10.11.11 与 12.0 共用的接口 |
| --- | --- |
| 类型和版本识别 | `GET /System/Info/Public` |
| 用户查询 | `GET /Users` |
| 用户媒体库 | `GET /UserViews?UserId=…` |
| 条目查询 | `GET /Items?UserId=…&ParentId=…&IncludeItemTypes=…&Recursive=true` |
| 条目完整详情 | `GET /Items/{itemId}?UserId=…` |
| 元数据保存 | `POST /Items/{itemId}` |
| 影片版本合并 | `POST /Videos/MergeVersions?ids=…` |

条目读取使用分页和显式递归查询，不依赖不同版本对递归的默认处理。每页请求 500 条，根据实际返回数量及 `TotalRecordCount` 继续读取。中途失败、响应格式错误或重复分页时丢弃该列表的部分结果，避免用不完整的数据更新或合并。

`GenreItems` 不是 Jellyfin 的 `ItemFields` 参数值；请求 `Genres` 即可得到流派信息。保存元数据前读取完整详情，保留原有字段（包括 12.0 新增的 `OriginalLanguage`），仅移除不需要回传的 `GenreItems`。

流派和地区更新每次完整扫描，先比较现有值，再对需要修改的条目读取详情并保存。程序不再读写增量时间基线，也不发送时间下限过滤条件。加载配置时自动移除旧 `scan_mode` 和 `sync_state`，保留服务器连接、配置 ID、当前选择和其他设置。

## 中文化结果的字段保护

Jellyfin 的流派、地区中文化仅在本次值确实需要翻译或去重时保存：流派操作向 `LockedFields` 添加 `Genres`，地区操作添加 `ProductionLocations`。每次均从最新完整详情构造请求，保留原有字段锁、整项 `LockData` 和其他元数据，不因完整 DTO 中包含某字段就自动锁定该字段。未知锁名原样保留；锁格式异常时拒绝写入。Emby 的既有保存和重试行为不变。

流派归一化与地区一样丢弃空白值，避免发送 `[""]` 一类无效标签再被服务器清理，导致回读误判；这一归一化规则由 Emby/Jellyfin 共用。

保存后回读确认本次字段值和全部提交锁，只有确认一致才计为成功；受保护的空列表也必须由回读明确返回。响应超时或服务端暂时错误时，如果回读确认值和锁均已保存，按成功处理。否则报告结果未确认，不重发旧的完整 DTO，避免覆盖期间其他客户端提交的数据。失败条目名称和 ID 写入现有日志，汇总显示部分失败；需要检查服务器当前值和锁后再处理。若值已写入而锁缺失，再次中文化会跳过无需翻译的值，此时须明确补锁，不能把再次执行当成自动恢复锁的保证。

此保护用于后续扫描和“替换全部元数据”，不会阻止有权限的用户再次编辑。它需要服务器正确执行字段锁；本地 Jellyfin 修复同时隔离播放和字幕维护的描述更新。不能仅凭工具加锁就宣称任意旧版服务器的锁绕过问题已修复。

已有中文值、未知未翻译值和空值不会仅因出现在扫描中就自动加锁，也不修改真实媒体库作为安装步骤。历史中文化结果需先导出备份、明确需保护的条目，再补充对应锁；已被覆盖的数据需从备份或重新整理恢复。

版本合并只调整关系，不复制或合并成员的流派、地区、锁。建议在尚未合并时，先分别完成所有成员的流派、地区更新并确认无失败，再执行版本合并。列表可能隐藏已合并的副版本，当前扫描不保证枚举这些隐藏成员；其保护需要按实际成员 ID 单独处理，不能由主版本更新成功推断。普通剧集更新处理 Series 条目，不保证逐集或逐季字段已同步。流派与地区是两个操作，整库处理也不是一个事务。

完整 DTO API 没有修订号条件写入，读取详情至提交之间仍可能与其他管理工具竞争。批量整理时应避免并行编辑相同条目；本次修改不宣称解决跨客户端的全部并发冲突。

## 核对依据

- 官方源码固定标签：[v10.11.11](https://github.com/jellyfin/jellyfin/tree/v10.11.11)（`1fbd8739292cce610231be93daf43368733edf63`）和 [v12.0](https://github.com/jellyfin/jellyfin/tree/v12.0)（`6c073e19ddf604b2369c638716164fdab4c952dc`）。核对了认证解析、Items、UserViews、UserLibrary、ItemUpdate、Videos 控制器以及字段枚举。
- 官方 [10.11.11 OpenAPI](https://repo.jellyfin.org/files/openapi/stable/jellyfin-openapi-10.11.11.json) 和 [12.0 OpenAPI](https://repo.jellyfin.org/files/openapi/stable/jellyfin-openapi-12.0.json)。12.0 文档中的服务端版本字段为 `12.0.0`，工具无需把它转换为三段或两段版本。
- [12.0 发布说明](https://jellyfin.org/posts/jellyfin-release-12.0/)与[认证迁移说明](https://github.com/jellyfin/jellyfin/pull/13306)。

## 回归验证

`tests/fixtures/jellyfin/` 保存两个官方 OpenAPI 文档的精简快照：接口、参数名、成功状态、认证头、字段枚举和条目属性。每份快照包含来源 URL 与原始 JSON 文件的 SHA-256；测试无需联网或访问用户媒体库。

`tests/integration/test_jellyfin_api_contracts.py` 对两个快照分别运行真实本地 HTTP 请求，验证基础路径、认证、分页、用户范围、查重、影片合并，以及电影和剧集的流派、地区更新。HTTP 服务端是测试替身；这不等同于在两套实际 Jellyfin 服务器上完成联调。

单元测试还覆盖版本识别、Emby 回归、每次完整扫描、旧配置清理、取消、异常分页和请求失败。Windows CI 运行原生 tkinter 工作流及媒体 API 回归；macOS 使用 PyQt5 工作流测试。

```shell
python -m pytest
```

### 2026-10-19 字段保护验证

- 修改前，新增的四个流派／地区 HTTP 契约用例均因缺少字段锁失败；修改后通过。
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest`：361 项通过、1 项 Windows 专属测试在 macOS 跳过。当前 Python 环境另有既有 urllib3／LibreSSL 兼容警告。
- `.venv/bin/python -m ruff check media_server/client.py tests/unit/media_server/test_curated_field_protection.py tests/unit/media_server/test_client.py tests/integration/test_jellyfin_api_contracts.py`：通过。
- 独立 Jellyfin `12.0.0-20261019183458` 测试实例中，使用三个生成的视频实际调用工具的流派／地区更新和版本合并，再调用服务器替换全部刷新、PlaybackInfo 并回读：中文值及既有、新增锁均保留；共用保存路径提交的空地区值也经刷新保留。
- 真实实例验证只覆盖测试电影；Series 由 HTTP 契约替身覆盖。未操作用户真实媒体库，未验证实际图形播放器、Windows 原生界面或官方 10.11.11／12.0 服务端运行环境。两套 OpenAPI 契约测试不能替代后者。
