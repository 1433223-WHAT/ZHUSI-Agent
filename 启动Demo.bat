@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set "BACKEND_PORT=8787"
set "APP_URL=http://127.0.0.1:%BACKEND_PORT%/demo/collaborator.html"
set "HEALTH_URL=http://127.0.0.1:%BACKEND_PORT%/api/health"

echo.
echo  =============================================
echo   筑思 Agent - 建筑学习与设计协作系统
echo  =============================================
echo.

set "PYTHON_EXE="
for /f "delims=" %%P in ('where python 2^>nul') do (
    if not defined PYTHON_EXE (
        "%%P" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul
        if not errorlevel 1 set "PYTHON_EXE=%%P"
    )
)
if not defined PYTHON_EXE (
    echo  [错误] 未找到可运行的 Python 3.8 或更高版本。请检查 PATH 中的 Python 安装位置。
    goto :failed
)

if not exist ".env" (
    echo  [错误] 未找到 .env。请复制 .env.example 为 .env，并填写需要使用的模型配置。
    goto :failed
)

if not exist "requirements.txt" (
    echo  [错误] 未找到 requirements.txt，项目文件可能不完整。
    goto :failed
)

"%PYTHON_EXE%" -c "import requests, docx, pypdf, PIL; import win32com.client" >nul 2>nul
if errorlevel 1 (
    echo  [提示] 正在安装核心依赖（requests / numpy / python-docx / pypdf / Pillow，约几十 MB）
    "%PYTHON_EXE%" -m pip install -r requirements.txt
    "%PYTHON_EXE%" -c "import requests, docx, pypdf, PIL; import win32com.client" >nul 2>nul
    if errorlevel 1 (
        echo  [错误] 依赖未安装成功，请手动执行后重试：
        echo         "%PYTHON_EXE%" -m pip install -r requirements.txt
        goto :failed
    )
    echo  [0/3] 核心依赖安装完成。
)

powershell -NoProfile -Command "if (Get-NetTCPConnection -State Listen -LocalPort %BACKEND_PORT% -ErrorAction SilentlyContinue) { exit 1 }"
if errorlevel 1 (
    echo  [错误] 端口 %BACKEND_PORT% 已被占用。请先运行 停止筑思Agent.bat，或关闭占用该端口的程序。
    goto :failed
)

echo  [1/3] 环境检查通过：%PYTHON_EXE%
echo  [2/3] 启动网页与 API 服务（端口 %BACKEND_PORT%）...
start "筑思Agent-Backend" cmd /k ""%PYTHON_EXE%" server.py --port %BACKEND_PORT%"

powershell -NoProfile -Command "$ok=$false; for ($i=0; $i -lt 20; $i++) { try { $r=Invoke-RestMethod -Uri '%HEALTH_URL%' -TimeoutSec 2; if ($r.status -eq 'ok') { $ok=$true; break } } catch {}; Start-Sleep -Milliseconds 500 }; if (-not $ok) { exit 1 }"
if errorlevel 1 (
    echo  [错误] 后端未在 10 秒内通过健康检查：%HEALTH_URL%
    echo         请查看“筑思Agent-Backend”窗口中的错误信息。
    goto :failed
)

powershell -NoProfile -Command "$ok=$false; for ($i=0; $i -lt 20; $i++) { try { $r=Invoke-WebRequest -UseBasicParsing -Uri '%APP_URL%' -TimeoutSec 2; if ($r.StatusCode -eq 200) { $ok=$true; break } } catch {}; Start-Sleep -Milliseconds 500 }; if (-not $ok) { exit 1 }"
if errorlevel 1 (
    echo  [错误] 主页面未在 10 秒内就绪：%APP_URL%
    echo         请查看“筑思Agent-Backend”窗口中的错误信息。
    goto :failed
)

echo  [3/3] 后端健康检查与主页面检查通过。

echo.
echo  启动成功：%APP_URL%
echo  健康检查：%HEALTH_URL%
echo  停止服务：双击 停止筑思Agent.bat
echo.
start "" "%APP_URL%"
pause
exit /b 0

:failed
echo.
echo  启动未完成，未通过的检查已显示在上方。
echo.
pause
exit /b 1
