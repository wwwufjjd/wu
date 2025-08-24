import sys
import os

# 尝试在 QApplication 初始化前设置环境变量，以选择更兼容的媒体后端
# 这对于解决在某些 Windows 系统上因缺少解码器而无法播放视频的问题特别有用
os.environ['QT_MULTIMEDIA_PREFERRED_PLUGINS'] = 'windowsmediafoundation'

from PyQt5.QtWidgets import QApplication
from gui.main_window import MainWindow

def main():
    """
    应用程序主入口
    """
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()