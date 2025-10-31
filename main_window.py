"""
重构版Sora2主窗口
使用PyQt-Fluent-Widgets创建现代化界面
"""

import sys
import json
import time
import os
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl, QPoint
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog,
    QListWidgetItem, QDialog, QFormLayout, QLabel, QScrollArea, QTableWidgetItem, QMenu, QTableWidget, QAbstractItemView,
    QGroupBox, QCheckBox, QListWidget, QTextBrowser
)
from PyQt5.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent, QPixmap, QBrush, QColor, QFont, QIcon
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
import requests
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

# PyQt-Fluent-Widgets 组件
from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, MessageBox, InfoBar, InfoBarPosition,
    LineEdit, TextEdit, PushButton, PrimaryPushButton, ToolButton,
    ComboBox, SpinBox, ListWidget, CardWidget, BodyLabel, TitleLabel,
    Icon, FluentIcon, Theme, setTheme, ProgressBar, ProgressRing,
    RoundMenu, Action, MenuAnimationType, RadioButton, MessageBoxBase, SubtitleLabel, TableWidget
)

from loguru import logger

# 导入自定义模块
from sora_client import SoraClient
from database_manager import db_manager, model_manager

# 导入拆分的UI组件
from ui.home_interface import HomeInterface
from ui.settings_interface import SettingsInterface
from ui.upscale_interface import UpscaleInterface
from ui.task_list_widget import TaskListWidget

# 导入拆分的对话框组件
from components.add_task_dialog import AddTaskDialog
from components.settings_dialog import SettingsDialog
from components.upscale_settings_dialog import UpscaleSettingsDialog

# 导入拆分的线程类
from threads.network_image_loader import NetworkImageLoader
from threads.image_upload_thread import ImageUploadThread
from threads.video_download_thread import VideoDownloadThread
from threads.task_status_check_thread import TaskStatusCheckThread
from threads.video_generation_thread import VideoGenerationThread

# 导入数据模型
from models.task_model import TaskModel
from models.config_model import ConfigModel
from models.model_info import ModelInfo
from models.upscale_settings import UpscaleSettings

# 导入工具类
from utils.file_utils import open_folder, open_file_location, format_file_size
from utils.log_utils import pack_logs, get_log_file_count
from utils.db_utils import check_database_health, get_database_info
from utils.api_utils import extract_video_url_from_response, parse_api_error


