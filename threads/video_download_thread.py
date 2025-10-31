"""
视频下载线程
"""

import requests
import os
from PyQt5.QtCore import QThread, pyqtSignal
from loguru import logger

class VideoDownloadThread(QThread):
    """视频下载线程"""
    progress = pyqtSignal(str)  # 进度消息
    finished = pyqtSignal(bool, str, str)  # success, message, save_path

    def __init__(self, video_url, save_path, api_key):
        super().__init__()
        self.video_url = video_url
        self.save_path = save_path
        self.api_key = api_key

    def run(self):
        """执行下载"""
        try:
            logger.info(f"开始下载视频: {self.video_url}")
            self.progress.emit('正在下载视频...')
            
            # 使用普通requests下载视频，不带特殊认证头
            logger.info(f"发送下载请求到: {self.video_url}")
            response = requests.get(self.video_url, stream=True, timeout=300)  # 5分钟超时
            response.raise_for_status()
            
            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))
            logger.info(f"文件总大小: {total_size} bytes")
            
            # 保存视频文件
            logger.info(f"保存文件到: {self.save_path}")
            downloaded_size = 0
            
            # 确保保存目录存在
            os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
            
            with open(self.save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # 每下载1MB报告一次进度
                        if downloaded_size % (1024 * 1024) == 0:
                            progress_mb = downloaded_size // (1024 * 1024)
                            total_mb = total_size // (1024 * 1024) if total_size > 0 else '?'
                            logger.info(f"已下载: {progress_mb}MB / {total_mb}MB")
            
            logger.info(f"视频下载完成: {self.save_path}")
            file_size = os.path.getsize(self.save_path)
            logger.info(f"最终文件大小: {file_size} bytes")
            self.finished.emit(True, '视频下载完成', self.save_path)
                
        except Exception as e:
            error_msg = f'下载出错: {str(e)}'
            logger.error(f"下载失败: URL={self.video_url}, 错误={e}")
            self.finished.emit(False, error_msg, '')