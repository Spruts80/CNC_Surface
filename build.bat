@echo off
chcp 65001 >nul
pyinstaller --onefile --windowed --name=GCodeStudio --icon=Spruts80.ico --collect-all matplotlib --collect-all pygcode gcode_studio.py
pause
