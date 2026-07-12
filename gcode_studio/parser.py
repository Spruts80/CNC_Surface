"""
Парсер G-кода.

Читает файлы G-кода и преобразует их в список точек траектории
для визуализации и анимации. Поддерживает команды G0 (холостой ход)
и G1 (рабочий ход), а также координаты X, Y, Z.
"""

import re
from typing import List, Tuple

from .models import GCodePoint


class GCodeParser:
    """Парсер файлов G-кода.

    Извлекает координаты и типы перемещений из G-кода,
    игнорируя комментарии и служебные строки.
    """

    def parse_file(self, filepath: str) -> Tuple[List[GCodePoint], List[str]]:
        """Парсинг файла G-кода.

        Читает файл построчно, извлекая координаты X, Y, Z
        и определяя тип перемещения (G0/G1).

        Args:
            filepath: Путь к файлу G-кода

        Returns:
            Кортеж (список точек траектории, список строк файла)
        """
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

                    # Пропускаем пустые строки и комментарии
                    if not stripped or stripped.startswith('%') or stripped.startswith('O') or stripped.startswith('('):
                        continue

                    # Определяем тип перемещения
                    if 'G0' in stripped:
                        rapid = True
                    elif 'G1' in stripped:
                        rapid = False

                    # Извлекаем координаты
                    xm = re.search(r'X([-+]?\d*\.?\d+)', stripped)
                    ym = re.search(r'Y([-+]?\d*\.?\d+)', stripped)
                    zm = re.search(r'Z([-+]?\d*\.?\d+)', stripped)

                    if xm:
                        x = float(xm.group(1))
                    if ym:
                        y = float(ym.group(1))
                    if zm:
                        z = float(zm.group(1))

                    # Добавляем точку если есть хотя бы одна координата
                    if xm or ym or zm:
                        points.append(GCodePoint(x, y, z, rapid, line_num))
        except IOError:
            pass

        return points, lines