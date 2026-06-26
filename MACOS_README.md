# macOS 版本使用说明

## 版本选择

macOS 只支持 PyQt5 版本入口：

```bash
python macos_main.py
```
- **原生支持 macOS 拖拽**
- 支持单个/多个文件夹拖拽
- 现代化界面
- 无需管理员权限
- 修复窗口最大化问题

请不要在 macOS 上运行 `python windows_main.py`。`windows_main.py` 是 Windows tkinter 入口，macOS 上会直接提示改用 `macos_main.py` 并退出。

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用 uv 运行（推荐）

如果你使用 `uv`，可直接用一套命令完成环境搭建与启动（macOS 下兼容）：

```bash
# 仅首次执行：安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 在项目内创建/重建虚拟环境（如需）
cd /Users/wiz/dev/Emby115Toolkit
uv venv .venv --clear
source .venv/bin/activate

# 安装项目依赖
uv pip install -r requirements.txt

# 启动 macOS 入口
uv run macos_main.py
```

若临时希望免环境持久化，也可直接执行：

```bash
uv run --with PyQt5 macos_main.py
```

## 功能对比

| 功能 | Windows tkinter (windows_main.py) | macOS PyQt5 (macos_main.py) |
|------|-------------------|-------------------|
| 窗口显示 | ✅ | ✅ |
| 文件浏览 | ✅ | ✅ |
| **拖拽功能** | ✅ | ✅ **原生支持** |
| 软链接创建 | ✅ 需管理员 | ✅ 无需 |
| 目录树镜像 | ✅ | ✅ |

## 常见问题

### Q: macOS 上创建软链接需要管理员权限吗？
A: 不需要。macOS 上普通用户即可创建软链接。

### Q: 为什么使用 PyQt5 而不是 tkinter？
A: tkinterdnd2 库在 macOS 上与 Tcl/Tk 9.0 不兼容，无法稳定实现拖拽功能。为避免维护两个 macOS GUI 版本，macOS 只保留 PyQt5 入口。

### Q: PyQt5 版本和 Windows 版本配置互通吗？
A: 是的，两个版本使用相同的 `config.yaml` 配置文件。

## 技术细节

### 代码结构
```
Emby115Toolkit/
├── windows_main.py              # Windows tkinter 版本入口
├── macos_main.py                # macOS PyQt5 版本入口
├── macos_gui/                   # macOS PyQt5 界面模块
│   ├── main_window.py
│   ├── symlink_export_tab.py    # 导出软链接（支持拖拽）
│   ├── folder_tools_tab.py      # 文件夹操作（支持拖拽）
│   ├── file_merge_tab.py        # 文件合并（支持拖拽）
│   ├── tree_mirror_tab.py       # 目录树镜像（支持拖拽）
│   └── ...
├── windows_gui/                 # tkinter 界面模块（Windows 专用）
├── services/                    # 共享业务逻辑
├── media_server/                # Emby/Jellyfin 集成
└── utils/                       # 配置、日志、通用工具
```

### 设计原则
- `windows_main.py`: 保持 Windows tkinter 版本完整，不支持 macOS 或 Linux
- `macos_main.py` + `macos_gui/`: 独立的 PyQt5 模块，专用于 macOS
- macOS 不再维护 tkinter 版本，避免使用和维护上的混淆
- Linux 不再支持，避免维护第三套平台差异
