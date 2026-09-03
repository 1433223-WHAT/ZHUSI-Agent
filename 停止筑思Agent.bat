@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo  筑思 Agent 停止工具
echo  只检查本项目默认端口 8787，并只停止 Python 进程。
echo.

powershell -NoProfile -Command ^
  "$ports=8787; $targets=@(Get-NetTCPConnection -State Listen -LocalPort $ports -ErrorAction SilentlyContinue | ForEach-Object { Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue } | Where-Object { $_.ProcessName -match '^python(w)?$' } | Sort-Object Id -Unique);" ^
  "if (-not $targets) { Write-Host '[提示] 没有找到监听 8787 的 Python 进程。'; exit 0 };" ^
  "Write-Host '将停止以下进程：'; $targets | Format-Table Id,ProcessName,Path -AutoSize;" ^
  "$answer=Read-Host '确认停止？输入 Y 继续'; if ($answer -notmatch '^[Yy]$') { Write-Host '已取消。'; exit 2 };" ^
  "$targets | Stop-Process -ErrorAction Stop; Write-Host '筑思 Agent 服务已停止。'"

if errorlevel 2 (
    pause
    exit /b 2
)
if errorlevel 1 (
    echo  [错误] 停止服务时出现问题，请查看上方信息。
    pause
    exit /b 1
)

pause
exit /b 0
