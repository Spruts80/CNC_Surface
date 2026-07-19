"""
Парсер G-кода.
"""
import re
from typing import List, Tuple
from .models import GCodePoint


class GCodeParser:
    def parse_file(self, filepath: str) -> Tuple[List[GCodePoint], List[str]]:
        points: List[GCodePoint] = []
        lines: List[str] = []
        x, y, z = 0.0, 0.0, 0.0
        rapid = False
        line_num = 0

        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line_num += 1
                    lines.append(line.rstrip('\n'))
                    stripped = line.strip()
                    if not stripped or stripped.startswith('%') or stripped.startswith('O') or stripped.startswith('('):
                        continue
                    if 'G0' in stripped:
                        rapid = True
                    elif 'G1' in stripped:
                        rapid = False
                    xm = re.search(r'X([-+]?\d*\.?\d+)', stripped)
                    ym = re.search(r'Y([-+]?\d*\.?\d+)', stripped)
                    zm = re.search(r'Z([-+]?\d*\.?\d+)', stripped)
                    if xm:
                        x = float(xm.group(1))
                    if ym:
                        y = float(ym.group(1))
                    if zm:
                        z = float(zm.group(1))
                    if xm or ym or zm:
                        points.append(GCodePoint(x, y, z, rapid, line_num))
        except IOError as e:
            raise IOError(f"Не удалось прочитать файл {filepath}: {e}") from e

        return points, lines