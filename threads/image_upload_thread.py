"""
图片上传线程 - 使用阿里云OSS（与视频克隆一致的直传方式）
"""

import uuid
from pathlib import Path
import requests
from PyQt5.QtCore import QThread, pyqtSignal
from loguru import logger

class ImageUploadThread(QThread):
    """图片上传线程 - 阿里云OSS直传"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str, str)  # success, message, image_url

    def __init__(self, file_path, token=None):
        super().__init__()
        self.file_path = file_path
        # token 参数兼容旧调用，不再使用
        self.running = True

    def _guess_content_type(self, suffix: str) -> str:
        s = suffix.lower()
        if s in ['.jpg', '.jpeg']:
            return 'image/jpeg'
        if s == '.png':
            return 'image/png'
        if s == '.gif':
            return 'image/gif'
        if s == '.webp':
            return 'image/webp'
        if s in ['.bmp']:
            return 'image/bmp'
        if s in ['.tif', '.tiff']:
            return 'image/tiff'
        return 'application/octet-stream'

    def run(self):
        """将本地图片上传到阿里云OSS并返回URL"""
        try:
            p = Path(self.file_path)
            if not p.exists() or not p.is_file():
                raise FileNotFoundError(f"图片文件不存在: {self.file_path}")

            oss_bucket_url = "https://shuke-sora2.oss-cn-beijing.aliyuncs.com"
            suffix = p.suffix or '.jpg'
            unique_name = f"image_{uuid.uuid4().hex}{suffix}"
            object_key = f"uploads/{unique_name}"
            upload_url = f"{oss_bucket_url}/{object_key}"

            content_type = self._guess_content_type(suffix)
            headers = {
                'Content-Type': content_type,
            }

            self.progress.emit(f"正在上传图片到OSS: {p.name}")
            logger.info(f"开始上传图片到OSS: path={self.file_path} url={upload_url} ct={content_type}")

            with open(self.file_path, 'rb') as f:
                data = f.read()
            resp = requests.put(upload_url, data=data, headers=headers, timeout=120)
            logger.info(f"OSS上传完成，状态码: {resp.status_code}")

            if resp.status_code in [200, 201, 204]:
                image_url = f"{oss_bucket_url}/{object_key}"
                logger.info(f"图片上传成功，URL: {image_url}")
                self.finished.emit(True, "图片上传成功", image_url)
            else:
                err = f"OSS上传失败: {resp.status_code} - {resp.text}"
                logger.error(err)
                self.finished.emit(False, err, "")

        except Exception as e:
            logger.exception(e)
            self.finished.emit(False, f"上传出错: {str(e)}", "")
