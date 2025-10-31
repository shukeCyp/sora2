#!/usr/bin/env python3
"""
Sora 2 视频生成工具启动脚本
提供GUI和命令行两种模式选择
"""

import sys
import os
from pathlib import Path


def check_dependencies():
    """检查依赖包"""
    print("检查依赖包...")

    required_packages = ['requests']
    optional_packages = ['PyQt5', 'PyQt-Fluent-Widgets']

    missing_required = []
    missing_optional = []

    # 检查必需包
    for package in required_packages:
        try:
            __import__(package)
            print(f"[OK] {package}")
        except ImportError:
            missing_required.append(package)
            print(f"[FAIL] {package}")

    # 检查可选包
    for package in optional_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"[OK] {package}")
        except ImportError:
            missing_optional.append(package)
            print(f"[FAIL] {package}")

    if missing_required:
        print(f"\n缺少必需依赖: {', '.join(missing_required)}")
        print("请运行: pip install -r requirements.txt")
        return False

    return True


def install_dependencies():
    """安装依赖包"""
    print("正在安装依赖包...")
    try:
        import subprocess
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("[OK] 依赖安装成功")
            return True
        else:
            print(f"[ERROR] 依赖安装失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"[ERROR] 安装依赖时出错: {e}")
        return False


def launch_gui():
    """启动GUI界面"""
    print("启动GUI界面...")
    try:
        # 直接导入并启动GUI，不进行额外的依赖检查
        from PyQt5.QtWidgets import QApplication
        from main_window import MainWindow
        
        app = QApplication(sys.argv)

        # 设置应用程序信息
        app.setApplicationName("Sora2 视频生成工具")
        app.setOrganizationName("Sora2")

        window = MainWindow()
        window.show()
        sys.exit(app.exec())

    except ImportError as e:
        print(f"[ERROR] GUI依赖缺失: {e}")
        print("请运行: pip install PyQt5 PyQt-Fluent-Widgets")
        return False
    except Exception as e:
        print(f"[ERROR] 启动GUI失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    # 设置工作目录
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    # 检查Python版本
    if sys.version_info < (3, 7):
        print("[ERROR] 需要Python 3.7或更高版本")
        print(f"当前版本: {sys.version}")
        return

    print(f"Python版本: {sys.version.split()[0]}")
    print(f"工作目录: {script_dir}")

    # 直接启动GUI界面
    print("正在启动GUI界面...")
    launch_gui()


if __name__ == "__main__":
    main()