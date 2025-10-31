# Sora2 视频生成工具

一个支持全系列Sora 2模型的视频生成工具，具备以下核心功能：

## 核心功能

- 支持标准版、高清版、横屏版、竖屏版等所有Sora-2模型
- 可自定义视频方向、尺寸、时长等参数
- 支持带图/无图视频生成
- 自动轮询任务状态并下载结果视频
- 提供GUI图形界面与命令行双模式
- 具备历史记录、设置保存、日志查看等完整用户功能

## 系统架构

通过`sora_client.py`调用固定API代理服务完成视频生成。

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行程序

```bash
python main.py
```

## 打包成可执行文件

```bash
build_exe.bat
```

## 功能模块

### 1. 任务列表
- 查看所有视频生成任务
- 支持批量下载已完成的视频
- 右键菜单操作（查看详情、下载视频、复制链接、删除任务）

### 2. 高清放大
- 视频分辨率提升功能
- 批量处理多个视频文件
- 自定义处理模式和放大系数
- 集成ComfyUI进行AI视频处理

### 3. 设置
- API密钥配置
- ComfyUI服务器地址设置
- 视频保存路径配置
- 数据管理（日志查看、数据库管理）

## 技术栈

- **PyQt5**: 构建GUI图形界面
- **PyQt-Fluent-Widgets**: 提供现代化UI组件
- **requests**: 调用Sora 2 API接口
- **loguru**: 日志记录管理
- **SQLite**: 本地数据存储

## 目录结构

```
├── components/     UI组件封装
├── models/         数据模型定义
├── threads/        多线程操作
├── ui/             各个界面实现
├── utils/          工具类函数
├── main.py         主程序入口
├── database_manager.py 数据库管理
├── sora_client.py  API客户端
└── config.ini      配置文件
```