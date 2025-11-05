"""
批量克隆界面

导入视频文件夹，过滤出≤20MB的视频，逐个分析并创建视频生成任务，
在列表中展示提示词与成功/失败状态，并支持导出表格。
"""

import os
from pathlib import Path
from typing import List, Dict, Any
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QTableWidgetItem
from qfluentwidgets import (
    PushButton, PrimaryPushButton, TitleLabel, BodyLabel, TableWidget, InfoBar, InfoBarPosition, RoundMenu, Action, FluentIcon
)

from utils.file_utils import format_file_size
from database_manager import db_manager
from threads.video_analysis_thread import VideoAnalysisThread
from components.prompt_preview_dialog import PromptPreviewDialog


class BatchCloneInterface(QWidget):
    """批量克隆界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("batchCloneInterface")
        self.video_items: List[Dict[str, Any]] = []
        self.current_index: int = 0
        self.is_processing: bool = False
        self.analysis_thread = None
        self.generation_thread = None
        self.status_timer = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 标题与说明
        header_layout = QHBoxLayout()
        title = TitleLabel('批量克隆')
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        description = BodyLabel('导入视频文件夹，仅展示≤20MB的视频，串行分析并生成提示词（不自动创建任务）。')
        description.setStyleSheet("color: #666; font-size: 13px;")
        layout.addWidget(description)

        # 控制按钮
        control_layout = QHBoxLayout()
        self.import_btn = PushButton('导入视频文件夹')
        self.import_btn.clicked.connect(self.import_video_folder)
        control_layout.addWidget(self.import_btn)

        self.start_btn = PrimaryPushButton('开始执行')
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_processing)
        control_layout.addWidget(self.start_btn)

        self.stop_btn = PushButton('停止')
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_processing)
        control_layout.addWidget(self.stop_btn)

        self.export_btn = PushButton('导出表格')
        self.export_btn.clicked.connect(self.export_table)
        control_layout.addWidget(self.export_btn)

        control_layout.addStretch()
        layout.addLayout(control_layout)

        # 列表表格
        self.table = TableWidget()
        self.setup_table()
        layout.addWidget(self.table)

        # 状态标签
        self.status_label = BodyLabel('请导入视频文件夹')
        self.status_label.setStyleSheet("color: #666; font-size: 13px;")
        layout.addWidget(self.status_label)

    def setup_table(self):
        headers = ['文件名', '大小', '提示词', '状态', '路径']
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(0)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(self.table.SelectRows)  # type: ignore
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)  # type: ignore
        self.table.customContextMenuRequested.connect(self.on_table_context_menu)

    def import_video_folder(self):
        folder = QFileDialog.getExistingDirectory(self, '选择视频文件夹', str(Path.home()))
        if not folder:
            return

        video_exts = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
        max_size = 20 * 1024 * 1024  # 20MB

        items: List[Dict[str, Any]] = []
        for root, _, files in os.walk(folder):
            for name in files:
                ext = Path(name).suffix.lower()
                if ext in video_exts:
                    path = Path(root) / name
                    try:
                        size = os.path.getsize(path)
                    except Exception:
                        size = 0
                    if size <= max_size:
                        items.append({
                            'file_name': name,
                            'path': str(path),
                            'size': size,
                            'prompt': '',
                            'status': '待处理',
                            'video_url': ''
                        })

        self.video_items = items
        self.refresh_table()

        if self.video_items:
            self.start_btn.setEnabled(True)
            self.status_label.setText(f'已导入 {len(self.video_items)} 个视频（≤20MB）')
            InfoBar.success(
                title='成功',
                content=f'成功导入 {len(self.video_items)} 个视频',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
        else:
            self.start_btn.setEnabled(False)
            self.status_label.setText('未找到符合条件的视频（≤20MB）')
            InfoBar.warning(
                title='提示',
                content='未找到符合条件的视频文件',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2500,
                parent=self
            )

    def refresh_table(self):
        self.table.setRowCount(0)
        for i, item in enumerate(self.video_items):
            self.table.insertRow(i)
            # 文件名
            self.table.setItem(i, 0, QTableWidgetItem(item['file_name']))
            # 大小
            self.table.setItem(i, 1, QTableWidgetItem(format_file_size(item['size'])))
            # 提示词
            prompt_display = QTableWidgetItem(self._truncate_prompt(item['prompt']))
            prompt_display.setToolTip(item['prompt'])
            self.table.setItem(i, 2, prompt_display)
            # 状态
            self.table.setItem(i, 3, QTableWidgetItem(item['status']))
            # 路径
            self.table.setItem(i, 4, QTableWidgetItem(item['path']))

    def on_table_context_menu(self, pos):
        index = self.table.indexAt(pos)
        row = index.row()
        if row < 0 or row >= len(self.video_items):
            return

        menu = RoundMenu(parent=self)

        # 查看
        view_action = Action(FluentIcon.VIEW, '查看')
        def _do_view():
            prompt = self.video_items[row].get('prompt', '')
            if not prompt:
                InfoBar.warning(
                    title='提示',
                    content='该条目尚未分析，暂无提示词',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                return
            try:
                dialog = PromptPreviewDialog(prompt, self)
                dialog.exec_()
            except Exception as e:
                InfoBar.error(
                    title='错误',
                    content=f'打开预览失败: {str(e)}',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
        view_action.triggered.connect(_do_view)
        menu.addAction(view_action)

        menu.addSeparator()

        # 删除
        delete_action = Action(FluentIcon.DELETE, '删除')
        def _do_delete():
            try:
                del self.video_items[row]
                self.table.removeRow(row)
            except Exception:
                pass
        delete_action.triggered.connect(_do_delete)
        menu.addAction(delete_action)

        menu.exec(self.table.mapToGlobal(pos))

    def start_processing(self):
        if not self.video_items:
            return
        api_key = db_manager.load_config('api_key', '')
        if not api_key:
            InfoBar.error(
                title='错误',
                content='请先在设置中配置API Key',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        self.is_processing = True
        self.current_index = 0
        self.import_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText('开始批量分析...')
        self.process_next()

    def stop_processing(self):
        self.is_processing = False
        self.import_btn.setEnabled(True)
        self.start_btn.setEnabled(bool(self.video_items))
        self.stop_btn.setEnabled(False)
        self.status_label.setText('已停止批量执行')
        # 无状态轮询

    def process_next(self):
        if not self.is_processing or self.current_index >= len(self.video_items):
            self.finish_processing()
            return

        row = self.current_index
        item = self.video_items[row]

        # 更新状态
        item['status'] = '分析中'
        self.table.item(row, 3).setText('分析中')
        self.status_label.setText(f"正在分析: {item['file_name']}")

        # 启动分析线程
        api_key = db_manager.load_config('api_key', '')
        self.analysis_thread = VideoAnalysisThread(item['path'], api_key)
        self.analysis_thread.progress.connect(lambda msg, r=row: self.on_analysis_progress(r, msg))
        self.analysis_thread.result.connect(lambda result, r=row: self.on_analysis_result(r, result))
        self.analysis_thread.error.connect(lambda err, r=row: self.on_analysis_error(r, err))
        self.analysis_thread.start()

    def on_analysis_progress(self, row: int, message: str):
        self.status_label.setText(message)
        # 行状态保持“分析中”即可

    def on_analysis_result(self, row: int, result: Any):
        # 构建提示词文本（仅包含解析内容，无额外说明）
        prompt_text = ''
        if isinstance(result, list):
            for item in result:
                prompt_text += f"时间: {item.get('time', '')}\n"
                prompt_text += f"内容: {item.get('content', '')}\n"
                if item.get('style'):
                    prompt_text += f"风格: {item.get('style', '')}\n"
                if item.get('narration'):
                    prompt_text += f"旁白: {item.get('narration', '')}\n"
                if item.get('dialogue'):
                    prompt_text += f"人物对话: {item.get('dialogue', '')}\n"
                if item.get('audio'):
                    prompt_text += f"音频/音乐: {item.get('audio', '')}\n"
                prompt_text += "\n"
        else:
            prompt_text = str(result)

        # 更新提示词与状态
        self.video_items[row]['prompt'] = prompt_text
        self.table.item(row, 2).setText(self._truncate_prompt(prompt_text))
        self.table.item(row, 2).setToolTip(prompt_text)
        self.video_items[row]['status'] = '已分析'
        self.table.item(row, 3).setText('已分析')

        # 下一项
        self.current_index += 1
        QTimer.singleShot(0, self.process_next)

    def on_analysis_error(self, row: int, error_message: str):
        self.video_items[row]['status'] = '分析失败'
        self.table.item(row, 3).setText('分析失败')
        InfoBar.error(
            title='错误',
            content=f"分析失败: {error_message}",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=4000,
            parent=self
        )
        # 跳到下一项
        self.current_index += 1
        QTimer.singleShot(0, self.process_next)

    # 取消任务创建逻辑

    # 取消任务创建回调

    # 取消任务失败回调

    # 取消生成完成回调

    def finish_processing(self):
        self.is_processing = False
        self.import_btn.setEnabled(True)
        self.start_btn.setEnabled(bool(self.video_items))
        self.stop_btn.setEnabled(False)
        self.status_label.setText('批量执行完成')
        # 无状态轮询
        InfoBar.success(
            title='完成',
            content='批量克隆执行完成',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    # 移除数据库状态轮询

    def export_table(self):
        if not self.video_items:
            InfoBar.warning(
                title='提示',
                content='没有可导出的数据',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            '导出CSV',
            '批量克隆结果.csv',
            'CSV文件 (*.csv)'
        )
        if not file_path:
            return

        try:
            import csv
            with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['文件名', '提示词', '状态', '路径'])
                for item in self.video_items:
                    writer.writerow([
                        item.get('file_name', ''),
                        item.get('prompt', '').replace('\n', ' ').strip(),
                        item.get('status', ''),
                        item.get('path', '')
                    ])

            InfoBar.success(
                title='成功',
                content='已导出为CSV文件',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
        except Exception as e:
            InfoBar.error(
                title='错误',
                content=f'导出失败: {str(e)}',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    def _truncate_prompt(self, text: str, limit: int = 60) -> str:
        if not text:
            return ''
        t = text.strip().replace('\n', ' ')
        return t if len(t) <= limit else t[:limit] + '…'
