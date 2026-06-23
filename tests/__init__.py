"""
测试包初始化文件
"""
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 的最前面
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
else:
    # 如果已在 path 中，确保它在最前面
    sys.path.remove(project_root)
    sys.path.insert(0, project_root)
