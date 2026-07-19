"""
Генератор G-кода для различных стратегий фрезерования.
"""
import os
from datetime import datetime
from typing import List, Tuple

from .models import MillingParams
from .config import (
    GCODE_EPSILON, GCODE_CENTER_EPSILON, GCODE_Z_PRECISION,
    GCODE_COORD_PRECISION, GCODE_LINE_NUM_STEP,
    GCODE_FILE_START, GCODE_FILE_END, GCODE_PROGRAM_END,
    GCODE_INIT_LINES, GCODE_TOOL_CHANGE_FMT, GCODE_SPINDLE_ON_FMT,
    GCODE_COOLANT_ON, GCODE_SAFE_Z_FMT, GCODE_RETRACT_FMT,
    GCODE_HOME_FMT, GCODE_PROGRAM_NUM_START, GCODE_LINE_NUM_START,
    FILE_PREFIX, FILE_EXTENSION,
    HEADER_SEPARATOR, HEADER_TITLE, HEADER_LABEL_DATE,
    HEADER_LABEL_FILE, HEADER_LABEL_FILE_OF, HEADER_LABEL_TYPE,
    HEADER_LABEL_DIRECTION, HEADER_LABEL_CONTOUR_DIR,
    HEADER_LABEL_FIELD, HEADER_LABEL_X_RANGE, HEADER_LABEL_Y_RANGE,
    HEADER_LABEL_MM, HEADER_LABEL_TOOL, HEADER_LABEL_TOOL_NUM,
    HEADER_LABEL_DIAMETER, HEADER_LABEL_STEPOVER, HEADER_LABEL_OVERLAP,
    HEADER_LABEL_PERCENT, HEADER_LABEL_DEPTH, HEADER_LABEL_Z_START,
    HEADER_LABEL_Z_END, HEADER_LABEL_Z_STEP, HEADER_LABEL_SAFE_Z,
    HEADER_LABEL_PASSES, HEADER_LABEL_MODES, HEADER_LABEL_FEED_XY,
    HEADER_LABEL_FEED_Z, HEADER_LABEL_SPEED, HEADER_LABEL_RPM,
    HEADER_LABEL_MM_MIN, HEADER_LABEL_Z_LEVELS, HEADER_LABEL_Z_VALUE,
    HEADER_LABEL_RAPID_FEED, HEADER_LABEL_ALLOWANCE, HEADER_LABEL_BACKTRACK,
    HEADER_DATE_FORMAT,
)