class MainWindow(FluentWindow):
    """主窗口"""
    
    # 定义信号 - 用于Chat任务完成回调
    from PyQt5.QtCore import pyqtSignal
    chat_task_completed = pyqtSignal(object, str)  # (future, task_id)

    def __init__(self):
        super().__init__()
        self._video_thread = None  # type: VideoGenerationThread | None
        self.upload_thread = None
        self.status_check_thread = None  # type: TaskStatusCheckThread | None
        self.image_loader = NetworkImageLoader()  # 图片加载器
        
        # 创建全局线程池(30个线程)
        from concurrent.futures import ThreadPoolExecutor
        self.global_thread_pool = ThreadPoolExecutor(max_workers=30, thread_name_prefix="ChatWorker")
        logger.info("全局线程池已创建: 30个工作线程")

        # 检查数据库状态
        self.check_database_on_startup()

        self.init_ui()

        # 启动任务状态检查线程
        self.start_status_check_thread()

        # 连接图片加载信号
        self.image_loader.image_loaded.connect(self.on_image_loaded)
        self.image_loader.load_failed.connect(self.on_image_load_failed)
        
        # 连接Chat任务完成信号
        self.chat_task_completed.connect(self._on_chat_task_done)

    def init_ui(self):
        """初始化UI"""
        self.resize(1200, 800)
        self.setWindowTitle('Sora2 视频生成工具')
        self.setWindowIcon(QIcon(':/icons/app.ico'))  # 设置窗口图标

        # 创建界面
        self.task_interface = TaskListWidget(self)
        self.upscale_interface = UpscaleInterface(self)
        self.settings_interface = SettingsInterface(self)

        # 添加到导航界面
        self.addSubInterface(self.task_interface, FluentIcon.ROBOT, '任务列表')
        self.addSubInterface(self.upscale_interface, FluentIcon.ZOOM, '高清放大')
        self.addSubInterface(self.settings_interface, FluentIcon.SETTING, '设置')

        self.navigationInterface.setCurrentItem(self.task_interface.objectName())

        # 设置最小宽度
        self.setMinimumWidth(1000)

    def closeEvent(self, a0):
        """窗口关闭时清理线程"""
        # 关闭全局线程池
        if hasattr(self, 'global_thread_pool') and self.global_thread_pool:
            logger.info("正在关闭全局线程池...")
            self.global_thread_pool.shutdown(wait=False)
            logger.info("全局线程池已关闭")
        
        # 停止视频生成线程
        if self._video_thread and self._video_thread.isRunning():
            self._video_thread.quit()
            self._video_thread.wait(1000)

        # 停止上传线程
        if self.upload_thread and self.upload_thread.isRunning():
            self.upload_thread.quit()
            self.upload_thread.wait(1000)

        # 停止状态检查线程
        if self.status_check_thread and self.status_check_thread.isRunning():
            self.status_check_thread.stop()
            self.status_check_thread.wait(2000)

        # 停止图片加载线程
        if self.image_loader and self.image_loader.isRunning():
            self.image_loader.loading = False
            self.image_loader.wait(1000)

        super().closeEvent(a0)

    def check_database_on_startup(self):
        """启动时检查数据库状态"""
        try:
            logger.info("正在检查数据库状态...")
            health = db_manager.check_database_health()

            if health['overall_status'] == 'healthy':
                logger.info("[OK] 数据库状态健康")
                # 记录表信息
                tables_info = []
                for table_name, table_info in health['tables'].items():
                    if table_info['exists']:
                        tables_info.append(f"{table_name}({table_info['record_count']}条)")
                logger.info(f"数据表状态: {', '.join(tables_info)}")

            elif health['overall_status'] == 'warning':
                logger.warning(f"[WARNING] 数据库警告: {health.get('missing_tables', [])}")
                InfoBar.warning(
                    title='数据库警告',
                    content=f'缺少数据表: {", ".join(health.get("missing_tables", []))}',
                    orient=Qt.Horizontal,  # type: ignore
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )

            elif health['overall_status'] == 'error':
                logger.error(f"[ERROR] 数据库错误: {health.get('error', '未知错误')}")
                InfoBar.error(
                    title='数据库错误',
                    content=health.get('error', '数据库初始化失败'),
                    orient=Qt.Horizontal,  # type: ignore
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=8000,
                    parent=self
                )

            # 获取数据库详细信息
            db_info = db_manager.get_database_info()
            if 'error' not in db_info:
                size_mb = db_info['size'] / (1024 * 1024)
                logger.info(f"数据库大小: {size_mb:.2f}MB")
                logger.info(f"数据库路径: {db_info['path']}")

        except Exception as e:
            logger.error(f"数据库启动检查失败: {e}")
            InfoBar.error(
                title='检查失败',
                content=f'无法检查数据库状态: {str(e)}',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

    def start_status_check_thread(self):
        """启动任务状态检查线程"""
        try:
            self.status_check_thread = TaskStatusCheckThread()
            self.status_check_thread.status_updated.connect(self.on_task_status_updated)
            self.status_check_thread.start()
            logger.info("任务状态检查线程已启动")
        except Exception as e:
            logger.error(f"启动任务状态检查线程失败: {e}")

    def on_task_status_updated(self, task_id, updates):
        """任务状态更新回调 - 线程安全的界面更新"""
        try:
            # 使用QTimer确保在主线程中执行UI更新
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._update_ui_for_task_status(task_id, updates))

        except Exception as e:
            logger.error(f"处理任务状态更新失败: {e}")

    def _update_ui_for_task_status(self, task_id, updates):
        """在主线程中更新UI"""
        try:
            # 刷新任务列表 (调用TaskInterface的load_tasks方法)
            self.task_interface.load_tasks()

            # 获取更新后的状态信息
            status = updates.get('status', '')
            status_text = {
                'pending': '排队中',
                'processing': '进行中',
                'completed': '已完成',
                'failed': '失败'
            }.get(status, status)

            # 显示状态更新通知
            if status == 'completed':
                InfoBar.success(
                    title='任务完成',
                    content=f'任务 {task_id[:12]}... 已完成',
                    orient=Qt.Horizontal,  # type: ignore
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
            elif status == 'failed':
                InfoBar.error(
                    title='任务失败',
                    content=f'任务 {task_id[:12]}... 失败',
                    orient=Qt.Horizontal,  # type: ignore
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )

        except Exception as e:
            logger.error(f"更新UI失败: {e}")

    def generate_video(self, task_data: Dict[str, Any]):
        """生成视频"""
        try:
            # 获取API Key
            api_key = db_manager.load_config('api_key', '')
            if not api_key:
                InfoBar.error(
                    title='错误',
                    content='请先在设置中配置API Key',
                    orient=Qt.Horizontal,  # type: ignore
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return

            # 创建视频生成线程
            self._video_thread = VideoGenerationThread(
                api_key=api_key,
                prompt=task_data['prompt'],
                model=task_data['model'],
                duration=task_data['duration'],
                images=task_data['images'],
                aspect_ratio=task_data.get('aspect_ratio', '16:9')
            )
            
            # 连接信号
            self._video_thread.progress.connect(self.on_generation_progress)
            self._video_thread.task_created.connect(self.on_task_created)
            self._video_thread.task_creation_failed.connect(self.on_task_creation_failed)
            self._video_thread.finished.connect(self.on_generation_finished)
            
            # 启动线程
            self._video_thread.start()
            
            InfoBar.info(
                title='开始生成',
                content='正在创建视频生成任务...',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )

        except Exception as e:
            logger.error(f"创建视频生成任务失败: {e}")
            InfoBar.error(
                title='错误',
                content=f'创建任务失败: {str(e)}',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    def on_generation_progress(self, message: str):
        """生成进度回调"""
        logger.info(message)

    def on_task_created(self, task_id: str, task_data: Dict[str, Any]):
        """任务创建成功回调"""
        try:
            # 保存任务到数据库
            db_manager.add_task(task_data)
            
            # 刷新任务列表
            self.task_interface.load_tasks()
            
            logger.info(f"任务已保存到数据库: {task_id}")

        except Exception as e:
            logger.error(f"保存任务失败: {e}")

    def on_task_creation_failed(self, message: str):
        """任务创建失败回调"""
        InfoBar.error(
            title='任务创建失败',
            content=message,
            orient=Qt.Horizontal,  # type: ignore
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )

    def on_generation_finished(self, success: bool, message: str, video_url: str, task_id: str):
        """生成完成回调"""
        if success:
            InfoBar.success(
                title='生成完成',
                content=message,
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            
            # 更新任务状态
            if task_id:
                updates = {
                    'status': 'completed',
                    'video_url': video_url,
                    'completed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                db_manager.update_task(task_id, updates)
                
                # 刷新任务列表
                self.task_interface.load_tasks()
        else:
            InfoBar.error(
                title='生成失败',
                content=message,
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            
            # 更新任务状态为失败
            if task_id:
                updates = {
                    'status': 'failed',
                    'completed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                db_manager.update_task(task_id, updates)
                
                # 刷新任务列表
                self.task_interface.load_tasks()

    def on_image_loaded(self, image_url: str, pixmap: QPixmap):
        """图片加载完成回调"""
        # 这个方法现在由TaskInterface处理
        pass

    def on_image_load_failed(self, image_url: str):
        """图片加载失败回调"""
        # 这个方法现在由TaskInterface处理
        pass

    def _on_chat_task_done(self, future, task_id: str):
        """Chat任务完成回调"""
        try:
            # 获取任务结果
            success, message, video_url = future.result()
            
            if success:
                InfoBar.success(
                    title='生成完成',
                    content=message,
                    orient=Qt.Horizontal,  # type: ignore
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                
                # 更新任务状态
                if task_id:
                    updates = {
                        'status': 'completed',
                        'video_url': video_url,
                        'completed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    db_manager.update_task(task_id, updates)
                    
                    # 刷新任务列表
                    self.task_interface.load_tasks()
            else:
                InfoBar.error(
                    title='生成失败',
                    content=message,
                    orient=Qt.Horizontal,  # type: ignore
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                
                # 更新任务状态为失败
                if task_id:
                    updates = {
                        'status': 'failed',
                        'completed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    db_manager.update_task(task_id, updates)
                    
                    # 刷新任务列表
                    self.task_interface.load_tasks()

        except Exception as e:
            logger.error(f"处理Chat任务结果失败: {e}")
            InfoBar.error(
                title='错误',
                content=f'处理任务结果失败: {str(e)}',
                orient=Qt.Horizontal,  # type: ignore
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )