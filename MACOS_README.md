# macOS 版本使用说明

## 版本选择

本项目提供两个入口文件，根据您的系统选择：

### 1. Windows 版本 (main.py)
```bash
python main.py
```
- 完整功能（包括拖拽）
- 需要管理员权限创建软链接
- 适用于 Windows 系统

### 2. macOS PyQt5 版本 (qt_main.py) ⭐ 推荐
```bash
python qt_main.py
```
- **原生支持 macOS 拖拽**
- 支持单个/多个文件夹拖拽
- 现代化界面
- 无需管理员权限
- 修复窗口最大化问题

## 安装依赖

```bash
# 基础依赖
pip install pyyaml requests

# PyQt5 版本需要
pip install PyQt5
```

## 功能对比

| 功能 | Windows (main.py) | macOS (qt_main.py) |
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
A: tkinterdnd2 库在 macOS 上与 Tcl/Tk 9.0 不兼容，无法实现拖拽功能。PyQt5 原生支持 macOS 拖拽。

### Q: PyQt5 版本和 Windows 版本配置互通吗？
A: 是的，两个版本使用相同的 `config.yaml` 配置文件。

## 技术细节

### 代码结构
```
Emby115Toolkit/
├── main.py              # Windows 版本入口
├── qt_main.py           # macOS PyQt5 版本入口 ⭐
├── qt_gui/              # PyQt5 界面模块
│   ├── main_window.py
│   ├── export_tab.py    # 导出软链接（支持拖拽）
│   ├── folder_tab.py    # 文件夹操作（支持拖拽）
│   ├── duplicate_tab.py # Emby查重（支持拖拽）
│   ├── merge_tab.py     # 文件合并（支持拖拽）
│   ├── mirror_tab.py    # 目录树镜像（支持拖拽）
│   └── ...
└── tabs/                # tkinter 界面模块（Windows 专用）
```

### 设计原则
- `main.py`: 保持 Windows 版本完整不变
- `qt_main.py` + `qt_gui/`: 独立的 PyQt5 模块，专用于 macOS
- 代码完全隔离，无冲突风险
