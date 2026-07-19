"""
Модели данных G-Code Studio.
"""
from dataclasses import dataclass

@dataclass
class MillingParams:
    x_min: float = 0.0
    x_max: float = 280.0
    y_min: float = 0.0
    y_max: float = 380.0
    tool_diameter: float = 6.0
    stepover: float = 3.0
    z_start: float = 0.0
    z_end: float = -0.6
    z_step: float = 0.05
    safe_z: float = 25.0
    feed_xy: int = 800
    feed_z: int = 80
    rapid_feed: int = 5000
    tool_number: int = 2
    spindle_speed: int = 4000
    passes_per_file: int = 5
    milling_type: str = "zigzag_x"
    milling_direction: str = "climb"
    contour_direction: str = "outside_in"
    allowance: float = 0.0
    backtrack_enabled: bool = False

@dataclass
class GCodePoint:
    x: float
    y: float
    z: float
    rapid: bool = False
    line_number: int = 0