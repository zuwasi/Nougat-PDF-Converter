@echo off
REM Bootstrap the PowerShell installer with execution-policy bypass.
REM Pass any switches through, e.g.: Install.cmd -PreloadModel -Cpu
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
pause
