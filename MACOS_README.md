# macOS 版本使用说明

## 版本选择

本项目提供三个入口文件，根据您的需求选择：

### 1. Windows 版本 (main.py)
```bash
python main.py
```
- 完整功能（包括拖拽）
- 需要管理员权限创建软链接
- 适用于 Windows 系统

### 2. macOS tkinter 版本 (main_mac.py)
```bash
python main_mac.py
```
- 修复了 macOS 窗口最大化问题
- 无需管理员权限
- **不支持拖拽**（使用"浏览"按钮选择文件）

### 3. macOS PyQt5 版本 (qt_main.py) ⭐ 推荐
```bash
python qt_main.py
```
- **原生支持 macOS 拖拽**
- 支持单个/多个文件夹拖拽
- 现代化界面
- 无需管理员权限

## 安装依赖

```bash
# 基础依赖（所有版本都需要）
pip install pyyaml requests

# PyQt5 版本额外需要
pip install PyQt5
```

## 功能对比

| 功能 | Windows | macOS tkinter | macOS PyQt5 |
|------|---------|---------------|-------------|
| 窗口显示 | ✅ | ✅ | ✅ |
| 文件浏览 | ✅ | ✅ | ✅ |
| 拖拽功能 | ✅ | ❌ | ✅ |
| 软链接创建 | ✅ | ✅ | ✅ |
| 目录树镜像 | ✅ | ✅ | ✅ |

## 常见问题

### Q: 为什么 macOS 上 tkinter 版本不支持拖拽？
A: tkinterdnd2 库在 macOS 上与 Tcl/Tk 9.0 不兼容。请使用 PyQt5 版本获得拖拽支持。

### Q: PyQt5 版本和 tkinter 版本配置互通吗？
A: 是的，两个版本使用相同的 `config.yaml` 配置文件。

### Q: macOS 上创建软链接需要管理员权限吗？
A: 不需要。macOS 上普通用户即可创建软链接。

## 技术细节

### 代码结构
```
Emby115Toolkit/
├── main.py              # Windows 版本入口
├── main_mac.py          # macOS tkinter 版本入口
├── qt_main.py           # macOS PyQt5 版本入口
├── qt_gui/              # PyQt5 界面模块
│   ├── main_window.py
│   ├── export_tab.py    # 导出软链接（支持拖拽）
│   ├── folder_tab.py    # 文件夹操作（支持拖拽）
│   ├── duplicate_tab.py # Emby查重（支持拖拽）
│   ├── merge_tab.py     # 文件合并（支持拖拽）
│   ├── mirror_tab.py    # 目录树镜像（支持拖拽）
│   └── ...
└── tabs/                # tkinter 界面模块（Windows/macOS tkinter 共用）
```

### 合并策略
- `main.py`: 保持 Windows 版本完整不变
- `main_mac.py`: macOS 专用 tkinter 版本（修复兼容性）
- `qt_main.py` + `qt_gui/`: 独立的 PyQt5 模块（不影响原有代码）

这种设计确保：
1. Windows 用户无感知，继续使用 `main.py`
2. macOS 用户可选择 `main_mac.py` 或 `qt_main.py`
3. 代码完全隔离，无冲突风险
