"""
视频克隆对话框
"""

import sys
from pathlib import Path
import os
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QFileDialog, QLabel, QFormLayout, QWidget
from PyQt5.QtGui import QDragEnterEvent, QDropEvent
from qfluentwidgets import (
    TitleLabel, TextEdit, PushButton, BodyLabel, CardWidget, InfoBar, InfoBarPosition, ProgressBar,
    ComboBox, RadioButton
)

from threads.video_analysis_thread import VideoAnalysisThread
from database_manager import db_manager
from utils.file_utils import format_file_size

class DragDropVideoWidget(TextEdit):
    """支持拖拽的视频文件区域"""
    files_dropped = pyqtSignal(list)  # 添加文件拖拽信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setPlaceholderText("拖拽视频文件到这里\n支持 .mp4, .avi, .mov, .mkv, .wmv, .flv, .webm, .m4v 等格式")
        self.setReadOnly(True)
        
    def dragEnterEvent(self, e):  # type: ignore
        """拖拽进入事件"""
        if e is not None and hasattr(e, 'mimeData'):
            mime_data = e.mimeData()
            if mime_data is not None and hasattr(mime_data, 'hasUrls') and mime_data.hasUrls():
                if hasattr(mime_data, 'urls'):
                    urls = mime_data.urls()
                    for url in urls:
                        if url.isLocalFile():
                            file_path = url.toLocalFile()
                            if self.is_video_file(file_path):
                                e.acceptProposedAction()
                                return
        if e is not None:
            e.ignore()
            
    def dragMoveEvent(self, e):  # type: ignore
        """拖拽移动事件"""
        if e is not None and hasattr(e, 'mimeData'):
            mime_data = e.mimeData()
            if mime_data is not None and hasattr(mime_data, 'hasUrls') and mime_data.hasUrls():
                e.acceptProposedAction()
        elif e is not None:
            e.ignore()

    def dropEvent(self, e):  # type: ignore
        """拖拽放下事件"""
        if e is None or not hasattr(e, 'mimeData'):
            return
        mime_data = e.mimeData()
        if mime_data is None or not hasattr(mime_data, 'urls'):
            return
        urls = mime_data.urls()
        video_files = []

        for url in urls:
            if url.isLocalFile():
                file_path = url.toLocalFile()
                if self.is_video_file(file_path):
                    video_files.append(file_path)

        if video_files:
            self.files_dropped.emit(video_files)
            e.acceptProposedAction()
        elif e is not None:
            # 显示错误提示
            InfoBar.warning(
                title='提示',
                content='请选择视频文件（支持 .mp4, .avi, .mov, .mkv, .wmv, .flv, .webm, .m4v 格式）',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self.parent() if self.parent() else None
            )
            e.ignore()

    def is_video_file(self, file_path):
        """检查是否是视频文件"""
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
        return Path(file_path).suffix.lower() in video_extensions

