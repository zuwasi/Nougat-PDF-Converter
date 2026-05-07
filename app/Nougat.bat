@echo off
REM Launches the Nougat GUI. Uses pythonw.exe from a venv at ..\venv\
REM (installer layout) or falls back to C:\nougat-env (dev layout).
setlocal
set "APP_DIR=%~dp0"

if exist "%APP_DIR%..\venv\Scripts\pythonw.exe" (
    set "PYW=%APP_DIR%..\venv\Scripts\pythonw.exe"
) else if exist "C:\nougat-env\Scripts\pythonw.exe" (
    set "PYW=C:\nougat-env\Scripts\pythonw.exe"
) else (
    echo ERROR: Could not find a Nougat venv.
    echo Expected: %APP_DIR%..\venv\Scripts\pythonw.exe
    echo      or: C:\nougat-env\Scripts\pythonw.exe
    pause
    exit /b 1
)

start "" "%PYW%" "%APP_DIR%nougat_app.py"
endlocal
