"""
任务列表界面 - 重新实现
"""

import os
from pathlib import Path
from datetime import datetime
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QAbstractItemView, 
    QTableWidgetItem, QDialog, QTableWidget, QApplication
)
from PyQt5.QtGui import QColor, QBrush, QFont
from qfluentwidgets import (
    TitleLabel, PushButton, PrimaryPushButton, BodyLabel, TableWidget, RoundMenu, Action, FluentIcon, InfoBar, InfoBarPosition, MessageBox
)
from loguru import logger

from database_manager import db_manager
from ui.image_widget import ImageWidget
from threads.video_download_thread import VideoDownloadThread


class TaskListWidget(QWidget):
    """任务列表界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("taskListWidget")
        # 分页相关
        self.current_page = 1
        self.page_size = 10  # 每页显示10个任务
        self.total_pages = 1
        # 选择相关
        self.selected_tasks = set()  # 存储选中的任务ID
        self.is_all_selected = False
        # 批量下载相关
        self.batch_download_threads = []  # 存储批量下载的线程
        self.batch_download_total = 0  # 总下载任务数
        self.batch_download_completed = 0  # 已完成的下载任务数
        self.batch_download_folder = ''  # 下载文件夹路径
        # 图片加载器
        from threads.network_image_loader import NetworkImageLoader
        self.image_loader = NetworkImageLoader()
        self.image_loader.image_loaded.connect(self.on_image_loaded)
        self.image_loader.load_failed.connect(self.on_image_load_failed)
        self.init_ui()
        # 初始化时加载任务
        self.load_tasks()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 标题和控制按钮
        header_layout = QHBoxLayout()
        title = TitleLabel('视频生成任务')
        header_layout.addWidget(title)
        header_layout.addStretch()

        # 刷新按钮（位于“视频克隆”左侧）
        self.refresh_btn = PushButton('刷新')
        self.refresh_btn.setFixedWidth(80)
        self.refresh_btn.clicked.connect(self.refresh_tasks)
        header_layout.addWidget(self.refresh_btn)

        # 剧本生成按钮（位于刷新旁边）
        self.script_generate_btn = PushButton('剧本生成')
        self.script_generate_btn.setFixedWidth(100)
        self.script_generate_btn.clicked.connect(self.show_script_generation_flow)
        header_layout.addWidget(self.script_generate_btn)

        # 全部删除（仅删除已完成任务）
        self.delete_all_btn = PushButton('全部删除')
        self.delete_all_btn.setFixedWidth(100)
        self.delete_all_btn.clicked.connect(self.delete_all_completed)
        header_layout.addWidget(self.delete_all_btn)

        # 视频克隆按钮
        self.video_clone_btn = PushButton('视频克隆')
        self.video_clone_btn.clicked.connect(self.show_video_clone_dialog)
        self.video_clone_btn.setFixedWidth(100)
        header_layout.addWidget(self.video_clone_btn)

        # 全选按钮
        self.select_all_btn = PushButton('全选')
        self.select_all_btn.clicked.connect(self.toggle_select_all)
        self.select_all_btn.setFixedWidth(80)
        header_layout.addWidget(self.select_all_btn)

        # 批量下载按钮
        self.batch_download_btn = PushButton('批量下载')
        self.batch_download_btn.clicked.connect(self.batch_download_videos)
        self.batch_download_btn.setFixedWidth(100)
        header_layout.addWidget(self.batch_download_btn)

        # 添加任务按钮
        self.add_task_btn = PrimaryPushButton('添加任务')
        self.add_task_btn.clicked.connect(self.show_add_task_dialog)
        header_layout.addWidget(self.add_task_btn)
        
        # 批量添加任务按钮
        self.batch_add_task_btn = PushButton('批量添加')
        self.batch_add_task_btn.clicked.connect(self.show_batch_add_task_dialog)
        header_layout.addWidget(self.batch_add_task_btn)

        # 去首帧按钮
        self.remove_first_frame_btn = PushButton('去首帧')
        self.remove_first_frame_btn.clicked.connect(self.show_remove_first_frame_dialog)
        header_layout.addWidget(self.remove_first_frame_btn)

        layout.addLayout(header_layout)
        
        # 任务列表表格
        self.task_table = TableWidget()
        self.setup_task_table()
        layout.addWidget(self.task_table)

        # 分页控制
        self.create_pagination_controls(layout)

    def create_pagination_controls(self, layout):
        """创建分页控制"""
        pagination_layout = QHBoxLayout()

        # 上一页按钮
        self.prev_btn = PushButton("上一页")
        self.prev_btn.clicked.connect(self.prev_page)
        self.prev_btn.setEnabled(False)  # 初始状态下禁用
        pagination_layout.addWidget(self.prev_btn)

        # 页码信息
        self.page_label = BodyLabel("第 1 页 / 共 1 页")
        self.page_label.setStyleSheet("color: #666; font-size: 13px;")
        pagination_layout.addWidget(self.page_label)

        # 下一页按钮
        self.next_btn = PushButton("下一页")
        self.next_btn.clicked.connect(self.next_page)
        pagination_layout.addWidget(self.next_btn)

        pagination_layout.addStretch()

        # 总条数信息
        self.total_label = BodyLabel("共 0 条记录")
        self.total_label.setStyleSheet("color: #666; font-size: 13px;")
        pagination_layout.addWidget(self.total_label)

        layout.addLayout(pagination_layout)

    def setup_task_table(self):
        """设置任务表格"""
        # 设置表格列
        headers = ['图片', '提示词', '状态', '创建时间']
        self.task_table.setColumnCount(len(headers))
        self.task_table.setHorizontalHeaderLabels(headers)

        # 设置列宽
        self.task_table.setColumnWidth(0, 110)   # 图片
        self.task_table.setColumnWidth(1, 300)  # 提示词
        self.task_table.setColumnWidth(2, 100)  # 状态
        self.task_table.setColumnWidth(3, 150)  # 创建时间

        # 设置表格属性
        self.task_table.setAlternatingRowColors(True)
        vertical_header = self.task_table.verticalHeader()
        if vertical_header:
            vertical_header.setVisible(False)
        horizontal_header = self.task_table.horizontalHeader()
        if horizontal_header:
            horizontal_header.setStretchLastSection(True)

        # 设置行高
        vertical_header = self.task_table.verticalHeader()
        if vertical_header:
            vertical_header.setDefaultSectionSize(120)
            # 强制更新
            self.task_table.resizeRowsToContents()

        # 禁止双击编辑
        self.task_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # 设置整个表格的右键点击和选择（只设置一次）
        self.task_table.setContextMenuPolicy(Qt.CustomContextMenu)  # type: ignore
        self.task_table.customContextMenuRequested.connect(self.show_context_menu_for_table)
        self.task_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.task_table.setSelectionMode(QTableWidget.MultiSelection)
        self.task_table.itemSelectionChanged.connect(self.on_selection_changed)

    def refresh_tasks(self):
        """刷新任务列表"""
        try:
            self.load_tasks()
            # 清空选择状态
            self.selected_tasks.clear()
            self.is_all_selected = False
            self.update_select_button_text()

            InfoBar.success(
                title='已刷新',
                content='任务列表已刷新',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1500,
                parent=self
            )
        except Exception as e:
            InfoBar.error(
                title='错误',
                content=f'刷新失败: {str(e)}',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    def show_script_generation_flow(self):
        """显示剧本生成流程：参数输入 -> 剧本列表"""
        try:
            from components.script_batch_dialog import ScriptParamsDialog, ScriptListDialog
            # 第一步：参数输入
            params_dialog = ScriptParamsDialog(self.window())
            if params_dialog.exec_() == QDialog.Accepted:
                params = params_dialog.get_params()
                # 第二步：剧本列表生成对话框
                list_dialog = ScriptListDialog(
                    theme=params['theme'],
                    aspect_ratio=params['aspect_ratio'],
                    duration=params['duration'],
                    count=params['count'],
                    parent=self.window()
                )
                list_dialog.exec_()
        except Exception as e:
            InfoBar.error(
                title='错误',
                content=f'打开剧本生成失败: {str(e)}',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    def delete_all_completed(self):
        """删除所有已完成和失败任务（危险操作）"""
        dialog = MessageBox(
            title='危险操作',
            content='将删除所有状态为“已完成”和“失败”的任务，且不可恢复。\n请慎重选择，是否继续？',
            parent=self
        )
        dialog.yesButton.setText('谨慎删除')
        dialog.cancelButton.setText('取消')

        if dialog.exec():
            try:
                deleted = db_manager.delete_completed_tasks()
                self.load_tasks()
                # 重置选择
                self.selected_tasks.clear()
                self.is_all_selected = False
                self.update_select_button_text()

                if deleted > 0:
                    InfoBar.success(
                        title='已删除',
                        content=f'共删除 {deleted} 条已完成/失败任务',
                        orient=Qt.Horizontal,  # type: ignore
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2500,
                        parent=self
                    )
                else:
                    InfoBar.info(
                        title='无变化',
                        content='当前没有已完成或失败任务可删除',
                        orient=Qt.Horizontal,  # type: ignore
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
            except Exception as e:
                InfoBar.error(
                    title='错误',
                    content=f'删除失败: {str(e)}',
                    orient=Qt.Horizontal,  # type: ignore
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )

    def load_tasks(self):
        """加载任务列表（分页）"""
        # 获取总记录数
        total_records = db_manager.get_tasks_count()

        # 计算分页信息
        self.total_pages = max(1, (total_records + self.page_size - 1) // self.page_size)

        # 确保当前页不超出范围
        if self.current_page > self.total_pages:
            self.current_page = self.total_pages

        # 计算偏移量
        offset = (self.current_page - 1) * self.page_size

        # 获取当前页的任务
        tasks = db_manager.get_tasks_paginated(limit=self.page_size, offset=offset)

        # 设置表格行数
        self.task_table.setRowCount(len(tasks))

        # 填充表格数据
        for row, task in enumerate(tasks):
            self.populate_task_row(row, task)

        # 设置行高（在数据加载后再次设置确保生效）
        vertical_header = self.task_table.verticalHeader()
        if vertical_header:
            vertical_header.setDefaultSectionSize(120)
            self.task_table.resizeRowsToContents()

        # 更新分页控件状态
        self.update_pagination_controls(total_records)

    def populate_task_row(self, row, task):
        """填充任务表格行数据"""
        # 图片列 - 显示第一张图片
        images = task.get('images', [])
        if images:
            # 创建图片控件显示第一张图片
            first_image_url = images[0]
            image_widget = ImageWidget(first_image_url)
            image_widget.setToolTip(f"包含 {len(images)} 张图片")

            # 设置到表格
            self.task_table.setCellWidget(row, 0, image_widget)

            # 异步加载图片
            self.image_loader.load_image(first_image_url)
        else:
            # 显示无图片占位符
            image_widget = ImageWidget()
            image_widget.setToolTip("没有图片")
            self.task_table.setCellWidget(row, 0, image_widget)

        # 提示词列
        prompt = task.get('prompt', '')
        if prompt:
            prompt_short = prompt[:80] + '...' if len(prompt) > 80 else prompt
            prompt_item = QTableWidgetItem(prompt_short)
            prompt_item.setToolTip(prompt)  # 完整提示词作为工具提示
        else:
            prompt_item = QTableWidgetItem("无提示词")
        self.task_table.setItem(row, 1, prompt_item)

        # 状态列
        status = task.get('status', 'pending')
        # 只有完成和失败是明确的，其他状态都属于进行中
        if status == 'completed':
            status_info = {'text': '已完成', 'color': '#00AA00'}  # 绿色
        elif status == 'failed':
            status_info = {'text': '失败', 'color': '#FF4444'}  # 红色
        else:
            # pending、processing以及其他状态都显示为进行中
            status_info = {'text': '进行中', 'color': '#FFA500'}  # 橙色

        status_item = QTableWidgetItem(status_info['text'])
        status_item.setTextAlignment(Qt.AlignCenter)  # type: ignore

        # 使用QBrush设置文本颜色
        color = QColor(status_info['color'])
        status_item.setForeground(QBrush(color))

        # 设置粗体字体
        font = QFont()
        font.setBold(True)
        status_item.setFont(font)

        self.task_table.setItem(row, 2, status_item)

        # 创建时间列
        created_at = task.get('created_at', '')
        if created_at and ' ' in created_at:
            date_part = created_at.split(' ')[0]
            time_part = created_at.split(' ')[1][:5]
            created_text = f"{date_part} {time_part}"
        else:
            created_text = created_at

        created_item = QTableWidgetItem(created_text)
        created_item.setTextAlignment(Qt.AlignCenter)  # type: ignore
        self.task_table.setItem(row, 3, created_item)

    def on_image_loaded(self, image_url, pixmap):
        """图片加载完成回调"""
        # 更新所有包含此图片URL的单元格
        for row in range(self.task_table.rowCount()):
            widget = self.task_table.cellWidget(row, 0)
            if isinstance(widget, ImageWidget) and widget.get_image_url() == image_url:
                widget.set_image(image_url, pixmap)

    def on_image_load_failed(self, image_url):
        """图片加载失败回调"""
        # 保持占位符状态
        pass

    def show_context_menu_for_table(self, pos):
        """显示表格右键菜单"""
        # 获取点击位置的行
        item = self.task_table.itemAt(pos)
        if not item:
            return

        row = item.row()
        # 获取当前页的任务列表
        offset = (self.current_page - 1) * self.page_size
        tasks = db_manager.get_tasks_paginated(limit=self.page_size, offset=offset)

        if row < len(tasks):
            task = tasks[row]
            self.create_context_menu(task, self.task_table.mapToGlobal(pos))

    def create_context_menu(self, task, pos):
        """创建右键菜单"""
        menu = RoundMenu(parent=self)

        # 查看详情
        view_action = Action(FluentIcon.VIEW, "查看详情")
        view_action.triggered.connect(lambda: self.view_task_detail(task))
        menu.addAction(view_action)

        menu.addSeparator()

        # 下载操作
        video_url = task.get('video_url', '')
        status = task.get('status', '')
        if status == 'completed' and video_url:
            download_action = Action(FluentIcon.DOWNLOAD, "下载视频")
            download_action.triggered.connect(lambda: self.download_task_video(video_url, task))
            menu.addAction(download_action)
        else:
            download_action = Action(FluentIcon.DOWNLOAD, "下载视频")
            download_action.setEnabled(False)
            menu.addAction(download_action)

        menu.addSeparator()

        # 复制链接
        if video_url:
            copy_action = Action(FluentIcon.COPY, "复制链接")
            copy_action.triggered.connect(lambda: self.copy_video_url(video_url))
            menu.addAction(copy_action)

        # 删除任务
        menu.addSeparator()
        delete_action = Action(FluentIcon.DELETE, "删除任务")
        delete_action.triggered.connect(lambda: self.delete_task_from_table(task))
        menu.addAction(delete_action)

        # 显示菜单
        menu.exec(pos)

    def copy_video_url(self, video_url):
        """复制视频URL到剪贴板"""
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(video_url)

        InfoBar.success(
            title='成功',
            content='链接已复制到剪贴板',
            orient=Qt.Horizontal,  # type: ignore
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def on_selection_changed(self):
        """选择变化时的处理"""
        selected_rows = set()
        for item in self.task_table.selectedItems():
            selected_rows.add(item.row())

        # 获取当前页的任务列表
        offset = (self.current_page - 1) * self.page_size
        tasks = db_manager.get_tasks_paginated(limit=self.page_size, offset=offset)

        # 更新选中的任务ID
        self.selected_tasks.clear()
        for row in selected_rows:
            if row < len(tasks):
                task_id = tasks[row].get('task_id')
                if task_id:
                    self.selected_tasks.add(task_id)

        # 更新按钮文本
        self.update_select_button_text()

    def update_select_button_text(self):
        """更新全选按钮文本"""
        if self.is_all_selected or len(self.selected_tasks) == self.task_table.rowCount():
            self.select_all_btn.setText('取消全选')
            self.is_all_selected = True
        else:
            self.select_all_btn.setText('全选')
            self.is_all_selected = False

    def toggle_select_all(self):
        """切换全选状态"""
        if self.is_all_selected:
            # 取消全选
            self.task_table.clearSelection()
            self.selected_tasks.clear()
            self.is_all_selected = False
            self.select_all_btn.setText('全选')
        else:
            # 全选当前页
            self.task_table.selectAll()
            offset = (self.current_page - 1) * self.page_size
            tasks = db_manager.get_tasks_paginated(limit=self.page_size, offset=offset)

            self.selected_tasks.clear()
            for task in tasks:
                if task.get('task_id'):
                    self.selected_tasks.add(task.get('task_id'))

            self.is_all_selected = True
            self.select_all_btn.setText('取消全选')

    def batch_download_videos(self):
        """批量下载视频"""
        if not self.selected_tasks:
            InfoBar.warning(
                title='提示',
                content='请先选择要下载的任务',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return

        # 获取选中任务的详细信息
        selected_tasks_data = []
        offset = (self.current_page - 1) * self.page_size
        tasks = db_manager.get_tasks_paginated(limit=self.page_size, offset=offset)

        downloadable_count = 0
        for task in tasks:
            if (task.get('task_id') in self.selected_tasks and
                task.get('status') == 'completed' and
                task.get('video_url')):
                selected_tasks_data.append(task)
                downloadable_count += 1

        if downloadable_count == 0:
            InfoBar.warning(
                title='提示',
                content='选中的任务中没有可下载的视频',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        # 获取保存路径
        video_save_path = db_manager.load_config('video_save_path', '')
        if not video_save_path:
            video_save_path = str(Path.home() / "Downloads" / "Sora2Videos")
        
        # 确保目录存在
        Path(video_save_path).mkdir(parents=True, exist_ok=True)
        
        # 重置批量下载状态
        self.batch_download_threads = []
        self.batch_download_total = downloadable_count
        self.batch_download_completed = 0
        self.batch_download_folder = video_save_path

        # 开始批量下载
        InfoBar.info(
            title='开始下载',
            content=f'正在下载 {downloadable_count} 个视频...',
            orient=Qt.Horizontal,  # type: ignore
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )
        
        # 获取API Key
        api_key = db_manager.load_config('api_key', '')

        # 依次创建下载线程
        import random
        for index, task in enumerate(selected_tasks_data, start=1):
            video_url = task.get('video_url')
            
            # 使用提示词的前20个字符作为文件名的一部分，只保留字母和数字
            prompt = task.get('prompt', '')
            # 只保留字母和数字，去除其他符号和字符
            clean_prompt = ''.join(c for c in prompt if c.isalnum()).strip()
            # 取前20个字符，如果不足20个字符则使用全部
            prompt_part = clean_prompt[:20] if clean_prompt else 'untitled'
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # 使用索引和随机数确保文件名唯一
            random_suffix = random.randint(100, 999)
            filename = f"{prompt_part}_{timestamp}_{index:02d}_{random_suffix}.mp4"
            save_path = str(Path(video_save_path) / filename)
            
            print(f"开始下载任务 {index}/{downloadable_count}: {task.get('task_id', 'unknown')} -> {filename}")
            
            # 创建并启动下载线程
            download_thread = VideoDownloadThread(video_url, save_path, api_key, prompt)
            download_thread.finished.connect(self.on_batch_download_item_finished)
            download_thread.start()
            
            # 保存线程引用
            self.batch_download_threads.append(download_thread)

    def on_batch_download_item_finished(self, success, message, save_path):
        """批量下载单个视频完成回调"""
        # 更新完成计数
        self.batch_download_completed += 1
        
        if success:
            print(f"视频下载成功: {save_path}")
        else:
            print(f"视频下载失败: {message}")
        
        # 检查是否所有下载都完成了
        if self.batch_download_completed >= self.batch_download_total:
            # 所有下载完成，显示提示并打开文件夹
            InfoBar.success(
                title='下载完成',
                content=f'批量下载完成！共 {self.batch_download_total} 个任务',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            
            # 打开文件夹
            if self.batch_download_folder:
                self.open_folder(self.batch_download_folder)
            
            # 清理线程引用
            self.batch_download_threads = []
            self.batch_download_total = 0
            self.batch_download_completed = 0
            self.batch_download_folder = ''

    def open_folder(self, folder_path):
        """打开文件夹"""
        import subprocess
        import platform
        
        try:
            system = platform.system()
            if system == "Windows":
                os.startfile(folder_path)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", folder_path])
            else:  # Linux
                subprocess.run(["xdg-open", folder_path])
        except Exception as e:
            print(f"打开文件夹失败: {e}")

    def view_task_detail(self, task):
        """查看任务详情"""
        # 创建详情对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("任务详情")
        dialog.resize(600, 500)

        layout = QVBoxLayout(dialog)

        # 任务信息文本
        info_text = f"""
        <h3>任务信息</h3>
        <p><b>任务ID:</b> {task.get('task_id', '')}</p>
        <p><b>状态:</b> {task.get('status', '')}</p>
        <p><b>创建时间:</b> {task.get('created_at', '')}</p>
        <p><b>提示词:</b> {task.get('prompt', '')}</p>
        <p><b>模型:</b> {task.get('model', '')}</p>
        <p><b>时长:</b> {task.get('duration', 0)}秒</p>
        """

        # 图片列表
        images = task.get('images', [])
        if images:
            info_text += f"<p><b>图片列表 ({len(images)}张):</b></p><ul>"
            for i, img in enumerate(images, 1):
                info_text += f"<li>{img}</li>"
            info_text += "</ul>"

        # 视频URL
        video_url = task.get('video_url', '')
        if video_url:
            info_text += f"<p><b>视频链接:</b> <a href='{video_url}'>{video_url}</a></p>"

        # 创建文本浏览器
        from PyQt5.QtWidgets import QTextBrowser
        text_browser = QTextBrowser()
        text_browser.setHtml(info_text)
        text_browser.setOpenExternalLinks(True)
        layout.addWidget(text_browser)

        # 关闭按钮
        close_btn = PushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

        dialog.exec_()

    def download_task_video(self, video_url, task=None):
        """下载任务视频"""
        if not video_url:
            InfoBar.warning(
                title='提示',
                content='没有可下载的视频',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return

        # 获取保存路径
        video_save_path = db_manager.load_config('video_save_path', '')
        if not video_save_path:
            video_save_path = str(Path.home() / "Downloads" / "Sora2Videos")
        
        # 确保目录存在
        Path(video_save_path).mkdir(parents=True, exist_ok=True)
        
        # 生成文件名 - 使用提示词前20个字符（如果提供了任务信息）
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if task and 'prompt' in task:
            # 使用提示词的前20个字符作为文件名的一部分，只保留字母和数字
            prompt = task.get('prompt', '')
            # 只保留字母和数字，去除其他符号和字符
            clean_prompt = ''.join(c for c in prompt if c.isalnum()).strip()
            # 取前20个字符，如果不足20个字符则使用全部
            prompt_part = clean_prompt[:20] if clean_prompt else 'untitled'
            filename = f"{prompt_part}_{timestamp}.mp4"
        else:
            # 如果没有任务信息，使用默认命名
            filename = f"sora_video_{timestamp}.mp4"
        save_path = str(Path(video_save_path) / filename)
        
        # 获取API Key
        api_key = db_manager.load_config('api_key', '')
        
        # 创建下载线程
        self.download_thread = VideoDownloadThread(video_url, save_path, api_key, (task.get('prompt', '') if task else None))
        self.download_thread.progress.connect(self.on_download_progress_table)
        self.download_thread.finished.connect(self.on_download_finished_table)
        self.download_thread.start()
        
        InfoBar.info(
            title='开始下载',
            content=f'正在下载视频到: {video_save_path}',
            orient=Qt.Horizontal,  # type: ignore
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def on_download_progress_table(self, message):
        """下载进度回调（表格）"""
        print(message)

    def on_download_finished_table(self, success, message, save_path):
        """下载完成回调（表格）"""
        if success:
            InfoBar.success(
                title='成功',
                content=f'视频已保存到: {save_path}',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            
            # 打开文件所在目录
            import subprocess
            import platform
            system = platform.system()
            folder_path = str(Path(save_path).parent)
            
            try:
                if system == "Windows":
                    os.startfile(folder_path)
                elif system == "Darwin":  # macOS
                    subprocess.run(["open", folder_path])
                else:  # Linux
                    subprocess.run(["xdg-open", folder_path])
            except:
                pass
        else:
            InfoBar.error(
                title='失败',
                content=message,
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    def delete_task_from_table(self, task):
        """删除任务"""
        # 确认对话框
        dialog = MessageBox(
            title='确认删除',
            content=f'确定要删除任务 "{task.get("task_id", "")[:12]}..." 吗？\n此操作不可恢复！',
            parent=self
        )
        dialog.yesButton.setText('确定删除')
        dialog.cancelButton.setText('取消')

        if dialog.exec():
            try:
                # 从数据库删除任务
                task_id = task.get('task_id')
                if db_manager.delete_task(task_id):
                    # 刷新任务列表
                    self.load_tasks()

                    InfoBar.success(
                        title='成功',
                        content='任务已删除',
                        orient=Qt.Horizontal,  # type: ignore
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
                else:
                    InfoBar.error(
                        title='错误',
                        content='删除任务失败',
                        orient=Qt.Horizontal,  # type: ignore
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
            except Exception as e:
                print(f"删除任务失败: {e}")
                InfoBar.error(
                    title='错误',
                    content=f'删除任务失败: {str(e)}',
                    orient=Qt.Horizontal,  # type: ignore
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )

    def update_pagination_controls(self, total_records):
        """更新分页控件状态"""
        # 更新页码信息
        self.page_label.setText(f"第 {self.current_page} 页 / 共 {self.total_pages} 页")

        # 更新总记录数
        self.total_label.setText(f"共 {total_records} 条记录")

        # 更新按钮状态
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < self.total_pages)

    def prev_page(self):
        """上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            self.load_tasks()

    def next_page(self):
        """下一页"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_tasks()

    def show_video_clone_dialog(self):
        """显示视频克隆对话框"""
        try:
            from components.video_clone_dialog import VideoCloneDialog
            dialog = VideoCloneDialog(self)
            dialog.exec_()
        except Exception as e:
            print(f"显示视频克隆对话框失败: {e}")

    def show_remove_first_frame_dialog(self):
        """选择文件夹并去除该文件夹内所有视频的首帧（覆盖原视频）"""
        try:
            # 选择目标文件夹
            from PyQt5.QtWidgets import QFileDialog
            folder = QFileDialog.getExistingDirectory(self, '选择包含视频的文件夹')
            if not folder:
                logger.info('用户取消选择文件夹，未进行首帧移除')
                return
            logger.info(f'选择文件夹用于首帧移除: {folder}')
            # 扫描文件夹内的视频文件（不递归）
            import os, glob
            video_exts = (".mp4", ".mov", ".mkv", ".webm")
            target_files = []
            for ext in video_exts:
                pattern = os.path.join(folder, f"*{ext}")
                target_files.extend(glob.glob(pattern))

            logger.info(f"检测到视频文件数: {len(target_files)} in {folder}")

            if not target_files:
                logger.warning(f"该文件夹中没有可处理的视频文件: {folder}")
                InfoBar.warning(
                    title='提示',
                    content='该文件夹中没有可处理的视频文件（支持 mp4/mov/mkv/webm）',
                    orient=Qt.Horizontal,  # type: ignore
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2500,
                    parent=self
                )
                return

            # 启动子线程处理
            from threads.video_first_frame_removal_thread import VideoFirstFrameRemovalThread
            self._first_frame_thread = VideoFirstFrameRemovalThread(target_files)
            logger.info(f"启动首帧移除子线程，待处理文件数: {len(target_files)}")
            self._first_frame_thread.progress.connect(lambda msg: InfoBar.info(
                title='处理中',
                content=msg,
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1500,
                parent=self
            ))
            def on_item_done(success, path, err):
                if success:
                    logger.info(f"去首帧成功: {path}")
                    InfoBar.success(
                        title='已完成',
                        content=f'去首帧成功: {os.path.basename(path)}',
                        orient=Qt.Horizontal,  # type: ignore
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=1600,
                        parent=self
                    )
                else:
                    logger.error(f"去首帧失败: {path} - {err}")
                    InfoBar.error(
                        title='失败',
                        content=f'处理失败: {os.path.basename(path)} - {err}',
                        orient=Qt.Horizontal,  # type: ignore
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2500,
                        parent=self
                    )
            self._first_frame_thread.item_finished.connect(on_item_done)
            def on_all_done(total, success_count):
                logger.info(f"首帧移除完成，成功/总: {success_count}/{total}")
                InfoBar.success(
                    title='全部完成',
                    content=f'该文件夹共检测到 {total} 个视频，成功处理 {success_count} 个',
                    orient=Qt.Horizontal,  # type: ignore
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2200,
                    parent=self
                )
            self._first_frame_thread.finished_summary.connect(on_all_done)
            self._first_frame_thread.start()
        except Exception as e:
            logger.exception(f"首帧移除流程异常: {e}")
            InfoBar.error(
                title='错误',
                content=f'处理失败: {str(e)}',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
    def show_failure_reason_dialog(self):
        """显示失败原因说明对话框"""
        try:
            from qfluentwidgets import MessageBox
            # 创建消息框
            dialog = MessageBox(
                title='失败原因说明',
                content="""关于审查，官方审查会涉及至少3个阶段/方向：
