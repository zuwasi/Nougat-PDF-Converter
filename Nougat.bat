@echo off
REM Launches the Nougat GUI using the nougat venv's Python (so tkinter + nougat both work).
start "" "C:\nougat-env\Scripts\pythonw.exe" "%~dp0nougat_app.py"
