"""
G-Code Studio — Генератор и визуализатор G-кода для ЧПУ.
"""

__version__ = "1.0.0"
__author__ = "G-Code Studio Team"

# Экспортируем основные классы для удобства
from .controller import GCodeStudio
from .models import MillingParams, GCodePoint
from .generator import GCodeGenerator
from .parser import GCodeParser