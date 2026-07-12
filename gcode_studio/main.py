#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Точка входа G-Code Studio.
"""
import sys
import os

# ВАЖНО: добавляем КОРЕНЬ проекта (родительскую папку gcode_studio)
# а не саму папку gcode_studio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def resource_path(relative_path):
    """Получить абсолютный путь к ресурсу (работает и в EXE, и в разработке)"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


import tkinter as tk
# ✅ Импортируем через имя пакета
from gcode_studio.controller import GCodeStudio


def main():
    """Запуск приложения G-Code Studio."""
    root = tk.Tk()
    app = GCodeStudio(root)
    root.mainloop()


if __name__ == "__main__":
    main()