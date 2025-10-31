"""
图片上传线程 - 图床API
"""

import requests
from PyQt5.QtCore import QThread, pyqtSignal

class ImageUploadThread(QThread):
    """图片上传线程 - 图床API"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str, str)  # success, message, image_url

    def __init__(self, file_path, token):
        super().__init__()
        self.file_path = file_path
        self.token = token
        self.running = True

    def run(self):
        """实际的图片上传实现"""
        try:
            # 图床API endpoint
            upload_url = "http://image.lanzhi.fun/api/index.php"

            # 准备文件上传
            with open(self.file_path, 'rb') as f:
                files = {'image': f}
                data = {'token': self.token}

                self.progress.emit(f"正在上传图片: {self.file_path}")
                response = requests.post(upload_url, files=files, data=data, timeout=60)

            if response.status_code == 200:
                result = response.json()
                if result.get('result') == 'success' and result.get('code') == 200:
                    image_url = result.get('url', '')
                    if image_url:
                        self.finished.emit(True, "图片上传成功", image_url)
                    else:
                        self.finished.emit(False, "上传成功但未获取到图片URL", "")
                else:
                    error_msg = result.get('message', '上传失败')
                    self.finished.emit(False, f"上传失败: {error_msg}", "")
            else:
                self.finished.emit(False, f"上传失败，状态码: {response.status_code}", "")

        except Exception as e:
            self.finished.emit(False, f"上传出错: {str(e)}", "")