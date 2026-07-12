@echo off
chcp 65001 >nul
echo ========================================
echo   Building G-Code Studio EXE
echo ========================================
echo.

:: Проверка запуска из корневой папки
if not exist "gcode_studio\main.py" (
    echo ERROR: Cannot find gcode_studio\main.py
    echo Please run this script from the project root folder.
    pause
    exit /b 1
)

:: Сборка
pyinstaller --clean --noconfirm GCodeStudio.spec

echo.
echo ========================================
if exist "dist\GCodeStudio.exe" (
    echo   SUCCESS! File created:
    echo   dist\GCodeStudio.exe
    echo ========================================
) else (
    echo   ERROR! File not created.
    echo ========================================
)
pause