class GCodeGenerator:
    def __init__(self, params: MillingParams):
        self.params = params
        self.generated_files: List[str] = []

    def calculate_overlap_percent(self) -> float:
        if self.params.tool_diameter <= 0:
            return 0.0
        return (self.params.tool_diameter - self.params.stepover) / self.params.tool_diameter * 100

    def validate_params(self) -> Tuple[bool, str]:
        p = self.params
        if p.x_min >= p.x_max:
            return False, "X_MIN >= X_MAX"
        if p.y_min >= p.y_max:
            return False, "Y_MIN >= Y_MAX"
        if p.z_start <= p.z_end:
            return False, "Z_START <= Z_END"
        if p.z_step <= 0:
            return False, "Z_STEP <= 0"
        if p.stepover <= 0:
            return False, "STEPOVER <= 0"
        if p.stepover > p.tool_diameter:
            return False, "STEPOVER > diameter"
        if p.safe_z <= p.z_start:
            return False, "SAFE_Z <= Z_START"
        return True, "OK"

    def generate_to_files(self, output_dir: str) -> Tuple[bool, List[str]]:
        self.generated_files = []
        valid, _ = self.validate_params()
        if not valid:
            return False, []

        z_levels = []
        z = self.params.z_start
        while z >= self.params.z_end - GCODE_EPSILON:
            z_levels.append(round(z, 4))
            z -= self.params.z_step
        if not z_levels:
            return False, []

        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError:
            return False, []

        passes_per_file = max(1, self.params.passes_per_file)
        file_num = 1
        total_files = (len(z_levels) + passes_per_file - 1) // passes_per_file

        for i in range(0, len(z_levels), passes_per_file):
            chunk = z_levels[i:i + passes_per_file]
            if not chunk:
                continue
            milling_type = self.params.milling_type
            if milling_type == "contour":
                direction = self.params.contour_direction
                filename = f"{FILE_PREFIX}_{milling_type}_{direction}_p{file_num}{FILE_EXTENSION}"
            else:
                filename = f"{FILE_PREFIX}_{milling_type}_p{file_num}{FILE_EXTENSION}"

            header = self._generate_header(chunk, file_num, total_files)

            file_lines = [GCODE_FILE_START] + header + [
                f"O{GCODE_PROGRAM_NUM_START + file_num}",
            ] + GCODE_INIT_LINES + [
                GCODE_TOOL_CHANGE_FMT.format(tool=self.params.tool_number),
                GCODE_SPINDLE_ON_FMT.format(speed=self.params.spindle_speed),
                GCODE_COOLANT_ON,
            ]

            line_num = GCODE_LINE_NUM_START

            for z_level in chunk:
                file_lines.append(GCODE_SAFE_Z_FMT.format(ln=line_num, z=self.params.safe_z))
                line_num += GCODE_LINE_NUM_STEP

                if self.params.milling_type == "zigzag_x":
                    layer, line_num = self._zigzag_x(z_level, line_num)
                elif self.params.milling_type == "zigzag_y":
                    layer, line_num = self._zigzag_y(z_level, line_num)
                elif self.params.milling_type == "center_spiral":
                    layer, line_num = self._center_spiral(z_level, line_num)
                elif self.params.milling_type == "contour":
                    layer, line_num = self._contour(z_level, line_num)
                else:
                    layer = []

                file_lines.extend(layer)

            file_lines.extend([
                GCODE_SAFE_Z_FMT.format(ln=line_num, z=self.params.safe_z),
                GCODE_RETRACT_FMT.format(ln=line_num + GCODE_LINE_NUM_STEP),
                GCODE_HOME_FMT.format(ln=line_num + GCODE_LINE_NUM_STEP * 2),
                GCODE_PROGRAM_END,
                GCODE_FILE_END,
            ])

            filepath = os.path.join(output_dir, filename)
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(file_lines))
                self.generated_files.append(filepath)
            except IOError:
                return False, self.generated_files

            file_num += 1

        return True, self.generated_files

    def _generate_header(self, z_levels: List[float], file_num: int, total_files: int) -> List[str]:
        h = []
        h.append(HEADER_SEPARATOR)
        h.append(HEADER_TITLE)
        h.append(f"{HEADER_LABEL_DATE}{datetime.now().strftime(HEADER_DATE_FORMAT)}")
        h.append(f"{HEADER_LABEL_FILE}{file_num}{HEADER_LABEL_FILE_OF}{total_files}")
        h.append(HEADER_SEPARATOR)
        h.append("")
        h.append(f"{HEADER_LABEL_TYPE}{self.params.milling_type}")
        h.append(f"{HEADER_LABEL_DIRECTION}{self.params.milling_direction}")

        if self.params.milling_type == "contour":
            h.append(f"{HEADER_LABEL_CONTOUR_DIR}{self.params.contour_direction}")

        h.append("")
        h.append(HEADER_LABEL_FIELD)
        h.append(f"{HEADER_LABEL_X_RANGE}{self.params.x_min} ... {self.params.x_max}{HEADER_LABEL_MM}")
        h.append(f"{HEADER_LABEL_Y_RANGE}{self.params.y_min} ... {self.params.y_max}{HEADER_LABEL_MM}")
        h.append("")
        h.append(HEADER_LABEL_TOOL)
        h.append(f"{HEADER_LABEL_TOOL_NUM}{self.params.tool_number}")
        h.append(f"{HEADER_LABEL_DIAMETER}{self.params.tool_diameter}{HEADER_LABEL_MM}")
        h.append(f"{HEADER_LABEL_STEPOVER}{self.params.stepover}{HEADER_LABEL_MM}")
        h.append(f"{HEADER_LABEL_OVERLAP}{self.calculate_overlap_percent():.1f}{HEADER_LABEL_PERCENT}")
        h.append("")
        h.append(HEADER_LABEL_DEPTH)
        h.append(f"{HEADER_LABEL_Z_START}{self.params.z_start}{HEADER_LABEL_MM}")
        h.append(f"{HEADER_LABEL_Z_END}{self.params.z_end}{HEADER_LABEL_MM}")
        h.append(f"{HEADER_LABEL_Z_STEP}{self.params.z_step}{HEADER_LABEL_MM}")
        h.append(f"{HEADER_LABEL_SAFE_Z}{self.params.safe_z}{HEADER_LABEL_MM}")
        h.append(f"{HEADER_LABEL_PASSES}{len(z_levels)}")
        h.append("")
        h.append(HEADER_LABEL_MODES)
        h.append(f"{HEADER_LABEL_FEED_XY}{self.params.feed_xy}{HEADER_LABEL_MM_MIN}")
        h.append(f"{HEADER_LABEL_FEED_Z}{self.params.feed_z}{HEADER_LABEL_MM_MIN}")
        h.append(f"{HEADER_LABEL_RAPID_FEED}{self.params.rapid_feed}{HEADER_LABEL_MM_MIN}")
        h.append(f"{HEADER_LABEL_SPEED}{self.params.spindle_speed}{HEADER_LABEL_RPM}")
        h.append("")
        h.append(f"{HEADER_LABEL_ALLOWANCE}{self.params.allowance}{HEADER_LABEL_MM}")
        if self.params.milling_type in ("zigzag_x", "zigzag_y"):
            h.append(f"{HEADER_LABEL_BACKTRACK}{'Включён' if self.params.backtrack_enabled else 'Выключен'}")
        h.append("")
        h.append(HEADER_LABEL_Z_LEVELS)
        for z_val in z_levels:
            h.append(f"{HEADER_LABEL_Z_VALUE}{z_val:.3f}{HEADER_LABEL_MM}")
        h.append("")
        h.append(HEADER_SEPARATOR)
        h.append("")
        return h

    def _zigzag_x(self, z: float, ln: int) -> Tuple[List[str], int]:
        lines = []
        p = self.params
        x_start = p.x_min - p.allowance
        x_end = p.x_max + p.allowance
        y_start = p.y_min - p.allowance
        y_end = p.y_max + p.allowance
        is_climb = (p.milling_direction == "climb")

        if p.backtrack_enabled:
            if is_climb:
                lines.append(f"N{ln} G0 X{x_end:.{GCODE_COORD_PRECISION}f} Y{y_end:.{GCODE_COORD_PRECISION}f}")
            else:
                lines.append(f"N{ln} G0 X{x_start:.{GCODE_COORD_PRECISION}f} Y{y_end:.{GCODE_COORD_PRECISION}f}")
            ln += GCODE_LINE_NUM_STEP
            lines.append(f"N{ln} G1 Z{z:.{GCODE_Z_PRECISION}f} F{p.feed_z}")
            ln += GCODE_LINE_NUM_STEP
            y = y_end
            while y >= y_start - GCODE_EPSILON:
                if is_climb:
                    lines.append(f"N{ln} G1 X{x_start:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                else:
                    lines.append(f"N{ln} G1 X{x_end:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                ln += GCODE_LINE_NUM_STEP
                y -= p.stepover
                if y >= y_start - GCODE_EPSILON:
                    lines.append(f"N{ln} G0 Z{p.safe_z:.1f}")
                    ln += GCODE_LINE_NUM_STEP
                    if is_climb:
                        lines.append(f"N{ln} G0 X{x_end:.{GCODE_COORD_PRECISION}f} Y{y:.{GCODE_COORD_PRECISION}f}")
                    else:
                        lines.append(f"N{ln} G0 X{x_start:.{GCODE_COORD_PRECISION}f} Y{y:.{GCODE_COORD_PRECISION}f}")
                    ln += GCODE_LINE_NUM_STEP
                    lines.append(f"N{ln} G1 Z{z:.{GCODE_Z_PRECISION}f} F{p.feed_z}")
                    ln += GCODE_LINE_NUM_STEP
        else:
            if is_climb:
                lines.append(f"N{ln} G0 X{x_end:.{GCODE_COORD_PRECISION}f} Y{y_end:.{GCODE_COORD_PRECISION}f}")
            else:
                lines.append(f"N{ln} G0 X{x_start:.{GCODE_COORD_PRECISION}f} Y{y_end:.{GCODE_COORD_PRECISION}f}")
            ln += GCODE_LINE_NUM_STEP
            lines.append(f"N{ln} G1 Z{z:.{GCODE_Z_PRECISION}f} F{p.feed_z}")
            ln += GCODE_LINE_NUM_STEP
            y = y_end
            gr = is_climb
            while y >= y_start - GCODE_EPSILON:
                target_x = x_start if gr else x_end
                lines.append(f"N{ln} G1 X{target_x:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                ln += GCODE_LINE_NUM_STEP
                y -= p.stepover
                if y >= y_start - GCODE_EPSILON:
                    lines.append(f"N{ln} G1 Y{y:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                gr = not gr
        return lines, ln

    def _zigzag_y(self, z: float, ln: int) -> Tuple[List[str], int]:
        lines = []
        p = self.params
        x_start = p.x_min - p.allowance
        x_end = p.x_max + p.allowance
        y_start = p.y_min - p.allowance
        y_end = p.y_max + p.allowance
        is_climb = (p.milling_direction == "climb")

        if p.backtrack_enabled:
            if is_climb:
                lines.append(f"N{ln} G0 X{x_start:.{GCODE_COORD_PRECISION}f} Y{y_end:.{GCODE_COORD_PRECISION}f}")
            else:
                lines.append(f"N{ln} G0 X{x_start:.{GCODE_COORD_PRECISION}f} Y{y_start:.{GCODE_COORD_PRECISION}f}")
            ln += GCODE_LINE_NUM_STEP
            lines.append(f"N{ln} G1 Z{z:.{GCODE_Z_PRECISION}f} F{p.feed_z}")
            ln += GCODE_LINE_NUM_STEP
            x = x_start
            while x <= x_end + GCODE_EPSILON:
                if is_climb:
                    lines.append(f"N{ln} G1 Y{y_start:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                else:
                    lines.append(f"N{ln} G1 Y{y_end:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                ln += GCODE_LINE_NUM_STEP
                x += p.stepover
                if x <= x_end + GCODE_EPSILON:
                    lines.append(f"N{ln} G0 Z{p.safe_z:.1f}")
                    ln += GCODE_LINE_NUM_STEP
                    if is_climb:
                        lines.append(f"N{ln} G0 X{x:.{GCODE_COORD_PRECISION}f} Y{y_end:.{GCODE_COORD_PRECISION}f}")
                    else:
                        lines.append(f"N{ln} G0 X{x:.{GCODE_COORD_PRECISION}f} Y{y_start:.{GCODE_COORD_PRECISION}f}")
                    ln += GCODE_LINE_NUM_STEP
                    lines.append(f"N{ln} G1 Z{z:.{GCODE_Z_PRECISION}f} F{p.feed_z}")
                    ln += GCODE_LINE_NUM_STEP
        else:
            if is_climb:
                lines.append(f"N{ln} G0 X{x_start:.{GCODE_COORD_PRECISION}f} Y{y_end:.{GCODE_COORD_PRECISION}f}")
            else:
                lines.append(f"N{ln} G0 X{x_start:.{GCODE_COORD_PRECISION}f} Y{y_start:.{GCODE_COORD_PRECISION}f}")
            ln += GCODE_LINE_NUM_STEP
            lines.append(f"N{ln} G1 Z{z:.{GCODE_Z_PRECISION}f} F{p.feed_z}")
            ln += GCODE_LINE_NUM_STEP
            x = x_start
            gu = is_climb
            while x <= x_end + GCODE_EPSILON:
                target_y = y_start if gu else y_end
                lines.append(f"N{ln} G1 Y{target_y:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                ln += GCODE_LINE_NUM_STEP
                x += p.stepover
                if x <= x_end + GCODE_EPSILON:
                    lines.append(f"N{ln} G1 X{x:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                gu = not gu
        return lines, ln

    def _center_spiral(self, z: float, ln: int) -> Tuple[List[str], int]:
        lines = []
        p = self.params
        cx = (p.x_min + p.x_max) / 2
        cy = (p.y_min + p.y_max) / 2
        is_climb = (p.milling_direction == "climb")
        x_left = p.x_min - p.allowance
        x_right = p.x_max + p.allowance
        y_bottom = p.y_min - p.allowance
        y_top = p.y_max + p.allowance

        if p.contour_direction == "outside_in":
            if is_climb:
                current_x = x_left
                lines.append(f"N{ln} G0 X{x_left:.{GCODE_COORD_PRECISION}f} Y{y_bottom:.{GCODE_COORD_PRECISION}f}")
            else:
                current_x = x_right
                lines.append(f"N{ln} G0 X{x_right:.{GCODE_COORD_PRECISION}f} Y{y_bottom:.{GCODE_COORD_PRECISION}f}")
            ln += GCODE_LINE_NUM_STEP
            lines.append(f"N{ln} G1 Z{z:.{GCODE_Z_PRECISION}f} F{p.feed_z}")
            ln += GCODE_LINE_NUM_STEP
            y = y_bottom
            going_right = is_climb
            while y <= cy - GCODE_EPSILON:
                lines.append(f"N{ln} G1 Y{y:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                ln += GCODE_LINE_NUM_STEP
                target_x = x_right if going_right else x_left
                if abs(current_x - target_x) > GCODE_CENTER_EPSILON:
                    lines.append(f"N{ln} G1 X{target_x:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                    current_x = target_x
                y += p.stepover
                going_right = not going_right
            lines.append(f"N{ln} G0 Z{p.safe_z:.1f}")
            ln += GCODE_LINE_NUM_STEP
            start_x = x_right if going_right else x_left
            lines.append(f"N{ln} G0 X{start_x:.{GCODE_COORD_PRECISION}f} Y{y_top:.{GCODE_COORD_PRECISION}f}")
            ln += GCODE_LINE_NUM_STEP
            current_x = start_x
            lines.append(f"N{ln} G1 Z{z:.{GCODE_Z_PRECISION}f} F{p.feed_z}")
            ln += GCODE_LINE_NUM_STEP
            y = y_top
            going_left = not is_climb
            while y >= cy + GCODE_EPSILON:
                target_x = x_left if going_left else x_right
                if abs(current_x - target_x) > GCODE_CENTER_EPSILON:
                    lines.append(f"N{ln} G1 X{target_x:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                    current_x = target_x
                lines.append(f"N{ln} G1 Y{y:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                ln += GCODE_LINE_NUM_STEP
                y -= p.stepover
                going_left = not going_left
        else:
            if is_climb:
                current_x = x_left
                lines.append(f"N{ln} G0 X{x_left:.{GCODE_COORD_PRECISION}f} Y{cy:.{GCODE_COORD_PRECISION}f}")
            else:
                current_x = x_right
                lines.append(f"N{ln} G0 X{x_right:.{GCODE_COORD_PRECISION}f} Y{cy:.{GCODE_COORD_PRECISION}f}")
            ln += GCODE_LINE_NUM_STEP
            lines.append(f"N{ln} G1 Z{z:.{GCODE_Z_PRECISION}f} F{p.feed_z}")
            ln += GCODE_LINE_NUM_STEP
            if is_climb:
                lines.append(f"N{ln} G1 X{x_right:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                ln += GCODE_LINE_NUM_STEP
                current_x = x_right
            else:
                lines.append(f"N{ln} G1 X{x_left:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                ln += GCODE_LINE_NUM_STEP
                current_x = x_left
            y = cy + p.stepover
            going_left = is_climb
            while y <= y_top + GCODE_EPSILON:
                lines.append(f"N{ln} G1 Y{y:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                ln += GCODE_LINE_NUM_STEP
                target_x = x_left if going_left else x_right
                if abs(current_x - target_x) > GCODE_CENTER_EPSILON:
                    lines.append(f"N{ln} G1 X{target_x:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                    current_x = target_x
                y += p.stepover
                going_left = not going_left
            lines.append(f"N{ln} G0 Z{p.safe_z:.1f}")
            ln += GCODE_LINE_NUM_STEP
            start_x = x_left if going_left else x_right
            start_y = cy - p.stepover
            lines.append(f"N{ln} G0 X{start_x:.{GCODE_COORD_PRECISION}f} Y{start_y:.{GCODE_COORD_PRECISION}f}")
            ln += GCODE_LINE_NUM_STEP
            current_x = start_x
            lines.append(f"N{ln} G1 Z{z:.{GCODE_Z_PRECISION}f} F{p.feed_z}")
            ln += GCODE_LINE_NUM_STEP
            y = cy - p.stepover
            going_right = not is_climb
            while y >= y_bottom - GCODE_EPSILON:
                target_x = x_right if going_right else x_left
                if abs(current_x - target_x) > GCODE_CENTER_EPSILON:
                    lines.append(f"N{ln} G1 X{target_x:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                    current_x = target_x
                lines.append(f"N{ln} G1 Y{y:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                ln += GCODE_LINE_NUM_STEP
                y -= p.stepover
                going_right = not going_right
        return lines, ln

    def _contour(self, z: float, ln: int) -> Tuple[List[str], int]:
        lines = []
        p = self.params
        r = p.tool_diameter / 2
        is_climb = (p.milling_direction == "climb")

        if p.contour_direction == "outside_in":
            x1 = p.x_min + r - p.allowance
            y1 = p.y_min + r - p.allowance
            x2 = p.x_max - r + p.allowance
            y2 = p.y_max - r + p.allowance
            if is_climb:
                lines.append(f"N{ln} G0 X{x1:.{GCODE_COORD_PRECISION}f} Y{y1:.{GCODE_COORD_PRECISION}f}")
            else:
                lines.append(f"N{ln} G0 X{x1:.{GCODE_COORD_PRECISION}f} Y{y1:.{GCODE_COORD_PRECISION}f}")
            ln += GCODE_LINE_NUM_STEP
            lines.append(f"N{ln} G1 Z{z:.{GCODE_Z_PRECISION}f} F{p.feed_z}")
            ln += GCODE_LINE_NUM_STEP
            while (x2 - x1) > GCODE_EPSILON and (y2 - y1) > GCODE_EPSILON:
                if (x2 - x1) < p.tool_diameter or (y2 - y1) < p.tool_diameter:
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2
                    if (x2 - x1) < p.tool_diameter:
                        lines.append(f"N{ln} G1 X{center_x:.{GCODE_COORD_PRECISION}f} Y{y1:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                        ln += GCODE_LINE_NUM_STEP
                        lines.append(f"N{ln} G1 X{center_x:.{GCODE_COORD_PRECISION}f} Y{y2:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                        ln += GCODE_LINE_NUM_STEP
                    else:
                        lines.append(f"N{ln} G1 X{x1:.{GCODE_COORD_PRECISION}f} Y{center_y:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                        ln += GCODE_LINE_NUM_STEP
                        lines.append(f"N{ln} G1 X{x2:.{GCODE_COORD_PRECISION}f} Y{center_y:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                        ln += GCODE_LINE_NUM_STEP
                    break
                if is_climb:
                    lines.append(f"N{ln} G1 X{x2:.{GCODE_COORD_PRECISION}f} Y{y1:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                    lines.append(f"N{ln} G1 X{x2:.{GCODE_COORD_PRECISION}f} Y{y2:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                    lines.append(f"N{ln} G1 X{x1:.{GCODE_COORD_PRECISION}f} Y{y2:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                    lines.append(f"N{ln} G1 X{x1:.{GCODE_COORD_PRECISION}f} Y{y1:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                else:
                    lines.append(f"N{ln} G1 X{x1:.{GCODE_COORD_PRECISION}f} Y{y2:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                    lines.append(f"N{ln} G1 X{x2:.{GCODE_COORD_PRECISION}f} Y{y2:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                    lines.append(f"N{ln} G1 X{x2:.{GCODE_COORD_PRECISION}f} Y{y1:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                    lines.append(f"N{ln} G1 X{x1:.{GCODE_COORD_PRECISION}f} Y{y1:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                x1 += p.stepover
                y1 += p.stepover
                x2 -= p.stepover
                y2 -= p.stepover
        else:
            cx = (p.x_min + p.x_max) / 2
            cy = (p.y_min + p.y_max) / 2
            x1 = cx - p.stepover / 2
            y1 = cy - p.stepover / 2
            x2 = cx + p.stepover / 2
            y2 = cy + p.stepover / 2
            limit_x1 = p.x_min + r - p.allowance
            limit_y1 = p.y_min + r - p.allowance
            limit_x2 = p.x_max - r + p.allowance
            limit_y2 = p.y_max - r + p.allowance
            lines.append(f"N{ln} G0 X{x1:.{GCODE_COORD_PRECISION}f} Y{y1:.{GCODE_COORD_PRECISION}f}")
            ln += GCODE_LINE_NUM_STEP
            lines.append(f"N{ln} G1 Z{z:.{GCODE_Z_PRECISION}f} F{p.feed_z}")
            ln += GCODE_LINE_NUM_STEP
            while True:
                if is_climb:
                    lines.append(f"N{ln} G1 X{x2:.{GCODE_COORD_PRECISION}f} Y{y1:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                    lines.append(f"N{ln} G1 X{x2:.{GCODE_COORD_PRECISION}f} Y{y2:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                    lines.append(f"N{ln} G1 X{x1:.{GCODE_COORD_PRECISION}f} Y{y2:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                    lines.append(f"N{ln} G1 X{x1:.{GCODE_COORD_PRECISION}f} Y{y1:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                else:
                    lines.append(f"N{ln} G1 X{x1:.{GCODE_COORD_PRECISION}f} Y{y2:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                    lines.append(f"N{ln} G1 X{x2:.{GCODE_COORD_PRECISION}f} Y{y2:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                    lines.append(f"N{ln} G1 X{x2:.{GCODE_COORD_PRECISION}f} Y{y1:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                    lines.append(f"N{ln} G1 X{x1:.{GCODE_COORD_PRECISION}f} Y{y1:.{GCODE_COORD_PRECISION}f} F{p.feed_xy}")
                    ln += GCODE_LINE_NUM_STEP
                if (x1 <= limit_x1 + GCODE_EPSILON and y1 <= limit_y1 + GCODE_EPSILON and
                        x2 >= limit_x2 - GCODE_EPSILON and y2 >= limit_y2 - GCODE_EPSILON):
                    break
                x1 -= p.stepover
                y1 -= p.stepover
                x2 += p.stepover
                y2 += p.stepover
                if x1 < limit_x1:
                    x1 = limit_x1
                if y1 < limit_y1:
                    y1 = limit_y1
                if x2 > limit_x2:
                    x2 = limit_x2
                if y2 > limit_y2:
                    y2 = limit_y2
        return lines, ln