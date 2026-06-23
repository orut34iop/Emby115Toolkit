"""
测试包初始化文件
"""
import sys
from pathlib import Path

# 确保当前目录独立成仓库后仍可按 emby115_v2 包名导入
project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)
else:
    # 如果已在 path 中，确保它在最前面
    sys.path.remove(project_root)
    sys.path.insert(0, project_root)
