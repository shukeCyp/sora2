"""
拖拽图片批量添加生成任务对话框
"""

from pathlib import Path
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDragEnterEvent, QDropEvent
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidgetItem, QHeaderView
)
from qfluentwidgets import (
    TitleLabel, BodyLabel, PushButton, PrimaryPushButton, InfoBar, InfoBarPosition,
    TableWidget, ComboBox
)

from threads.image_upload_thread import ImageUploadThread


class ImageBatchAddDialog(QDialog):
    """批量添加生成任务（拖拽图片）"""

    def __init__(self, parent=None, default_prompt: str = "", default_resolution: str = "16:9", default_duration: int = 10):
        super().__init__(parent)
        self.setWindowTitle("批量添加生成任务（拖拽图片）")
        self.setModal(True)
        self.resize(860, 620)
        self._default_prompt = default_prompt or ""
        self._default_resolution = default_resolution if default_resolution in ("16:9", "9:16") else "16:9"
        self._default_duration = default_duration if default_duration in (10, 15) else 10
        self._upload_threads = []
        self.setAcceptDrops(True)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        title = TitleLabel("将图片拖拽到对话框任意位置以添加任务记录")
        layout.addWidget(title)

        desc = BodyLabel("每张图片会生成一条记录，支持编辑提示词；每行可单独选择分辨率与时长，也可批量应用设置")
        desc.setStyleSheet("color: #666;")
        layout.addWidget(desc)

        # 选项区域（分辨率/时长）
        opts = QHBoxLayout()
        res_label = BodyLabel("分辨率：")
        opts.addWidget(res_label)
        self.resolution_combo = ComboBox()
        self.resolution_combo.addItems(["16:9", "9:16"]) 
        self.resolution_combo.setCurrentText(self._default_resolution)
        self.resolution_combo.currentTextChanged.connect(self.on_resolution_changed)
        opts.addWidget(self.resolution_combo)

        dur_label = BodyLabel("时长：")
        opts.addWidget(dur_label)
        self.duration_combo = ComboBox()
        self.duration_combo.addItems(["10", "15"]) 
        self.duration_combo.setCurrentText(str(self._default_duration))
        self.duration_combo.currentTextChanged.connect(self.on_duration_changed)
        opts.addWidget(self.duration_combo)
        
        # 应用到所有记录按钮
        self.apply_all_btn = PushButton("应用到所有行")
        self.apply_all_btn.clicked.connect(self.apply_options_to_all_rows)
        opts.addWidget(self.apply_all_btn)
        opts.addStretch()
        layout.addLayout(opts)

        # 表格
        self.table = TableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["图片URL", "提示词", "分辨率", "时长(秒)", "状态"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        # 按钮栏
        btns = QHBoxLayout()
        btns.addStretch()
        self.cancel_btn = PushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        btns.addWidget(self.cancel_btn)

        self.ok_btn = PrimaryPushButton("确定")
        self.ok_btn.clicked.connect(self.accept)
        btns.addWidget(self.ok_btn)
        layout.addLayout(btns)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if not urls:
            event.ignore()
            return
        event.acceptProposedAction()
        count = 0
        file_paths: list[str] = []
        for url in urls:
            fp = url.toLocalFile()
            if fp:
                file_paths.append(fp)
        for fp in file_paths:
            if self._is_image_file(fp):
                self._append_row_for_file(fp)
                self._upload_image(fp)
                count += 1
        if count > 0:
            InfoBar.info(
                title='添加图片',
                content=f'已添加 {count} 张图片，开始上传...',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )

    def _append_row_for_file(self, file_path: str):
        row = self.table.rowCount()
        self.table.insertRow(row)
        # 图片URL列先显示本地路径或占位
        self.table.setItem(row, 0, QTableWidgetItem(Path(file_path).name))
        # 提示词默认
        self.table.setItem(row, 1, QTableWidgetItem(self._default_prompt))
        # 分辨率下拉
        res_combo = ComboBox()
        res_combo.addItems(["16:9", "9:16"]) 
        res_combo.setCurrentText(self._default_resolution)
        self.table.setCellWidget(row, 2, res_combo)
        
        # 时长下拉
        dur_combo = ComboBox()
        dur_combo.addItems(["10", "15"]) 
        dur_combo.setCurrentText(str(self._default_duration))
        self.table.setCellWidget(row, 3, dur_combo)
        # 状态
        status_item = QTableWidgetItem("上传中")
        status_item.setForeground(Qt.darkBlue)
        self.table.setItem(row, 4, status_item)

    def _upload_image(self, file_path: str):
        token = "1c17b11693cb5ec63859b091c5b9c1b2"  # 与单任务上传一致的预设token
        thread = ImageUploadThread(file_path, token)
        thread.progress.connect(lambda msg: None)
        # 闭包捕获行索引
        row_index = self.table.rowCount() - 1
        thread.finished.connect(lambda success, message, url: self._on_upload_finished(row_index, success, message, url))
        thread.start()
        self._upload_threads.append(thread)

    def _on_upload_finished(self, row: int, success: bool, message: str, image_url: str):
        if row < 0 or row >= self.table.rowCount():
            return
        if success and image_url:
            self.table.setItem(row, 0, QTableWidgetItem(image_url))
            status_item = QTableWidgetItem("已上传")
            status_item.setForeground(Qt.darkGreen)
            self.table.setItem(row, 4, status_item)
        else:
            status_item = QTableWidgetItem(f"上传失败: {message}")
            status_item.setForeground(Qt.red)
            self.table.setItem(row, 4, status_item)

    def _is_image_file(self, file_path: str) -> bool:
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff', '.tif'}
        return Path(file_path).suffix.lower() in image_extensions

    def on_resolution_changed(self, text: str):
        if text in ("16:9", "9:16"):
            self._default_resolution = text

    def on_duration_changed(self, text: str):
        try:
            val = int(text)
            if val in (10, 15):
                self._default_duration = val
        except Exception:
            pass

    def apply_options_to_all_rows(self):
        rows = self.table.rowCount()
        for r in range(rows):
            res_widget = self.table.cellWidget(r, 2)
            dur_widget = self.table.cellWidget(r, 3)
            if res_widget and hasattr(res_widget, 'setCurrentText'):
                res_widget.setCurrentText(self._default_resolution)
            if dur_widget and hasattr(dur_widget, 'setCurrentText'):
                dur_widget.setCurrentText(str(self._default_duration))

    def get_tasks_data(self) -> list[dict]:
        """从表格收集任务数据"""
        tasks = []
        rows = self.table.rowCount()
        for r in range(rows):
            url_item = self.table.item(r, 0)
            prompt_item = self.table.item(r, 1)
            res_widget = self.table.cellWidget(r, 2)
            dur_widget = self.table.cellWidget(r, 3)
            status_item = self.table.item(r, 4)

            image_url = url_item.text().strip() if url_item else ""
            prompt = (prompt_item.text().strip() if prompt_item else "")
            resolution = "16:9"
            if res_widget and hasattr(res_widget, 'currentText'):
                resolution = res_widget.currentText().strip()
            duration_str = str(self._default_duration)
            if dur_widget and hasattr(dur_widget, 'currentText'):
                duration_str = dur_widget.currentText().strip()
            status = status_item.text() if status_item else ""

            # 仅收集已上传成功的行
            if image_url and status.startswith("已上传"):
                try:
                    duration = int(duration_str)
                except Exception:
                    duration = self._default_duration
                # 校正分辨率
                if resolution not in ("16:9", "9:16"):
                    resolution = self._default_resolution

                tasks.append({
                    'prompt': prompt,
                    'resolution': resolution,
                    'duration': duration,
                    'images': [image_url]
                })

        return tasks
