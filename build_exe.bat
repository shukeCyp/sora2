@echo off
chcp 65001 >nul
echo ====================================
echo Sora2 视频生成工具 - PyInstaller 打包
echo ====================================
echo.

:: 检查 PyInstaller 是否已安装
echo [1/5] 检查 PyInstaller...
python -c "import PyInstaller" 2>nul
if %errorlevel% neq 0 (
    echo PyInstaller 未安装，正在安装...
    python -m pip install pyinstaller
    if %errorlevel% neq 0 (
        echo 安装 PyInstaller 失败！
        pause
        exit /b 1
    )
    echo PyInstaller 安装成功！
) else (
    echo PyInstaller 已安装
)
echo.

echo 安装/更新 imageio 及 imageio-ffmpeg...
python -m pip install --upgrade imageio imageio-ffmpeg
if %errorlevel% neq 0 (
    echo 依赖安装失败！
    pause
    exit /b 1
)
echo 依赖安装完成
echo.

:: 清理旧的打包文件
echo [2/5] 清理旧的打包文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del /q *.spec

:: 强制删除可能存在的exe文件
if exist dist\Sora2.exe (
    echo 正在强制删除旧的 exe 文件...
    del /f /q dist\Sora2.exe
)
echo 清理完成
echo.

:: 开始打包
echo [3/5] 开始打包...
echo 正在使用 PyInstaller 打包成单文件 exe...
echo.

python -m PyInstaller --onefile --windowed --name "Sora2" --hidden-import PyQt5 --hidden-import PyQt5.QtCore --hidden-import PyQt5.QtGui --hidden-import PyQt5.QtWidgets --hidden-import qfluentwidgets --hidden-import requests --hidden-import loguru --hidden-import sqlite3 --hidden-import imageio --hidden-import imageio_ffmpeg --collect-all qfluentwidgets --collect-all imageio_ffmpeg --add-data "sora2_up.json;." --add-data "README.md;." --noconfirm main.py

if %errorlevel% neq 0 (
    echo.
    echo 打包失败！请检查错误信息。
    pause
    exit /b 1
)

echo.
echo [4/5] 打包完成！
echo.

:: 检查生成的文件
echo [5/5] 检查生成的文件...
if exist dist\Sora2.exe (
    echo ✓ 成功生成: dist\Sora2.exe
    echo.
    echo 文件信息:
    dir dist\Sora2.exe | find "Sora2.exe"
    echo.
    echo ====================================
    echo 打包成功完成！
    echo ====================================
    echo.
    echo 可执行文件位置: dist\Sora2.exe
    echo 您可以将 dist\Sora2.exe 复制到任何位置运行
    echo.
) else (
    echo ✗ 未找到生成的 exe 文件
    echo 打包可能失败，请检查上面的错误信息
)

pause