class VideoCloneDialog(QDialog):
    """视频克隆对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.video_path = None
        self.analysis_thread = None
        self.selected_duration = 10  # 默认10秒
        self.selected_aspect_ratio = "16:9"  # 默认横屏
        self.setWindowTitle("视频克隆")
        self.setModal(True)
        self.resize(500, 450)  # 增加高度以容纳新控件
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 标题
        title = TitleLabel("视频克隆")
        layout.addWidget(title)
        
        # 说明文本
        description = BodyLabel("拖拽视频文件到下方区域进行分析，分析结果将自动复制到剪切板")
        description.setStyleSheet("color: #666; font-size: 13px;")
        layout.addWidget(description)
        
        # 视频拖拽区域
        video_card = CardWidget()
        video_layout = QVBoxLayout(video_card)
        
        video_title = BodyLabel("拖拽视频文件到这里")
        video_title.setStyleSheet("font-weight: bold;")
        video_layout.addWidget(video_title)
        
        # 拖拽区域
        self.drop_area = DragDropVideoWidget(self)
        self.drop_area.setFixedHeight(120)
        self.drop_area.files_dropped.connect(self.handle_dropped_files)  # 连接信号
        video_layout.addWidget(self.drop_area)
        
        # 浏览按钮
        self.browse_btn = PushButton("浏览视频文件")
        self.browse_btn.clicked.connect(self.browse_video_file)
        video_layout.addWidget(self.browse_btn)
        
        layout.addWidget(video_card)
        
        # 参数设置区域
        settings_card = CardWidget()
        settings_layout = QFormLayout(settings_card)
        settings_layout.setLabelAlignment(Qt.AlignRight)  # type: ignore
        settings_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)  # type: ignore
        
        # 分辨率选择
        self.resolution_combo = ComboBox()
        self.resolution_combo.addItem("横屏 (16:9)", "16:9")
        self.resolution_combo.addItem("竖屏 (9:16)", "9:16")
        self.resolution_combo.setCurrentIndex(0)  # 默认横屏
        settings_layout.addRow("分辨率:", self.resolution_combo)
        
        # 时长选择 - 单选框
        self.duration_group = QWidget()
        duration_layout = QHBoxLayout(self.duration_group)

        self.duration_10 = RadioButton("10秒")
        self.duration_10.setChecked(True)
        self.duration_10.toggled.connect(lambda checked: self.set_duration(10) if checked else None)

        self.duration_15 = RadioButton("15秒")
        self.duration_15.toggled.connect(lambda checked: self.set_duration(15) if checked else None)

        duration_layout.addWidget(self.duration_10)
        duration_layout.addWidget(self.duration_15)
        duration_layout.addStretch()

        settings_layout.addRow("时长(秒):", self.duration_group)
        
        layout.addWidget(settings_card)
        
        # 加载状态区域
        self.loading_widget = CardWidget()
        self.loading_widget.setVisible(False)  # 默认隐藏
        loading_layout = QVBoxLayout(self.loading_widget)
        
        loading_title = BodyLabel("正在处理视频...")
        loading_title.setStyleSheet("font-weight: bold;")
        loading_layout.addWidget(loading_title)
        
        # 进度条
        self.progress_bar = ProgressBar()
        self.progress_bar.setRange(0, 0)  # 设置为不确定模式
        loading_layout.addWidget(self.progress_bar)
        
        # 进度文本
        self.progress_label = BodyLabel("准备中...")
        self.progress_label.setStyleSheet("color: #666; font-size: 12px;")
        loading_layout.addWidget(self.progress_label)
        
        layout.addWidget(self.loading_widget)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = PushButton("关闭")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
    def set_duration(self, duration):
        """设置时长"""
        self.selected_duration = duration

    def handle_dropped_files(self, file_paths):
        """处理拖拽的文件"""
        if not file_paths:
            return
            
        # 只处理第一个视频文件
        file_path = file_paths[0]
        
        # 检查文件大小
        if not self.check_file_size(file_path):
            return
            
        self.video_path = file_path
        file_size = os.path.getsize(file_path)
        self.drop_area.setText(f"已选择视频文件:\n{Path(file_path).name}\n\n路径: {file_path}\n大小: {format_file_size(file_size)}")
        # 自动开始分析
        self.start_analysis()
        
    def check_file_size(self, file_path):
        """检查视频文件大小"""
        try:
            file_size = os.path.getsize(file_path)
            # 20MB = 20 * 1024 * 1024 bytes
            max_size = 20 * 1024 * 1024
            
            if file_size > max_size:
                InfoBar.error(
                    title='文件过大',
                    content=f'视频文件大小为 {format_file_size(file_size)}，超过20MB限制',
                    orient=Qt.Horizontal,  # type: ignore
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return False
            return True
        except Exception as e:
            InfoBar.error(
                title='错误',
                content=f'检查文件大小失败: {str(e)}',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return False
        
    def browse_video_file(self):
        """浏览选择视频文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择视频文件",
            str(Path.home()),
            "视频文件 (*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm *.m4v)"
        )
        
        if file_path:
            # 检查文件大小
            if not self.check_file_size(file_path):
                return
                
            self.video_path = file_path
            file_size = os.path.getsize(file_path)
            self.drop_area.setText(f"已选择视频文件:\n{Path(file_path).name}\n\n路径: {file_path}\n大小: {format_file_size(file_size)}")
            # 自动开始分析
            self.start_analysis()
            
    def start_analysis(self):
        """开始分析视频"""
        # 检查视频文件
        if not self.video_path:
            InfoBar.warning(
                title='提示',
                content='请先选择视频文件',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return
            
        # 从设置中获取API Key
        api_key = db_manager.load_config('api_key', '')
        if not api_key:
            InfoBar.warning(
                title='提示',
                content='请先在设置中配置API Key',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
            
        # 获取选择的参数
        self.selected_aspect_ratio = self.resolution_combo.currentData()
            
        # 显示加载状态
        self.show_loading_state()
            
        # 创建分析线程
        self.analysis_thread = VideoAnalysisThread(
            self.video_path,
            api_key
        )
        self.analysis_thread.progress.connect(self.on_analysis_progress)
        self.analysis_thread.result.connect(self.on_analysis_result)
        self.analysis_thread.error.connect(self.on_analysis_error)
        self.analysis_thread.start()
        
    def show_loading_state(self):
        """显示加载状态"""
        # 禁用操作按钮
        self.browse_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.drop_area.setReadOnly(True)
        self.resolution_combo.setEnabled(False)
        self.duration_10.setEnabled(False)
        self.duration_15.setEnabled(False)
        
        # 显示加载组件
        self.loading_widget.setVisible(True)
        self.progress_label.setText("准备中...")
        
    def hide_loading_state(self):
        """隐藏加载状态"""
        # 启用操作按钮
        self.browse_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        self.drop_area.setReadOnly(False)
        self.resolution_combo.setEnabled(True)
        self.duration_10.setEnabled(True)
        self.duration_15.setEnabled(True)
        
        # 隐藏加载组件
        self.loading_widget.setVisible(False)
        
    def on_analysis_progress(self, message):
        """分析进度更新"""
        self.progress_label.setText(message)
        
    def on_analysis_result(self, result):
        """分析结果回调"""
        # 隐藏加载状态
        self.hide_loading_state()
        
        # 处理结果
        if isinstance(result, list):
            result_text = ""
            for item in result:
                # 构建结果文本
                result_text += f"时间: {item.get('time', '')}\n"
                result_text += f"视频内容: {item.get('content', '')}\n"
                result_text += f"音频内容: {item.get('audio', '')}\n\n"
                
            # 复制到剪切板
            self.copy_to_clipboard(result_text)
                
            InfoBar.success(
                title='成功',
                content=f'视频分析完成，结果已复制到剪切板',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            
            # 分析完成之后自动创建任务
            self.create_task_from_analysis(result_text)
        else:
            InfoBar.warning(
                title='提示',
                content='分析完成但未返回有效结果',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            
    def create_task_from_analysis(self, analysis_result):
        """根据分析结果创建任务"""
        try:
            # 获取主窗口实例
            main_window = self.parent()
            while main_window and not callable(getattr(main_window, 'generate_video', None)):
                main_window = main_window.parent()
                
            if not main_window or not callable(getattr(main_window, 'generate_video', None)):
                InfoBar.warning(
                    title='提示',
                    content='无法获取主窗口实例，无法自动创建任务',
                    orient=Qt.Horizontal,  # type: ignore
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                # 分析完成之后自动关闭克隆弹窗
                self.accept()
                return
                
            # 构建任务数据
            task_data = {
                'prompt': analysis_result,
                'model': 'sora-2',
                'aspect_ratio': self.selected_aspect_ratio,
                'duration': self.selected_duration,
                'images': []  # 视频克隆不使用图片
            }
            
            # 调用主窗口的生成方法（使用getattr避免静态检查错误）
            generate_video_func = getattr(main_window, 'generate_video')
            generate_video_func(task_data)
            
            InfoBar.success(
                title='任务创建',
                content='已根据视频分析结果自动创建视频生成任务',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            
            # 分析完成之后自动关闭克隆弹窗
            self.accept()  # 使用accept()关闭对话框
            
        except Exception as e:
            InfoBar.error(
                title='错误',
                content=f'创建任务失败: {str(e)}',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            # 即使创建任务失败，也关闭对话框
            self.accept()
            
    def on_analysis_error(self, error_message):
        """分析错误回调"""
        # 隐藏加载状态
        self.hide_loading_state()
        
        # 显示错误信息
        InfoBar.error(
            title='错误',
            content=f'视频分析失败: {error_message}',
            orient=Qt.Horizontal,  # type: ignore
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )
        
    def copy_to_clipboard(self, text):
        """复制文本到剪切板"""
        try:
            from PyQt5.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(text)
        except Exception as e:
            print(f"复制到剪切板失败: {e}")