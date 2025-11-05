"""
视频分析工作线程
调用自定义API代理分析视频
"""

import requests
import json
import os
import uuid
import re
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal
from loguru import logger
from database_manager import db_manager
from utils.file_utils import format_file_size

class VideoAnalysisThread(QThread):
    """视频分析工作线程"""
    progress = pyqtSignal(str)  # 进度消息
    result = pyqtSignal(object)  # 分析结果
    error = pyqtSignal(str)  # 错误消息

    def __init__(self, video_path, api_key):
        super().__init__()
        self.video_path = video_path
        self.api_key = api_key

    def run(self):
        """执行视频分析"""
        try:
            # 检查视频文件大小
            if not self.check_file_size():
                return
                
            self.progress.emit("正在上传视频到阿里云OSS...")
            
            # 先上传视频到阿里云OSS
            video_url = self.upload_video_to_oss()
            
            self.progress.emit("正在分析视频...")
            
            # 调用自定义API代理进行视频分析
            analysis_result = self.analyze_video_with_proxy(video_url)
            
            self.result.emit(analysis_result)
                
        except Exception as e:
            error_msg = f"视频分析失败: {str(e)}"
            logger.error(error_msg)
            logger.exception(e)  # 记录完整的异常堆栈
            self.error.emit(error_msg)

    def check_file_size(self):
        """检查视频文件大小"""
        try:
            file_size = os.path.getsize(self.video_path)
            # 20MB = 20 * 1024 * 1024 bytes
            max_size = 20 * 1024 * 1024
            
            if file_size > max_size:
                error_msg = f"视频文件大小为 {format_file_size(file_size)}，超过20MB限制"
                logger.error(error_msg)
                self.error.emit(error_msg)
                return False
            return True
        except Exception as e:
            error_msg = f"检查文件大小失败: {str(e)}"
            logger.error(error_msg)
            self.error.emit(error_msg)
            return False

    def upload_video_to_oss(self):
        """上传视频到阿里云OSS"""
        try:
            logger.info(f"开始上传视频到阿里云OSS: {self.video_path}")
            
            # 阿里云OSS桶地址
            oss_bucket_url = "https://shuke-sora2.oss-cn-beijing.aliyuncs.com"
            logger.debug(f"使用OSS桶地址: {oss_bucket_url}")
            
            # 生成唯一的文件名
            file_extension = Path(self.video_path).suffix
            unique_filename = f"video_{uuid.uuid4().hex}{file_extension}"
            object_key = f"uploads/{unique_filename}"
            
            # 构建上传URL (使用PUT方法)
            upload_url = f"{oss_bucket_url}/{object_key}"
            logger.debug(f"上传URL: {upload_url}")
            
            # 读取视频文件内容
            with open(self.video_path, 'rb') as video_file:
                video_data = video_file.read()
                
            # 设置请求头
            headers = {
                'Content-Type': 'video/mp4',  # 根据实际文件类型调整
            }
            
            self.progress.emit("正在上传视频文件到阿里云OSS...")
            logger.info("开始发送上传请求到阿里云OSS (使用PUT方法)")
            
            # 发送上传请求 (使用PUT方法)
            response = requests.put(upload_url, data=video_data, headers=headers, timeout=300)
            logger.info(f"上传请求完成，状态码: {response.status_code}")
            
            if response.status_code in [200, 201, 204]:
                # 上传成功，返回可访问的URL
                video_url = f"{oss_bucket_url}/{object_key}"
                logger.info(f"视频上传成功，URL: {video_url}")
                return video_url
            else:
                error_msg = f"视频上传到阿里云OSS失败: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            logger.error(f"视频上传到阿里云OSS失败: {str(e)}")
            logger.exception(e)  # 记录完整的异常堆栈
            raise

    def analyze_video_with_proxy(self, video_url):
        """使用自定义API代理分析视频"""
        try:
            logger.info(f"开始分析视频，URL: {video_url}")
            
            # 从数据库获取API代理地址
            api_proxy = "https://api.shaohua.fun"  # 默认代理地址
            logger.debug(f"使用API代理地址: {api_proxy}")
            
            # 构建API请求
            url = f"{api_proxy}/v1/chat/completions"
            logger.debug(f"分析API URL: {url}")
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            logger.debug(f"分析请求头设置完成")
            
            # 构建请求体，包含视频URL
            payload = {
                "model": "gemini-2.5-pro-preview-05-06",
                "stream": False,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "请分析该视频并按时间轴拆分为若干场景。" \
                                    "每个场景请严格给出以下字段，使用简体中文：" \
                                    "time(时间或时间段)、content(内容)、style(风格)、narration(旁白)、dialogue(人物对话)、audio(音频/音乐)。" \
                                    "仅以JSON数组返回，不要任何额外说明或客套话。示例：" \
                                    "[{" \
                                    "\"time\": \"00:00-00:05\", \"content\": \"镜头掠过城市夜景\", \"style\": \"冷色调、快剪\", " \
                                    "\"narration\": \"开场解说\", \"dialogue\": \"\", \"audio\": \"低沉电子乐\"}]"
                                )
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": video_url
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 4000
            }
            logger.debug(f"分析请求体构建完成，模型: {payload['model']}")
            
            self.progress.emit("正在调用视频分析API...")
            
            # 发送请求
            logger.info("开始发送分析请求")
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            logger.info(f"分析请求完成，状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                logger.debug(f"分析响应: {result}")
                
                # 解析响应结果
                analysis_result = self.parse_api_response(result)
                logger.info(f"解析分析结果完成，结果项数: {len(analysis_result) if isinstance(analysis_result, list) else 'N/A'}")
                
                # 检查是否有有效的分析结果
                if not analysis_result:
                    error_msg = "视频分析未返回有效结果"
                    logger.warning(error_msg)
                    raise Exception(error_msg)
                    
                return analysis_result
            else:
                error_msg = f"API调用失败: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            logger.error(f"API代理调用失败: {str(e)}")
            logger.exception(e)  # 记录完整的异常堆栈
            # 重新抛出异常，不返回模拟数据
            raise

    def parse_api_response(self, response):
        """解析API响应"""
        try:
            logger.info("开始解析API响应")
            
            if not response:
                logger.warning("API响应为空")
                return []
            
            if 'choices' not in response:
                logger.warning("API响应中缺少'choices'字段")
                return []
            
            choices = response['choices']
            if not choices:
                logger.warning("'choices'字段为空")
                return []
                
            # 获取第一个选择的内容
            message = choices[0].get('message', {})
            content = message.get('content', '')
            
            if not content:
                logger.warning("消息内容为空")
                return []
            
            # 优先尝试按JSON解析
            json_text = content.strip()
            # 去除代码块围栏
            if '```' in json_text:
                fences = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", json_text)
                if fences:
                    json_text = fences[0].strip()
            # 截取可能的JSON片段
            start_idx_candidates = [idx for idx in (json_text.find('['), json_text.find('{')) if idx != -1]
            if start_idx_candidates:
                start_idx = min(start_idx_candidates)
                end_idx = max(json_text.rfind(']'), json_text.rfind('}'))
                if end_idx > start_idx:
                    json_text = json_text[start_idx:end_idx+1]
            try:
                data = json.loads(json_text)
                scenes = data.get('scenes', data) if isinstance(data, dict) else data
                if isinstance(scenes, list):
                    normalized = []
                    for s in scenes:
                        if not isinstance(s, dict):
                            continue
                        time_val = s.get('time') or s.get('time_range')
                        if not time_val:
                            start = s.get('start', '')
                            end = s.get('end', '')
                            time_val = f"{start}-{end}".strip('-')
                        item = {
                            'time': time_val or '',
                            'content': s.get('content') or s.get('description') or '',
                            'style': s.get('style') or '',
                            'narration': s.get('narration') or s.get('voice_over') or '',
                            'dialogue': s.get('dialogue') or s.get('character_dialogue') or '',
                            'audio': s.get('audio') or s.get('music_audio') or s.get('bgm') or ''
                        }
                        normalized.append(item)
                        logger.debug(f"解析场景 {len(normalized)}: {item}")
                    if normalized:
                        logger.info(f"JSON解析完成，共{len(normalized)}个场景")
                        return normalized
            except Exception as e:
                logger.debug(f"JSON解析失败，回退到行解析: {e}")

            # 回退：简单解析内容，按行分割
            lines = content.strip().split('\n')
            logger.info(f"内容解析完成，共{len(lines)}行")

            result = []
            i = 0
            while i < len(lines):
                # 跳过空行
                if not lines[i].strip():
                    i += 1
                    continue
                # 简单解析，假设每3行是一个时间段的信息
                if i + 2 < len(lines):
                    item = {
                        'time': f"00:00:{i//3*5:02d}",  # 简单的时间戳
                        'content': lines[i].strip() if lines[i].strip() else "视频内容",
                        'style': '',
                        'narration': '',
                        'dialogue': '',
                        'audio': lines[i+1].strip() if i+1 < len(lines) and lines[i+1].strip() else "音频内容"
                    }
                    result.append(item)
                    logger.debug(f"解析时间段 {len(result)}: {item}")
                i += 3

            logger.info(f"解析完成，共{len(result)}个时间段")
            return result
            
        except Exception as e:
            logger.error(f"解析API响应失败: {str(e)}")
            logger.exception(e)  # 记录完整的异常堆栈
            return []

    def get_mock_data(self):
        """获取模拟数据 - 仅用于测试"""
        logger.info("返回模拟数据")
        return [
            {
                'time': '00:00:01',
                'content': '视频开始，显示标题画面',
                'audio': '背景音乐开始播放'
            },
            {
                'time': '00:00:05',
                'content': '主角出现在画面中，穿着红色衣服',
                'audio': '主角说："大家好，欢迎观看我的视频"'
            },
            {
                'time': '00:00:10',
                'content': '展示产品特写镜头',
                'audio': '介绍产品功能和特点'
            },
            {
                'time': '00:00:15',
                'content': '演示产品使用过程',
                'audio': '详细说明使用步骤'
            },
            {
                'time': '00:00:20',
                'content': '总结和结束画面',
                'audio': '感谢观看，再见'
            }
        ]
