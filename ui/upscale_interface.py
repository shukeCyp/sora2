"""
高清放大界面
"""

from pathlib import Path
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QDialog
from qfluentwidgets import (
    PushButton, PrimaryPushButton, TitleLabel, BodyLabel, TableWidget
)

from components.upscale_settings_dialog import UpscaleSettingsDialog
from components.upscale_servers_dialog import UpscaleServersDialog
from threads.video_upscale_thread import VideoUpscaleThread
from database_manager import db_manager

class UpscaleInterface(QWidget):
    """高清放大界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("upscaleInterface")
        self.video_files = []  # 存储导入的视频文件路径
        self.current_thread = None  # 当前处理线程
        self.is_processing = False  # 处理状态标志
        self.current_index = 0  # 当前处理的视频索引
        self.mode = 'tiny'  # 默认模式改为tiny
        self.scale = 2  # 默认放大系数
        # 并发调度相关
        self.pending_indices = []
        self.running_workers = 0
        self.active_threads = []
        self.enabled_servers = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 控制按钮区域
        control_layout = QHBoxLayout()
        
        # 导入视频文件夹按钮
        self.import_btn = PushButton('导入视频文件夹')
        self.import_btn.clicked.connect(self.import_video_folder)
        control_layout.addWidget(self.import_btn)
        
        # 设置按钮
        self.settings_btn = PushButton('设置')
        self.settings_btn.clicked.connect(self.show_upscale_settings)
        control_layout.addWidget(self.settings_btn)
        
        # 服务器配置按钮
        self.server_btn = PushButton('服务器配置')
        self.server_btn.clicked.connect(self.show_server_config)
        control_layout.addWidget(self.server_btn)
        
        # 开始处理按钮
        self.process_btn = PrimaryPushButton('开始处理')
        self.process_btn.clicked.connect(self.start_processing)
        self.process_btn.setEnabled(False)  # 初始禁用，直到导入视频
        control_layout.addWidget(self.process_btn)
        
        # 停止按钮
        self.stop_btn = PushButton('停止处理')
        self.stop_btn.clicked.connect(self.stop_processing)
        self.stop_btn.setEnabled(False)
        control_layout.addWidget(self.stop_btn)
        
        control_layout.addStretch()
        layout.addLayout(control_layout)
        
        # 视频文件表格
        self.video_table = TableWidget()
        self.setup_video_table()
        layout.addWidget(self.video_table)
        
        # 状态标签
        self.status_label = BodyLabel("请先导入视频文件夹")
        self.status_label.setStyleSheet("color: #666; font-size: 13px;")
        layout.addWidget(self.status_label)

    def setup_video_table(self):
        """设置视频表格"""
        # 设置表格列
        headers = ['文件名', '状态', '大小', '路径']
        self.video_table.setColumnCount(len(headers))
        self.video_table.setHorizontalHeaderLabels(headers)
        self.video_table.setRowCount(0)

        # 设置列宽
        self.video_table.setColumnWidth(0, 200)  # 文件名
        self.video_table.setColumnWidth(1, 100)  # 状态
        self.video_table.setColumnWidth(2, 100)  # 大小
        self.video_table.setColumnWidth(3, 300)  # 路径

        # 设置表格属性
        self.video_table.setAlternatingRowColors(True)
        vertical_header = self.video_table.verticalHeader()
        if vertical_header:
            vertical_header.setVisible(False)
        horizontal_header = self.video_table.horizontalHeader()
        if horizontal_header:
            horizontal_header.setStretchLastSection(True)
        
        # 禁止编辑
        from PyQt5.QtWidgets import QAbstractItemView
        self.video_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

    def import_video_folder(self):
        """导入视频文件夹"""
        folder_path = QFileDialog.getExistingDirectory(
            self, 
            "选择视频文件夹", 
            str(Path.home())
        )
        
        if not folder_path:
            return
            
        # 清空当前表格
        self.video_table.setRowCount(0)
        self.video_files = []
        
        # 查找视频文件
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv'}
        folder = Path(folder_path)
        
        for file_path in folder.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                self.video_files.append(str(file_path))
                
        # 填充表格
        self.video_table.setRowCount(len(self.video_files))
        for row, file_path in enumerate(self.video_files):
            path_obj = Path(file_path)
            
            from PyQt5.QtWidgets import QTableWidgetItem
            
            # 文件名
            name_item = QTableWidgetItem(path_obj.name)
            self.video_table.setItem(row, 0, name_item)
            
            # 状态
            status_item = QTableWidgetItem("待处理")
            status_item.setTextAlignment(Qt.AlignCenter)  # type: ignore
            self.video_table.setItem(row, 1, status_item)
            
            # 大小
            try:
                size = path_obj.stat().st_size
                size_str = self.format_file_size(size)
                size_item = QTableWidgetItem(size_str)
                size_item.setTextAlignment(Qt.AlignCenter)  # type: ignore
                self.video_table.setItem(row, 2, size_item)
            except:
                size_item = QTableWidgetItem("未知")
                size_item.setTextAlignment(Qt.AlignCenter)  # type: ignore
                self.video_table.setItem(row, 2, size_item)
            
            # 路径
            path_item = QTableWidgetItem(str(path_obj))
            self.video_table.setItem(row, 3, path_item)
                
        if self.video_files:
            self.status_label.setText(f"已导入 {len(self.video_files)} 个视频文件")
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.success(
                title='成功',
                content=f'成功导入 {len(self.video_files)} 个视频文件',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            self.process_btn.setEnabled(True)
        else:
            self.status_label.setText("未找到视频文件")
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.warning(
                title='提示',
                content='未在所选文件夹中找到视频文件',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            self.process_btn.setEnabled(False)

    def format_file_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"

    def show_upscale_settings(self):
        """显示高清放大设置对话框"""
        dialog = UpscaleSettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            settings = dialog.get_settings()
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.success(
                title='成功',
                content='高清放大设置已保存',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )

    def show_server_config(self):
        """显示高清放大服务器配置对话框"""
        dialog = UpscaleServersDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.success(
                title='成功',
                content='服务器配置已保存',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )

    def start_processing(self):
        """开始处理视频"""
        if not self.video_files:
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.warning(
                title='提示',
                content='请先导入视频文件',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return
            
        # 获取设置
        self.mode = db_manager.load_config('upscale_mode', 'tiny')  # 默认tiny
        self.scale = db_manager.load_config('upscale_scale', 2)
        # 获取启用的服务器列表
        self.enabled_servers = db_manager.get_upscale_servers(enabled_only=True)
        if not self.enabled_servers:
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.error(
                title='错误',
                content='请先在“服务器配置”中添加并启用至少一个服务器',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
            
        # 确认对话框
        from qfluentwidgets import MessageBox
        dialog = MessageBox(
            title='确认处理',
            content=f'确定要处理 {len(self.video_files)} 个视频文件吗？\n模式: {self.mode}\n放大系数: {self.scale}倍',
            parent=self
        )
        dialog.yesButton.setText('开始处理')
        dialog.cancelButton.setText('取消')
        
        if dialog.exec():
            # 设置处理状态
            self.is_processing = True
            
            # 更新按钮状态
            self.import_btn.setEnabled(False)
            self.settings_btn.setEnabled(False)
            self.server_btn.setEnabled(False)
            self.process_btn.setEnabled(False)
            self.process_btn.setText('处理中...')
            self.stop_btn.setEnabled(True)
            
            # 更新表格状态
            for row in range(self.video_table.rowCount()):
                status_item = self.video_table.item(row, 1)
                if status_item:
                    status_item.setText("待处理")
            
            # 初始化任务队列并启动并发处理
            self.pending_indices = list(range(len(self.video_files)))
            self.active_threads = []
            self.running_workers = 0

            # 根据启用的服务器并发启动任务
            for server in self.enabled_servers:
                if not self.pending_indices:
                    break
                self.start_next_for_server(server['url'])
                self.running_workers += 1

    def stop_processing(self):
        """停止处理"""
        if self.is_processing:
            # 确认停止
            from qfluentwidgets import MessageBox
            dialog = MessageBox(
                title='确认停止',
                content='确定要停止处理吗？已处理的文件将保留。',
                parent=self
            )
            dialog.yesButton.setText('停止处理')
            dialog.cancelButton.setText('继续处理')
            
            if dialog.exec():
                self.is_processing = False
                
                # 停止所有正在运行的线程
                try:
                    for t in list(self.active_threads):
                        if t.isRunning():
                            t.terminate()
                            t.wait()
                except Exception:
                    pass
                
                # 更新按钮状态
                self.import_btn.setEnabled(True)
                self.settings_btn.setEnabled(True)
                self.server_btn.setEnabled(True)
                self.process_btn.setEnabled(True)
                self.process_btn.setText('开始处理')
                self.stop_btn.setEnabled(False)
                
                # 更新状态标签
                self.status_label.setText("处理已停止")
                
                from qfluentwidgets import InfoBar, InfoBarPosition
                InfoBar.warning(
                    title='已停止',
                    content='视频处理已停止',
                    orient=Qt.Horizontal,  # type: ignore
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )

    def start_next_for_server(self, server_url: str):
        """为指定服务器启动下一个任务"""
        if not self.is_processing or not self.pending_indices:
            return

        index = self.pending_indices.pop(0)
        input_path = Path(self.video_files[index])
        # 默认命名（高清放大不使用AI标题）
        output_path = input_path.parent / f"{input_path.stem}-hd{input_path.suffix}"

        # 更新状态标签与表格
        self.status_label.setText(f"正在处理: {input_path.name}")
        status_item = self.video_table.item(index, 1)
        if status_item:
            status_item.setText("处理中")

        # 创建并启动线程
        t = VideoUpscaleThread(
            str(input_path),
            str(output_path),
            self.mode,
            self.scale,
            server_url
        )
        t.progress.connect(lambda message, idx=index: self.on_worker_progress(idx, message))
        t.finished.connect(lambda success, message, out, idx=index, srv=server_url, thread=t: self.on_worker_finished(idx, srv, success, message, out, thread))
        self.active_threads.append(t)
        t.start()

    def finish_processing(self):
        """完成处理"""
        self.is_processing = False
        
        # 更新按钮状态
        self.import_btn.setEnabled(True)
        self.settings_btn.setEnabled(True)
        self.server_btn.setEnabled(True)
        self.process_btn.setEnabled(True)
        self.process_btn.setText('开始处理')
        self.stop_btn.setEnabled(False)
        
        # 检查是否所有文件都已处理完成
        all_completed = True
        for row in range(self.video_table.rowCount()):
            status_item = self.video_table.item(row, 1)
            if status_item and status_item.text() not in ["已完成", "失败"]:
                all_completed = False
                break
        
        if all_completed:
            self.status_label.setText("所有视频处理完成")
            from qfluentwidgets import InfoBar, InfoBarPosition
            InfoBar.success(
                title='完成',
                content='所有视频高清放大处理完成',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
        else:
            self.status_label.setText("处理已停止")

    def on_worker_progress(self, row_index: int, message: str):
        """处理进度更新"""
        self.status_label.setText(message)

    def on_worker_finished(self, row_index: int, server_url: str, success: bool, message: str, output_path: str, thread: VideoUpscaleThread):
        """并发线程完成回调"""
        # 更新表格状态
        status_item = self.video_table.item(row_index, 1)
        if status_item:
            if success:
                status_item.setText("已完成")
            else:
                status_item.setText("失败")
                from qfluentwidgets import InfoBar, InfoBarPosition
                InfoBar.error(
                    title='处理失败',
                    content=f'{Path(self.video_files[row_index]).name}: {message}',
                    orient=Qt.Horizontal,  # type: ignore
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )

        # 清理线程引用
        try:
            if thread in self.active_threads:
                self.active_threads.remove(thread)
        except Exception:
            pass

        # 为该服务器继续启动下一项任务或结束处理
        if self.is_processing and self.pending_indices:
            self.start_next_for_server(server_url)
        else:
            # 该服务器不再有任务，减少活跃工作者计数
            self.running_workers = max(0, self.running_workers - 1)
            if self.running_workers == 0:
                self.finish_processing()
