"""
图片显示控件
"""

import sys
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtGui import QPixmap

class ImageWidget(QWidget):
    """图片显示控件"""
    def __init__(self, image_url=None, parent=None, size: int = 100):
        super().__init__(parent)
        self.image_url = image_url
        self.pixmap = None
        self._size = max(60, int(size))
        self.setFixedSize(self._size, self._size)
        self.init_ui()

    def init_ui(self):
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(5, 5, 5, 5)

        self.image_label = QLabel()
        inner = max(40, self._size - 10)
        self.image_label.setFixedSize(inner, inner)
        self.image_label.setAlignment(Qt.AlignCenter)  # type: ignore
        self.image_label.setStyleSheet("border: 1px solid #ddd; border-radius: 4px; background-color: #f9f9f9;")
        self._layout.addWidget(self.image_label)

        # 显示占位符
        self.show_placeholder()

    def show_placeholder(self):
        """显示占位符"""
        self.image_label.setText("无图片")
        self.image_label.setStyleSheet("border: 1px solid #ddd; border-radius: 4px; background-color: #f9f9f9; color: #999;")

    def set_image(self, image_url, pixmap=None):
        """设置图片"""
        self.image_url = image_url
        if pixmap:
            self.pixmap = pixmap
            # 缩放图片以适应标签大小
            target_w = self.image_label.width()
            target_h = self.image_label.height()
            scaled_pixmap = pixmap.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)  # type: ignore
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.setText("")
            self.image_label.setStyleSheet("border: 1px solid #ddd; border-radius: 4px; background-color: white;")
        else:
            self.show_placeholder()

    def get_image_url(self):
        """获取图片URL"""
        return self.image_url
