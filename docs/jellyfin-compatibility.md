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
