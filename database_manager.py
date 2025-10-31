"""
数据库管理模块
用于存储历史记录和用户设置
"""

import sqlite3
import json
import os
import sys
import platform
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
from loguru import logger


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self):
        """初始化数据库管理器"""
        # 获取应用数据目录
        self.app_data_dir = self._get_app_data_dir()

        # 在Sora2文件夹下创建两个文件夹：logs和database
        self.logs_dir = os.path.join(self.app_data_dir, "logs")
        self.database_dir = os.path.join(self.app_data_dir, "database")
        self.db_path = os.path.join(self.database_dir, "sora2.db")

        # 确保所有目录存在
        os.makedirs(self.app_data_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.database_dir, exist_ok=True)

        # 配置日志
        self._setup_logging()

        logger.info(f"数据库路径: {self.db_path}")
        logger.info(f"日志目录: {self.logs_dir}")
        logger.info(f"数据库备份目录: {self.database_dir}")

        # 检查和初始化数据库
        self._check_and_init_database()
    
    def _get_app_data_dir(self) -> str:
        """获取应用数据目录（跨平台兼容）"""
        system = platform.system()
        
        if system == "Darwin":  # macOS
            # ~/Library/Application Support/Sora2
            app_dir = os.path.expanduser("~/Library/Application Support/Sora2")
        elif system == "Windows":  # Windows
            # %APPDATA%\Sora2
            app_dir = os.path.join(os.environ.get("APPDATA", ""), "Sora2")
        else:  # Linux和其他Unix系统
            # ~/.local/share/sora2
            app_dir = os.path.expanduser("~/.local/share/sora2")
            
        return app_dir

    def _setup_logging(self):
        """配置日志系统"""
        try:
            from datetime import datetime

            # 生成带日期时间的日志文件名
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"sora2_{current_time}.log"
            log_file_path = os.path.join(self.logs_dir, log_filename)

            # 移除默认的日志处理器
            logger.remove()

            # 添加控制台输出（彩色）
            logger.add(
                sys.stderr,
                format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
                level="INFO"
            )

            # 添加文件输出
            logger.add(
                log_file_path,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                level="DEBUG",
                rotation="50 MB",  # 文件大小超过50MB时轮转
                retention="7 days",  # 保留7天的日志
                compression="zip",  # 压缩旧日志文件
                encoding="utf-8"
            )

            logger.info(f"日志系统初始化完成，日志文件: {log_file_path}")

        except Exception as e:
            # 如果日志配置失败，使用基本配置
            print(f"日志配置失败: {e}")

    def get_current_log_file(self) -> str:
        """获取当前日志文件路径"""
        try:
            # 查找最新的日志文件
            log_files = [f for f in os.listdir(self.logs_dir) if f.startswith('sora2_') and f.endswith('.log')]
            if log_files:
                latest_log = max(log_files, key=lambda f: os.path.getctime(os.path.join(self.logs_dir, f)))
                return os.path.join(self.logs_dir, latest_log)
            return ""
        except Exception:
            return ""

    def _check_and_init_database(self):
        """检查并初始化数据库"""
        try:
            # 检查数据库文件是否存在
            db_exists = os.path.exists(self.db_path)

            if not db_exists:
                logger.info("数据库文件不存在，正在创建...")
            else:
                logger.info("数据库文件已存在，检查表结构...")

            # 连接数据库并检查表
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 获取所有表名
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]

            logger.info(f"现有数据表: {existing_tables}")

            # 需要创建的表
            required_tables = ['config', 'tasks']

            # 检查每个表是否存在
            for table in required_tables:
                if table not in existing_tables:
                    logger.info(f"创建数据表: {table}")

            conn.close()

            # 初始化所有表结构
            self._init_database()

            # 验证表是否创建成功
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            final_tables = [row[0] for row in cursor.fetchall()]
            conn.close()

            missing_tables = [t for t in required_tables if t not in final_tables]
            if missing_tables:
                logger.error(f"以下表创建失败: {missing_tables}")
                raise Exception(f"数据库表创建失败: {missing_tables}")
            else:
                logger.info("所有数据表创建/验证完成")

        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise

    def _init_database(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 创建logs表（如果不存在）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

        # 创建config、tasks和chat_tasks表
        self.create_config_table()
        self.create_tasks_table()
        self.create_chat_tasks_table()

    def init_db(self):
        """公开的初始化数据库方法"""
        self._init_database()
    
  
  
    def add_log(self, level: str, message: str) -> bool:
        """添加日志记录"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO logs (level, message)
                VALUES (?, ?)
            ''', (level, message))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"添加日志失败: {e}")
            return False

    def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取日志记录"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, level, message, created_at
                FROM logs
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))

            logs = []
            for row in cursor.fetchall():
                log = {
                    'id': row[0],
                    'level': row[1],
                    'message': row[2],
                    'created_at': row[3]
                }
                logs.append(log)

            conn.close()
            return logs
        except Exception as e:
            logger.error(f"获取日志失败: {e}")
            return []

    
    def clear_logs(self) -> bool:
        """清空日志"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM logs')

            conn.commit()
            conn.close()
            logger.info("日志已清空")
            return True
        except Exception as e:
            logger.error(f"清空日志失败: {e}")
            return False

    
    def create_config_table(self) -> bool:
        """创建config配置表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT,
                    type TEXT DEFAULT 'string',
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 插入默认配置
            default_configs = [
                ('api_key', '', 'string', 'Sora API Key'),
                ('api_base_url', 'https://api.shaohua.fun', 'string', 'API Base URL'),
                ('image_token', '1c17b11693cb5ec63859b091c5b9c1b2', 'string', '图床Token'),
                ('default_model', 'sora-2', 'string', '默认模型'),
                ('default_duration', '10', 'integer', '默认时长(秒)'),
                ('auto_download', 'true', 'boolean', '自动下载视频'),
                ('video_save_path', '', 'string', '视频保存路径'),
                ('theme', 'auto', 'string', '主题设置(light/dark/auto)'),
            ]

            for key, value, type_, desc in default_configs:
                cursor.execute('''
                    INSERT OR IGNORE INTO config (key, value, type, description)
                    VALUES (?, ?, ?, ?)
                ''', (key, value, type_, desc))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"创建config表失败: {e}")
            return False

    def create_tasks_table(self) -> bool:
        """创建tasks任务表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    prompt TEXT NOT NULL,
                    model TEXT DEFAULT 'sora-2',
                    orientation TEXT DEFAULT 'portrait',
                    size TEXT DEFAULT 'small',
                    duration INTEGER DEFAULT 10,
                    images TEXT,
                    video_url TEXT,
                    thumbnail_url TEXT,
                    status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    progress INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_task_id ON tasks(task_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at)')

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"创建tasks表失败: {e}")
            return False

    def create_chat_tasks_table(self) -> bool:
        """创建chat_tasks表 - 记录Chat模式的任务"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    model TEXT NOT NULL,
                    is_chat_mode INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
                )
            ''')

            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_tasks_task_id ON chat_tasks(task_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_tasks_model ON chat_tasks(model)')

            conn.commit()
            conn.close()
            logger.info("chat_tasks表创建成功")
            return True
        except Exception as e:
            logger.error(f"创建chat_tasks表失败: {e}")
            return False

    def save_config(self, key: str, value: Any, type_: str = 'string', description: Optional[str] = None) -> bool:
        """保存配置到config表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 转换值为字符串
            if isinstance(value, bool):
                value_str = 'true' if value else 'false'
            elif isinstance(value, (dict, list)):
                value_str = json.dumps(value)
            else:
                value_str = str(value)

            cursor.execute('''
                INSERT OR REPLACE INTO config (key, value, type, description, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (key, value_str, type_, description))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False

    def load_config(self, key: str, default: Any = None) -> Any:
        """从config表加载配置"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT value, type FROM config WHERE key = ?', (key,))
            row = cursor.fetchone()

            conn.close()

            if row:
                value_str, type_ = row
                # 根据类型转换值
                if type_ == 'boolean':
                    return value_str.lower() == 'true'
                elif type_ == 'integer':
                    return int(value_str)
                elif type_ == 'float':
                    return float(value_str)
                elif type_ == 'json':
                    return json.loads(value_str)
                else:
                    return value_str
            else:
                return default
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return default

    def add_task(self, task_data: Dict[str, Any]) -> bool:
        """添加任务到tasks表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            images_json = json.dumps(task_data.get('images', []))

            cursor.execute('''
                INSERT INTO tasks
                (task_id, prompt, model, orientation, size, duration, images,
                 status, progress, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                task_data.get('task_id'),
                task_data.get('prompt'),
                task_data.get('model', 'sora-2'),
                task_data.get('orientation', 'portrait'),
                task_data.get('size', 'small'),
                task_data.get('duration', 10),
                images_json,
                task_data.get('status', 'pending'),
                task_data.get('progress', 0),
                task_data.get('error_message')
            ))

            conn.commit()
            conn.close()
            logger.info(f"添加任务成功: {task_data.get('task_id')}")
            return True
        except Exception as e:
            logger.error(f"添加任务失败: {e}")
            return False

    def get_tasks(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """获取任务列表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if status:
                cursor.execute('''
                    SELECT id, task_id, prompt, model, orientation, size, duration, images,
                           video_url, thumbnail_url, status, error_message, progress,
                           created_at, started_at, completed_at, updated_at
                    FROM tasks
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (status, limit))
            else:
                cursor.execute('''
                    SELECT id, task_id, prompt, model, orientation, size, duration, images,
                           video_url, thumbnail_url, status, error_message, progress,
                           created_at, started_at, completed_at, updated_at
                    FROM tasks
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (limit,))

            tasks = []
            for row in cursor.fetchall():
                task = {
                    'id': row[0],
                    'task_id': row[1],
                    'prompt': row[2],
                    'model': row[3],
                    'orientation': row[4],
                    'size': row[5],
                    'duration': row[6],
                    'images': json.loads(row[7]) if row[7] else [],
                    'video_url': row[8],
                    'thumbnail_url': row[9],
                    'status': row[10],
                    'error_message': row[11],
                    'progress': row[12],
                    'created_at': row[13],
                    'started_at': row[14],
                    'completed_at': row[15],
                    'updated_at': row[16]
                }
                tasks.append(task)

            conn.close()
            return tasks
        except Exception as e:
            logger.error(f"获取任务失败: {e}")
            return []

    def get_tasks_paginated(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """获取任务列表（支持分页）"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, task_id, prompt, model, orientation, size, duration, images,
                       video_url, thumbnail_url, status, error_message, progress,
                       created_at, started_at, completed_at, updated_at
                FROM tasks
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))

            tasks = []
            for row in cursor.fetchall():
                task = {
                    'id': row[0],
                    'task_id': row[1],
                    'prompt': row[2],
                    'model': row[3],
                    'orientation': row[4],
                    'size': row[5],
                    'duration': row[6],
                    'images': json.loads(row[7]) if row[7] else [],
                    'video_url': row[8],
                    'thumbnail_url': row[9],
                    'status': row[10],
                    'error_message': row[11],
                    'progress': row[12],
                    'created_at': row[13],
                    'started_at': row[14],
                    'completed_at': row[15],
                    'updated_at': row[16]
                }
                tasks.append(task)

            conn.close()
            return tasks
        except Exception as e:
            logger.error(f"获取任务失败: {e}")
            return []

    def get_tasks_count(self) -> int:
        """获取任务总数"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM tasks')
            count = cursor.fetchone()[0]

            conn.close()
            return count
        except Exception as e:
            logger.error(f"获取任务总数失败: {e}")
            return 0

    def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """更新任务"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            set_clauses = []
            values = []

            for key, value in updates.items():
                if key == 'images':
                    value = json.dumps(value)

                set_clauses.append(f"{key} = ?")
                values.append(value)

            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            values.append(task_id)

            cursor.execute(f'''
                UPDATE tasks
                SET {", ".join(set_clauses)}
                WHERE task_id = ?
            ''', values)

            conn.commit()
            conn.close()
            logger.info(f"更新任务成功: {task_id}")
            return True
        except Exception as e:
            logger.error(f"更新任务失败: {e}")
            return False

    def delete_task(self, task_id: str) -> bool:
        """删除任务(同时会自动删除chat_tasks表中的关联记录)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 先删除chat_tasks表中的记录(如果存在)
            cursor.execute('DELETE FROM chat_tasks WHERE task_id = ?', (task_id,))
            chat_deleted = cursor.rowcount
            
            # 再删除tasks表中的记录
            cursor.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))
            tasks_deleted = cursor.rowcount

            conn.commit()
            conn.close()

            if tasks_deleted > 0:
                if chat_deleted > 0:
                    logger.info(f"删除Chat任务成功: {task_id} (tasks:{tasks_deleted}条, chat_tasks:{chat_deleted}条)")
                else:
                    logger.info(f"删除任务成功: {task_id} (删除了{tasks_deleted}条记录)")
                return True
            else:
                logger.warning(f"未找到要删除的任务: {task_id}")
                return False
        except Exception as e:
            logger.error(f"删除任务失败: {e}")
            return False
    
    def add_chat_task(self, task_id: str, model: str) -> bool:
        """添加Chat模式任务记录"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR IGNORE INTO chat_tasks (task_id, model)
                VALUES (?, ?)
            ''', (task_id, model))

            conn.commit()
            conn.close()
            logger.info(f"Chat任务记录已添加: {task_id} (model: {model})")
            return True
        except Exception as e:
            logger.error(f"添加Chat任务记录失败: {e}")
            return False
    
    def is_chat_task(self, task_id: str) -> bool:
        """检查是否为Chat模式任务"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM chat_tasks WHERE task_id = ?', (task_id,))
            count = cursor.fetchone()[0]

            conn.close()
            return count > 0
        except Exception as e:
            logger.error(f"检查Chat任务状态失败: {e}")
            return False
    
    def get_chat_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取所有Chat模式任务列表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT ct.task_id, ct.model, ct.created_at,
                       t.prompt, t.status, t.video_url
                FROM chat_tasks ct
                LEFT JOIN tasks t ON ct.task_id = t.task_id
                ORDER BY ct.created_at DESC
                LIMIT ?
            ''', (limit,))

            columns = ['task_id', 'model', 'created_at', 'prompt', 'status', 'video_url']
            chat_tasks = []
            
            for row in cursor.fetchall():
                task = dict(zip(columns, row))
                chat_tasks.append(task)

            conn.close()
            return chat_tasks
        except Exception as e:
            logger.error(f"获取Chat任务列表失败: {e}")
            return []

    def clear_tasks(self) -> bool:
        """清空所有任务"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM tasks')

            conn.commit()
            conn.close()
            logger.info("所有任务已清空")
            return True
        except Exception as e:
            logger.error(f"清空任务失败: {e}")
            return False

    def get_task_statistics(self) -> Dict[str, int]:
        """获取任务统计信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT status, COUNT(*) as count
                FROM tasks
                GROUP BY status
            ''')

            stats = {
                'total': 0,
                'pending': 0,
                'processing': 0,
                'completed': 0,
                'failed': 0
            }

            for row in cursor.fetchall():
                status, count = row
                stats['total'] += count
                if status in stats:
                    stats[status] = count

            conn.close()
            return stats
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}

    def check_database_health(self) -> Dict[str, Any]:
        """检查数据库健康状态"""
        try:
            health_info = {
                'database_exists': os.path.exists(self.db_path),
                'database_path': self.db_path,
                'tables': {},
                'overall_status': 'healthy'
            }

            if not health_info['database_exists']:
                health_info['overall_status'] = 'error'
                health_info['error'] = '数据库文件不存在'
                return health_info

            # 检查表结构
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 获取所有表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            required_tables = ['config', 'tasks']

            for table in required_tables:
                table_info = {
                    'exists': table in tables,
                    'record_count': 0
                }

                if table_info['exists']:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    table_info['record_count'] = cursor.fetchone()[0]

                health_info['tables'][table] = table_info

            conn.close()

            # 检查是否有缺失的表
            missing_tables = [t for t in required_tables if t not in tables]
            if missing_tables:
                health_info['overall_status'] = 'warning'
                health_info['missing_tables'] = missing_tables

            return health_info

        except Exception as e:
            logger.error(f"数据库健康检查失败: {e}")
            return {
                'overall_status': 'error',
                'error': str(e),
                'database_path': self.db_path
            }

    def get_database_info(self) -> Dict[str, Any]:
        """获取数据库详细信息"""
        try:
            info = {
                'path': self.db_path,
                'size': 0,
                'created_time': None,
                'modified_time': None,
                'tables_summary': {}
            }

            if os.path.exists(self.db_path):
                stat = os.stat(self.db_path)
                info['size'] = stat.st_size
                info['created_time'] = stat.st_ctime
                info['modified_time'] = stat.st_mtime

                # 获取表统计信息
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]

                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    info['tables_summary'][table] = count

                conn.close()

            return info

        except Exception as e:
            logger.error(f"获取数据库信息失败: {e}")
            return {'error': str(e), 'path': self.db_path}


class ModelManager:
    """模型管理器"""

    def __init__(self):
        self.models = {
            'sora-2': {
                'name': 'Sora 2 标准版',
                'description': 'Sora 2 现已推出，openai最新的视频生成模型比之前的系统更加物理精准、逼真，并且更易于控制。它还支持同步对话和音效。',
                'type': 'standard',
                'orientation': 'auto',
                'quality': 'standard'
            },
            'sora-2-landscape': {
                'name': 'Sora 2 横屏版',
                'description': '调用新版本的 Sora 生成横屏视频。',
                'type': 'landscape',
                'orientation': 'landscape',
                'quality': 'standard'
            }
        }

    def get_all_models(self):
        """获取所有模型"""
        return self.models

    def get_model_info(self, model_id):
        """获取指定模型信息"""
        return self.models.get(model_id, {})

    def get_models_by_type(self, model_type):
        """根据类型获取模型"""
        return {k: v for k, v in self.models.items() if v['type'] == model_type}

    def get_models_by_quality(self, quality):
        """根据画质获取模型"""
        return {k: v for k, v in self.models.items() if v['quality'] == quality}


# 全局实例
db_manager = DatabaseManager()
model_manager = ModelManager()