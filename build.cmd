@echo off
rem 本地打包：生成 dist\mstsc-manager\ 文件夹（含 mstsc-manager.exe），并压缩成 zip
cd /d "%~dp0"
uv sync --group dev || exit /b 1
uv run pyinstaller main.spec --noconfirm || exit /b 1
for /f "tokens=2 delims== " %%v in ('findstr /r "^version" pyproject.toml') do set VER=%%~v
set VER=%VER:"=%
set ZIP=mstsc-manager-v%VER%-windows-x64.zip
if exist "%ZIP%" del "%ZIP%"
powershell -NoProfile -Command "Compress-Archive -Path 'dist/mstsc-manager/*' -DestinationPath '%ZIP%' -Force"
echo.
echo 输出: dist\mstsc-manager\mstsc-manager.exe
echo 压缩包: %ZIP%
