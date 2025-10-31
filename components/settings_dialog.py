"""
设置对话框
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QFormLayout
from qfluentwidgets import (
    TitleLabel, LineEdit, PushButton, PrimaryPushButton
)

from database_manager import db_manager

class SettingsDialog(QDialog):
    """设置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setModal(True)
        self.resize(400, 350)
        self.init_ui()
        self.load_settings()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 标题
        title = TitleLabel("应用设置")
        layout.addWidget(title)
        
        # 表单布局
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight)  # type: ignore
        form_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)  # type: ignore
        
        # API Key
        self.api_key_input = LineEdit()
        self.api_key_input.setPlaceholderText("请输入您的 Sora API Key")
        form_layout.addRow("API Key:", self.api_key_input)
        
        # ComfyUI服务器
        self.comfyui_server_input = LineEdit()
        self.comfyui_server_input.setPlaceholderText("请输入ComfyUI服务器地址，例如: http://localhost:8188")
        form_layout.addRow("ComfyUI服务器:", self.comfyui_server_input)
        
        # 视频保存路径
        self.video_path_input = LineEdit()
        self.video_path_input.setPlaceholderText("选择视频保存路径，留空则使用默认路径")
        form_layout.addRow("视频保存路径:", self.video_path_input)
        
        layout.addLayout(form_layout)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = PushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.save_btn = PrimaryPushButton("保存")
        self.save_btn.clicked.connect(self.save_and_close)
        button_layout.addWidget(self.save_btn)
        
        layout.addLayout(button_layout)
        
    def load_settings(self):
        """加载设置"""
        api_key = db_manager.load_config('api_key', '')
        self.api_key_input.setText(api_key)

        # 加载ComfyUI服务器地址
        comfyui_server = db_manager.load_config('comfyui_server', '')
        self.comfyui_server_input.setText(comfyui_server)

        # 加载视频保存路径
        video_path = db_manager.load_config('video_save_path', '')
        self.video_path_input.setText(video_path)
        
    def save_and_close(self):
        """保存设置并关闭"""
        api_key = self.api_key_input.text().strip()
        db_manager.save_config('api_key', api_key, 'string', 'Sora API Key')
        
        # 保存ComfyUI服务器设置
        comfyui_server = self.comfyui_server_input.text().strip()
        db_manager.save_config('comfyui_server', comfyui_server, 'string', 'ComfyUI服务器地址')
        
        # 保存视频保存路径
        video_path = self.video_path_input.text().strip()
        db_manager.save_config('video_save_path', video_path, 'string', '视频保存路径')
        
        self.accept()
        
    def save_comfyui_server(self):
        """实时保存ComfyUI服务器地址"""
        comfyui_server = self.comfyui_server_input.text().strip()
        db_manager.save_config('comfyui_server', comfyui_server, 'string', 'ComfyUI服务器地址')

        self.accept()
        
    def get_settings(self):
        """获取设置"""
        return {
            'api_key': self.api_key_input.text().strip(),
            'comfyui_server': self.comfyui_server_input.text().strip(),
            'video_save_path': self.video_path_input.text().strip()
        }