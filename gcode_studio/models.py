"""
Модели данных G-Code Studio.

Содержит структуры данных для параметров фрезерования
и точек траектории G-кода.
"""

from dataclasses import dataclass
# gcode_studio/models.py
from .config import (
    DEFAULT_X_MIN, DEFAULT_X_MAX, DEFAULT_Y_MIN, DEFAULT_Y_MAX,
    DEFAULT_TOOL_DIAMETER, DEFAULT_STEPOVER, DEFAULT_Z_START,
    DEFAULT_Z_END, DEFAULT_Z_STEP, DEFAULT_SAFE_Z,
    DEFAULT_FEED_XY, DEFAULT_FEED_Z, DEFAULT_TOOL_NUMBER,
    DEFAULT_SPINDLE_SPEED, DEFAULT_PASSES_PER_FILE,
    DEFAULT_MILLING_TYPE, DEFAULT_MILLING_DIRECTION,
    DEFAULT_CONTOUR_DIRECTION, DEFAULT_ALLOWANCE,
)


@dataclass
class MillingParams:
    """Параметры фрезерования.

    Атрибуты:
        x_min: Минимальная координата X поля обработки (мм)
        x_max: Максимальная координата X поля обработки (мм)
        y_min: Минимальная координата Y поля обработки (мм)
        y_max: Максимальная координата Y поля обработки (мм)
        tool_diameter: Диаметр фрезы (мм)
        stepover: Шаг между проходами (мм)
        z_start: Начальная глубина обработки (мм)
        z_end: Конечная глубина обработки (мм)
        z_step: Шаг заглубления по Z (мм)
        safe_z: Безопасная высота Z (мм)
        feed_xy: Подача по XY (мм/мин)
        feed_z: Подача по Z (мм/мин)
        tool_number: Номер инструмента
        spindle_speed: Обороты шпинделя (об/мин)
        passes_per_file: Количество проходов в одном файле
        milling_type: Тип обработки (zigzag_x, zigzag_y, center_spiral, contour)
        milling_direction: Направление фрезерования (climb, conventional)
        contour_direction: Направление контурной обработки (outside_in, inside_out)
        allowance: Припуск — выход фрезы за границы поля (мм)
    """
    x_min: float = DEFAULT_X_MIN
    x_max: float = DEFAULT_X_MAX
    y_min: float = DEFAULT_Y_MIN
    y_max: float = DEFAULT_Y_MAX
    tool_diameter: float = DEFAULT_TOOL_DIAMETER
    stepover: float = DEFAULT_STEPOVER
    z_start: float = DEFAULT_Z_START
    z_end: float = DEFAULT_Z_END
    z_step: float = DEFAULT_Z_STEP
    safe_z: float = DEFAULT_SAFE_Z
    feed_xy: int = DEFAULT_FEED_XY
    feed_z: int = DEFAULT_FEED_Z
    tool_number: int = DEFAULT_TOOL_NUMBER
    spindle_speed: int = DEFAULT_SPINDLE_SPEED
    passes_per_file: int = DEFAULT_PASSES_PER_FILE
    milling_type: str = DEFAULT_MILLING_TYPE
    milling_direction: str = DEFAULT_MILLING_DIRECTION
    contour_direction: str = DEFAULT_CONTOUR_DIRECTION
    allowance: float = DEFAULT_ALLOWANCE


@dataclass
class GCodePoint:
    """Точка траектории G-кода.

    Атрибуты:
        x: Координата X (мм)
        y: Координата Y (мм)
        z: Координата Z (мм)
        rapid: True если это холостое перемещение (G0), False если рабочий ход (G1)
        line_number: Номер строки в исходном файле G-кода
    """
    x: float
    y: float
    z: float
    rapid: bool = False
    line_number: int = 0