1、提交的图片中是否涉及真人（非常像真人的也不行）
2、提示词内容是否违规（暴力、色情、版权、活着的名人）
3、生成结果审查是否合格（这也是大家经常看到的生成了90%多后失败的原因）

请确保遵守相关规定，避免提交违规内容。""",
                parent=self
            )
            dialog.yesButton.setText('我已了解')
            dialog.cancelButton.setVisible(False)  # 隐藏取消按钮
            dialog.exec_()
        except Exception as e:
            print(f"显示失败原因对话框失败: {e}")

    def show_add_task_dialog(self):
        """显示添加任务对话框"""
        from components.add_task_dialog import AddTaskDialog
        dialog = AddTaskDialog(self.window())
        if dialog.exec_() == QDialog.Accepted:
            task_data = dialog.get_task_data()
            if not task_data['prompt']:
                InfoBar.warning(
                    title='警告',
                    content='请输入提示词',
                    orient=Qt.Horizontal,  # type: ignore
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                return

            # 调用主窗口的生成方法
            parent_window = self.window()
            if parent_window and hasattr(parent_window, 'generate_video'):
                parent_window.generate_video(task_data)
    
    def show_batch_add_task_dialog(self):
        """显示批量添加任务对话框（拖拽图片生成记录）"""
        try:
            from components.image_batch_add_dialog import ImageBatchAddDialog
            dialog = ImageBatchAddDialog(self.window())
            if dialog.exec_() == QDialog.Accepted:
                tasks_data = dialog.get_tasks_data()
                if not tasks_data:
                    InfoBar.warning(
                        title='警告',
                        content='没有有效的任务数据（请确保提示词或图片URL已填充）',
                        orient=Qt.Horizontal,  # type: ignore
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
                    return
                
                # 批量创建任务
                parent_window = self.window()
                if parent_window and hasattr(parent_window, 'generate_video'):
                    success_count = 0
                    for task_info in tasks_data:
                        # 构造任务数据（包含图片）
                        task_data = {
                            'prompt': task_info.get('prompt', ''),
                            'model': 'sora-2',
                            'aspect_ratio': task_info.get('resolution', '16:9'),
                            'duration': task_info.get('duration', 10),
                            'images': task_info.get('images', [])
                        }
                        
                        # 调用主窗口的生成方法
                        parent_window.generate_video(task_data)
                        success_count += 1
                        
                    InfoBar.success(
                        title='成功',
                        content=f'已提交 {success_count} 个任务到队列',
                        orient=Qt.Horizontal,  # type: ignore
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )
                    
                    # 刷新任务列表
                    self.load_tasks()
                else:
                    InfoBar.error(
                        title='错误',
                        content='无法获取主窗口实例',
                        orient=Qt.Horizontal,  # type: ignore
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=3000,
                        parent=self
                    )
        except Exception as e:
            InfoBar.error(
                title='错误',
                content=f'批量添加任务失败: {str(e)}',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
