"""
带货界面（复刻列表界面样式）

布局与风格对齐任务列表：顶部标题与操作区、表格、分页控件。
保留“添加”按钮，打开商品添加对话框（仅UI）。
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QHeaderView, QSizePolicy, QAbstractItemView, QTableWidgetItem, QLabel
from qfluentwidgets import (
    TitleLabel, BodyLabel, PushButton, PrimaryPushButton, TableWidget, InfoBar, InfoBarPosition
)
from components.goods_add_dialog import GoodsAddDialog
from components.prompt_settings_dialog import PromptSettingsDialog
from threads.goods_video_pipeline_thread import GoodsVideoPipelineThread
from ui.image_widget import ImageWidget
from database_manager import db_manager


class GoodsInterface(QWidget):
    """带货列表界面（UI骨架，复刻任务列表样式）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("goodsInterface")
        # 提示词缓存（初始化时从数据库加载）
        default_main = (
            '根据提供的商品主图生成标准电商白底图：\n'
            '- 背景：纯白(#FFFFFF)，干净无纹理；\n'
            '- 主体：保持原始外观与质感，不改变颜色与结构；\n'
            '- 抠图：边缘干净无锯齿，无残留背景；\n'
            '- 光线：均匀柔和，无明显阴影或色偏；\n'
            '- 构图：产品居中，适度留白，画面整洁；\n'
            '- 分辨率：至少 2048×2048；\n'
            '- 输出：PNG(透明背景)或JPEG(白底)，适合电商展示。'
        )
        default_scene = (
            '请基于白底图与商品标题生成一个 15 秒的产品介绍视频脚本与镜头计划。要求：\n'
            '1) 产品简短描述与核心卖点(中文)。\n'
            '2) 旁白文案(中文、自然口语，节奏紧凑)。\n'
            '3) 背景音乐风格：轻快现代，音量不压旁白。\n'
            '4) 运镜设计：推进/摇移/环绕等，流畅自然。\n'
            '5) 时间轴划分为 2–3 个镜头，每个镜头标注【时长/画面内容/镜头运动/旁白/字幕】。\n'
            '6) 画面以白底图为核心，可加入品牌色点缀。\n'
            '7) 结尾包含行动号召(如“立即了解/购买”)。\n'
            '总时长严格控制在 15 秒。\n'
            '请按如下格式输出：\n'
            'Shot 1（0–5s）：画面内容…｜镜头运动…｜旁白…｜字幕…\n'
            'Shot 2（5–10s）：…\n'
            'Shot 3（10–15s）：…'
        )
        self.main_prompt_text = db_manager.load_config('main_image_prompt', default_main) or default_main
        self.scene_prompt_text = db_manager.load_config('scene_generation_prompt', default_scene) or default_scene
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        # 与主页任务列表对齐的页面边距与间距
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 顶部标题与操作区（左标题，右操作按钮）
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        title = TitleLabel('商品列表')
        header_layout.addWidget(title)
        header_layout.addStretch()

        # 提示词设置按钮（位于“添加”左侧）
        self.prompt_btn = PushButton('提示词设置')
        self.prompt_btn.setFixedWidth(100)
        self.prompt_btn.clicked.connect(self.on_prompt_settings_clicked)
        header_layout.addWidget(self.prompt_btn)

        self.add_btn = PrimaryPushButton('添加')
        self.add_btn.setFixedWidth(100)
        self.add_btn.clicked.connect(self.on_add_clicked)
        header_layout.addWidget(self.add_btn)
        layout.addLayout(header_layout)

        # 列表表格（使用与主页一致的样式）
        self.table = TableWidget()
        self.setup_table()
        layout.addWidget(self.table)

        # 分页控件（样式复刻，功能占位）
        self.create_pagination_controls(layout)

    def setup_table(self):
        headers = ['商品标题', '主图', '白底图', '状态']
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(0)
        # 表格扩展与选择行为
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        header = self.table.horizontalHeader()
        # 与主页列表一致：最后一列拉伸填充剩余空间
        header.setStretchLastSection(True)
        # 主页未设置固定模式，这里不强制固定，使用固定列宽
        # 开启单元格文本换行
        self.table.setWordWrap(True)
        self.table.setSelectionBehavior(self.table.SelectRows)  # type: ignore
        self.table.setSelectionMode(self.table.MultiSelection)  # type: ignore
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # 行高与表头
        v_header = self.table.verticalHeader()
        if v_header:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(160)
            self.table.resizeRowsToContents()

        # 固定列宽，保持与主页任务列表的风格一致
        # 商品标题、主图、白底图、状态（状态列自动拉伸占满剩余宽度）
        self.table.setColumnWidth(0, 300)
        self.table.setColumnWidth(1, 170)
        self.table.setColumnWidth(2, 170)

    def on_add_clicked(self):
        # 打开添加商品对话框并启动流水线
        try:
            dialog = GoodsAddDialog(self)
            if dialog.exec_():
                title = dialog.get_title() or '未填写标题'
                main_image = dialog.get_main_image()
                # 先在表格插入一行，并显示处理中状态
                row_index = self.table.rowCount()
                self.add_goods_row(title, main_image)
                status_item = self.table.item(row_index, 3)
                if status_item:
                    status_item.setText('处理中')

                # 启动流水线线程
                self.start_goods_pipeline(title, main_image, row_index)
        except Exception as e:
            InfoBar.error(
                title='错误',
                content=f'打开添加对话框失败: {str(e)}',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    def on_prompt_settings_clicked(self):
        """打开提示词设置对话框"""
        try:
            dialog = PromptSettingsDialog(
                initial_main_prompt=self.main_prompt_text,
                initial_scene_prompt=self.scene_prompt_text,
                parent=self
            )
            if dialog.exec_():
                self.main_prompt_text = dialog.get_main_prompt()
                self.scene_prompt_text = dialog.get_scene_prompt()
                InfoBar.success(
                    title='成功',
                    content='提示词已更新',
                    orient=Qt.Horizontal,  # type: ignore
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=1600,
                    parent=self
                )
        except Exception as e:
            InfoBar.error(
                title='错误',
                content=f'打开提示词设置失败: {str(e)}',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    # 使用固定列宽，不随窗口尺寸动态调整

    def add_goods_row(self, title: str, main_image_path: str = ''):
        """向表格添加一行商品数据（UI演示）"""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # 商品标题（支持多行换行）
        title_label = QLabel(title)
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # type: ignore
        title_label.setStyleSheet("padding: 4px; color: #333;")
        self.table.setCellWidget(row, 0, title_label)

        # 主图
        image_widget_main = ImageWidget(size=150)
        if main_image_path:
            try:
                from PyQt5.QtGui import QPixmap
                pixmap = QPixmap(main_image_path)
                if not pixmap.isNull():
                    image_widget_main.set_image(main_image_path, pixmap)
            except Exception:
                pass
        self.table.setCellWidget(row, 1, image_widget_main)

        # 白底图（占位）
        image_widget_white = ImageWidget(size=150)
        self.table.setCellWidget(row, 2, image_widget_white)

        # 状态
        status_item = QTableWidgetItem('未完善')
        status_item.setTextAlignment(Qt.AlignCenter)  # type: ignore
        self.table.setItem(row, 3, status_item)

        # 移除创建时间列，剩余宽度由“状态”列自动拉伸

        # 调整行高以适配内容
        v_header = self.table.verticalHeader()
        if v_header:
            v_header.setDefaultSectionSize(160)
            self.table.resizeRowsToContents()

    def start_goods_pipeline(self, title: str, main_image_path: str, row_index: int):
        try:
            self.pipeline_thread = GoodsVideoPipelineThread(
                title=title,
                main_image_path=main_image_path,
                main_prompt_text=self.main_prompt_text,
                scene_prompt_text=self.scene_prompt_text,
                parent=self,
            )
            self.pipeline_thread.progress.connect(lambda msg: self.on_pipeline_progress(msg, row_index))
            self.pipeline_thread.finished.connect(lambda success, data: self.on_pipeline_finished(success, data, row_index))
            self.pipeline_thread.start()
        except Exception as e:
            InfoBar.error(
                title='错误',
                content=f'启动流水线失败: {str(e)}',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    def on_pipeline_progress(self, msg: str, row_index: int):
        # 在状态栏更新进度
        try:
            status_item = self.table.item(row_index, 3)
            if status_item:
                status_item.setText(msg)
        except Exception:
            pass

    def on_pipeline_finished(self, success: bool, data: dict, row_index: int):
        try:
            if success:
                white_url = data.get('white_image_url', '')
                # 更新白底图单元格显示
                from PyQt5.QtGui import QPixmap
                import requests
                pixmap = None
                try:
                    if white_url:
                        r = requests.get(white_url, timeout=30)
                        if r.status_code == 200:
                            pixmap = QPixmap()
                            pixmap.loadFromData(r.content)
                except Exception:
                    pixmap = None

                w = self.table.cellWidget(row_index, 2)
                if isinstance(w, ImageWidget) and pixmap:
                    w.set_image(white_url, pixmap)

                status_item = self.table.item(row_index, 3)
                if status_item:
                    status_item.setText('已创建任务')

                InfoBar.success(
                    title='完成',
                    content='白底图与视频提示词生成成功，已创建任务',
                    orient=Qt.Horizontal,  # type: ignore
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
            else:
                err = data.get('error') or '未知错误'
                status_item = self.table.item(row_index, 3)
                if status_item:
                    status_item.setText('失败')
                InfoBar.error(
                    title='失败',
                    content=f'流水线执行失败: {err}',
                    orient=Qt.Horizontal,  # type: ignore
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3500,
                    parent=self
                )
        except Exception as e:
            InfoBar.error(
                title='错误',
                content=f'更新UI失败: {str(e)}',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    def create_pagination_controls(self, layout: QVBoxLayout):
        pagination_layout = QHBoxLayout()
        pagination_layout.setContentsMargins(0, 0, 0, 0)
        pagination_layout.setSpacing(8)

        # 上一页按钮
        self.prev_btn = PushButton("上一页")
        self.prev_btn.clicked.connect(self.prev_page)
        self.prev_btn.setEnabled(False)
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

    def prev_page(self):
        InfoBar.info(
            title='提示',
            content='分页暂未实现',
            orient=Qt.Horizontal,  # type: ignore
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def next_page(self):
        InfoBar.info(
            title='提示',
            content='分页暂未实现',
            orient=Qt.Horizontal,  # type: ignore
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )
