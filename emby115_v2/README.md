# Emby115Toolkit V2

V2 是面向 115 云盘 + CloudDrive2 + Emby 工作流的 WebUI / CLI 自动化版本。后续 `emby115_v2` 目录会作为独立仓库维护。

## 安装

```bash
cd emby115_v2
pip install -r requirements.txt
```

## 运行

启动 WebUI：

```bash
python main.py --serve-web
```

一键启动本地 WebUI：

```bash
scripts/start_webui.bat
./scripts/start_webui.sh
```

运行 CLI 动作：

```bash
python main.py --action build_symlink_workspace --dry-run
```

非 localhost 监听必须设置访问令牌：

```bash
python main.py --serve-web --host 0.0.0.0 --access-token YOUR_TOKEN
```

## 测试

```bash
pytest
```

更多架构和动作说明见 [docs/项目概述.md](docs/项目概述.md) 和 [docs/V2_CHECKPOINT.md](docs/V2_CHECKPOINT.md)。
