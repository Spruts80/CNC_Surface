Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Сборка G-Code Studio EXE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

pyinstaller --onefile --windowed --name=GCodeStudio --icon=app_icon.ico --add-data "app_icon.ico;." --add-data "gcode_studio;gcode_studio" --collect-all matplotlib --hidden-import=numpy --hidden-import=matplotlib.backends.backend_tkagg --noconfirm --clean gcode_studio\main.py

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan

if (Test-Path "dist\GCodeStudio.exe") {
    Write-Host "  УСПЕХ! Файл создан:" -ForegroundColor Green
    Write-Host "  dist\GCodeStudio.exe" -ForegroundColor Green
} else {
    Write-Host "  ОШИБКА! Файл не создан." -ForegroundColor Red
}

Write-Host "========================================" -ForegroundColor Cyan
Read-Host "Нажмите Enter для выхода"