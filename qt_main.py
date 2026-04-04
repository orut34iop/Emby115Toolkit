#!/usr/bin/env python3
"""
PyQt5 版本启动入口
提供原生 macOS 拖拽支持
"""

import sys
import os

# 确保可以导入项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """主函数"""
    try:
        from PyQt5.QtWidgets import QApplication
        from qt_gui.main_window import MainWindow

        app = QApplication(sys.argv)
        app.setStyle('Fusion')

        # 设置应用信息
        app.setApplicationName("Emby115Toolkit")
        app.setApplicationDisplayName("Emby115Toolkit - PyQt5")

        window = MainWindow()
        window.show()

        sys.exit(app.exec_())

    except ImportError as e:
        print(f"错误: 无法导入 PyQt5 模块: {e}")
        print("\n请安装 PyQt5:")
        print("  pip install PyQt5")
        sys.exit(1)

if __name__ == '__main__':
    main()
