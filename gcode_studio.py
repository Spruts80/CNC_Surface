#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G-Code Studio - Генератор и Визуализатор G-кода"""
import os
import re
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from dataclasses import dataclass
from typing import List, Tuple, Optional

try:
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.figure import Figure
    from matplotlib.patches import Circle
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


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
    tool_number: int = 2
    spindle_speed: int = 4000
    passes_per_file: int = 5
    milling_type: str = "zigzag_x"
    milling_direction: str = "climb"
    contour_direction: str = "outside_in"


@dataclass
class GCodePoint:
    x: float
    y: float
    z: float
    rapid: bool = False
    line_number: int = 0


class GCodeViewerWindow:
    def __init__(self, parent, filepath: str):
        self.parent = parent
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.content = f.read()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
            return
        self.window = tk.Toplevel(parent)
        self.window.title(f"Просмотр: {self.filename}")
        self.window.geometry("1000x750")
        text_frame = ttk.Frame(self.window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        y_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.text_widget = tk.Text(text_frame, wrap=tk.NONE, font=('Consolas', 10),
                                   yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.text_widget.pack(fill=tk.BOTH, expand=True)
        y_scroll.config(command=self.text_widget.yview)
        x_scroll.config(command=self.text_widget.xview)
        self.text_widget.insert(tk.END, self.content)
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Сохранить как...", command=self._save_as).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Копировать всё", command=self._copy_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Закрыть", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

    def _save_as(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".nc", filetypes=[("G-code", "*.nc"), ("Text", "*.txt")])
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(self.text_widget.get("1.0", tk.END).rstrip('\n'))

    def _copy_all(self):
        self.window.clipboard_clear()
        self.window.clipboard_append(self.text_widget.get("1.0", tk.END).rstrip('\n'))


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
        if p.x_min >= p.x_max: return False, "X_MIN >= X_MAX"
        if p.y_min >= p.y_max: return False, "Y_MIN >= Y_MAX"
        if p.z_start <= p.z_end: return False, "Z_START <= Z_END"
        if p.z_step <= 0: return False, "Z_STEP <= 0"
        if p.stepover <= 0: return False, "STEPOVER <= 0"
        if p.stepover > p.tool_diameter: return False, "STEPOVER > diameter"
        if p.safe_z <= p.z_start: return False, "SAFE_Z <= Z_START"
        return True, "OK"

    def generate_to_files(self, output_dir: str) -> Tuple[bool, List[str]]:
        self.generated_files = []
        valid, msg = self.validate_params()
        if not valid: return False, []
        z_levels = []
        z = self.params.z_start
        while z >= self.params.z_end - 0.0001:
            z_levels.append(round(z, 4))
            z -= self.params.z_step
        if not z_levels: return False, []
        try: os.makedirs(output_dir, exist_ok=True)
        except OSError: return False, []
        passes_per_file = max(1, self.params.passes_per_file)
        file_num = 1
        for i in range(0, len(z_levels), passes_per_file):
            chunk = z_levels[i:i + passes_per_file]
            if not chunk: continue
            file_lines = ["%", f"O{1000 + file_num}", "N5 G0 G40 G49 G80 G21",
                          "N10 G0 G53 Z0", "N15 G0 G53 X0 Y0",
                          f"N20 T{self.params.tool_number} M6",
                          f"N30 S{self.params.spindle_speed} M4", "N35 M8"]
            line_num = 40
            for z_level in chunk:
                file_lines.append(f"N{line_num} G0 Z{self.params.safe_z}"); line_num += 5
                if self.params.milling_type == "zigzag_x":
                    layer, line_num = self._zigzag_x(z_level, line_num)
                elif self.params.milling_type == "zigzag_y":
                    layer, line_num = self._zigzag_y(z_level, line_num)
                elif self.params.milling_type == "center_spiral":
                    layer, line_num = self._center_spiral(z_level, line_num)
                elif self.params.milling_type == "contour":
                    layer, line_num = self._contour(z_level, line_num)
                else: layer = []
                file_lines.extend(layer)
            file_lines.extend([f"N{line_num} G0 Z{self.params.safe_z}",
                               f"N{line_num+5} G0 G53 Z35 M9",
                               f"N{line_num+10} G0 G53 X0 Y0 M5", "M30", "%"])
            filepath = os.path.join(output_dir, f"stol_p{file_num}.nc")
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(file_lines))
                self.generated_files.append(filepath)
            except IOError: return False, self.generated_files
            file_num += 1
        return True, self.generated_files

    def _zigzag_x(self, z, ln):
        """Зигзаг по X: движение вдоль X, шаг по Y"""
        lines = []
        p = self.params
        lines.append(f"N{ln} G0 X{p.x_min} Y{p.y_max}"); ln += 5
        lines.append(f"N{ln} G1 Z{z:.3f} F{p.feed_z}"); ln += 5
        y, gr = p.y_max, (p.milling_direction == "climb")
        while y >= p.y_min - 0.0001:
            lines.append(f"N{ln} G1 X{p.x_max if gr else p.x_min} F{p.feed_xy}"); ln += 5
            y -= p.stepover
            if y >= p.y_min - 0.0001:
                lines.append(f"N{ln} G1 Y{y:.3f} F{p.feed_xy}"); ln += 5
            gr = not gr
        return lines, ln

    def _zigzag_y(self, z, ln):
        """Зигзаг по Y: движение вдоль Y, шаг по X"""
        lines = []
        p = self.params
        lines.append(f"N{ln} G0 X{p.x_min} Y{p.y_min}"); ln += 5
        lines.append(f"N{ln} G1 Z{z:.3f} F{p.feed_z}"); ln += 5
        x, gu = p.x_min, (p.milling_direction == "climb")
        while x <= p.x_max + 0.0001:
            lines.append(f"N{ln} G1 Y{p.y_max if gu else p.y_min} F{p.feed_xy}"); ln += 5
            x += p.stepover
            if x <= p.x_max + 0.0001:
                lines.append(f"N{ln} G1 X{x:.3f} F{p.feed_xy}"); ln += 5
            gu = not gu
        return lines, ln

    def _center_spiral(self, z, ln):
        """От центра змейкой - с полным проходом через центр от края до края"""
        lines = []
        p = self.params
        cx, cy = (p.x_min + p.x_max)/2, (p.y_min + p.y_max)/2
        
        # Отслеживаем текущую позицию фрезы
        current_x = p.x_min
        current_y = cy
        
        # Подход к левому краю на центральной линии
        lines.append(f"N{ln} G0 X{p.x_min:.3f} Y{cy:.3f}")
        ln += 5
        
        # Подход к левому краю на центральной линии
        lines.append(f"N{ln} G0 X{p.x_min:.3f} Y{cy:.3f}")
        ln += 5
        
        # Погружение
        lines.append(f"N{ln} G1 Z{z:.3f} F{p.feed_z}")
        ln += 5
        
        # ПЕРВЫЙ ПРОХОД: полный проход через центр от левого края до правого
        lines.append(f"N{ln} G1 X{p.x_max:.3f} F{p.feed_xy}")
        ln += 5
        current_x = p.x_max
        
        # Зигзаг ВВЕРХ от центра
        y = cy + p.stepover
        going_left = True  # Начинаем с движения влево
        
        while y <= p.y_max + 0.0001:
            # Шаг по Y
            lines.append(f"N{ln} G1 Y{y:.3f} F{p.feed_xy}")
            ln += 5
            current_y = y
            
            # Движение по X (только если нужно!)
            target_x = p.x_min if going_left else p.x_max
            if abs(current_x - target_x) > 0.001:
                lines.append(f"N{ln} G1 X{target_x:.3f} F{p.feed_xy}")
                ln += 5
                current_x = target_x
            
            y += p.stepover
            going_left = not going_left
        
        # Возврат к центральной линии
        lines.append(f"N{ln} G1 Y{cy:.3f} F{p.feed_xy}")
        ln += 5
        current_y = cy
        
        # Определяем, где фреза после возврата
        #num_passes_up = int((p.y_max - cy) / p.stepover)
        #at_left = (num_passes_up % 2 == 1)
        
        # Зигзаг ВНИЗ от центра
        y = cy - p.stepover
        # Фреза на X=0 после последнего прохода вверх, идём вправо
        going_right = True
        
        while y >= p.y_min - 0.0001:
            # Движение по X (только если нужно!)
            target_x = p.x_max if going_right else p.x_min
            if abs(current_x - target_x) > 0.001:
                lines.append(f"N{ln} G1 X{target_x:.3f} F{p.feed_xy}")
                ln += 5
                current_x = target_x
                
            # Шаг по Y
            lines.append(f"N{ln} G1 Y{y:.3f} F{p.feed_xy}")
            ln += 5
            current_y = y
            
            y -= p.stepover
            going_right = not going_right
                   
        return lines, ln

    def _contour(self, z, ln):
        lines = []
        p = self.params
        r = p.tool_diameter / 2 # радиус фрезы = 3 мм
        
        x1, y1 = p.x_min + r, p.y_min + r
        x2, y2 = p.x_max - r, p.y_max - r
        
        lines.append(f"N{ln} G0 X{x1:.3f} Y{y1:.3f}"); ln += 5
        lines.append(f"N{ln} G1 Z{z:.3f} F{p.feed_z}"); ln += 5
        
        while (x2 - x1) > 0.001 and (y2 - y1) > 0.001:
            # Если ширина или высота контура меньше диаметра фрезы —
            # делаем один центральный проход вместо прямоугольника
            if (x2 - x1) < p.tool_diameter or (y2 - y1) < p.tool_diameter:
                # Центр оставшейся области
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
            
                # Определяем, по какой оси делать проход
                if (x2 - x1) < p.tool_diameter:
                    # Область узкая по X — делаем вертикальный проход
                    lines.append(f"N{ln} G1 X{center_x:.3f} Y{y1:.3f} F{p.feed_xy}"); ln += 5
                    lines.append(f"N{ln} G1 X{center_x:.3f} Y{y2:.3f} F{p.feed_xy}"); ln += 5
                else:
                    # Область узкая по Y — делаем горизонтальный проход
                    lines.append(f"N{ln} G1 X{x1:.3f} Y{center_y:.3f} F{p.feed_xy}"); ln += 5
                    lines.append(f"N{ln} G1 X{x2:.3f} Y{center_y:.3f} F{p.feed_xy}"); ln += 5
                break  # Выходим из цикла, центр обработан
            # Обычный прямоугольный контур
            lines.append(f"N{ln} G1 X{x2:.3f} Y{y1:.3f} F{p.feed_xy}"); ln += 5
            lines.append(f"N{ln} G1 X{x2:.3f} Y{y2:.3f} F{p.feed_xy}"); ln += 5
            lines.append(f"N{ln} G1 X{x1:.3f} Y{y2:.3f} F{p.feed_xy}"); ln += 5
            lines.append(f"N{ln} G1 X{x1:.3f} Y{y1:.3f} F{p.feed_xy}"); ln += 5
        
            x1 += p.stepover; y1 += p.stepover
            x2 -= p.stepover; y2 -= p.stepover


           # lines.append(f"N{ln} G1 X{x2:.3f} Y{y1:.3f} F{p.feed_xy}"); ln += 5
           # lines.append(f"N{ln} G1 X{x2:.3f} Y{y2:.3f} F{p.feed_xy}"); ln += 5
           # lines.append(f"N{ln} G1 X{x1:.3f} Y{y2:.3f} F{p.feed_xy}"); ln += 5
           # lines.append(f"N{ln} G1 X{x1:.3f} Y{y1:.3f} F{p.feed_xy}"); ln += 5
           # x1 += p.stepover; y1 += p.stepover; x2 -= p.stepover; y2 -= p.stepover
        return lines, ln


class GCodeParser:
    def parse_file(self, filepath: str) -> Tuple[List[GCodePoint], List[str]]:
        points = []
        lines = []
        x, y, z = 0.0, 0.0, 0.0
        rapid = False
        line_num = 0
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line_num += 1
                    raw_line = line.rstrip('\n')
                    lines.append(raw_line)
                    line = line.strip()
                    if not line or line.startswith('%') or line.startswith('O') or line.startswith('('):
                        continue
                    if 'G0' in line: rapid = True
                    elif 'G1' in line: rapid = False
                    xm = re.search(r'X([-+]?\d*\.?\d+)', line)
                    ym = re.search(r'Y([-+]?\d*\.?\d+)', line)
                    zm = re.search(r'Z([-+]?\d*\.?\d+)', line)
                    if xm: x = float(xm.group(1))
                    if ym: y = float(ym.group(1))
                    if zm: z = float(zm.group(1))
                    if xm or ym or zm:
                        points.append(GCodePoint(x, y, z, rapid, line_num))
        except IOError:
            pass
        return points, lines


class GCodeStudio:
    def __init__(self, root):
        self.root = root
        self.root.title("G-Code Studio - Генератор и Визуализатор")
        self.root.geometry("1400x900")
        self.root.minsize(1100, 700)
        self.params = MillingParams()
        self.generator = GCodeGenerator(self.params)
        self.parser = GCodeParser()
        self.current_points: List[GCodePoint] = []
        self.code_lines: List[str] = []
        self.anim_running = False
        self.anim_paused = False
        self.anim_frame = 0
        self.anim_after_id = None
        self.highlight_tag = "current_line"
        self.view_link_counter = 0
        self.viz_link_counter = 0
        self.view_links = {}
        self.viz_links = {}
        self._setup_ui()

    def _setup_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.generator_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.generator_tab, text="⚙ Генератор")
        self._setup_generator_tab()
        self.viewer_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.viewer_tab, text="👁 Визуализатор")
        self._setup_viewer_tab()

    def _setup_generator_tab(self):
        main_frame = ttk.Frame(self.generator_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X)
        params_frame = ttk.LabelFrame(top_frame, text="Параметры обработки", padding=10)
        params_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        field_frame = ttk.LabelFrame(params_frame, text=" Поле обработки", padding=5)
        field_frame.pack(fill=tk.X, pady=5)
        row = ttk.Frame(field_frame); row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="X мин:", width=10).pack(side=tk.LEFT)
        self.x_min_var = tk.DoubleVar(value=0.0)
        ttk.Entry(row, textvariable=self.x_min_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text="X макс:", width=10).pack(side=tk.LEFT)
        self.x_max_var = tk.DoubleVar(value=280.0)
        ttk.Entry(row, textvariable=self.x_max_var, width=10).pack(side=tk.LEFT, padx=5)
        row = ttk.Frame(field_frame); row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="Y мин:", width=10).pack(side=tk.LEFT)
        self.y_min_var = tk.DoubleVar(value=0.0)
        ttk.Entry(row, textvariable=self.y_min_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text="Y макс:", width=10).pack(side=tk.LEFT)
        self.y_max_var = tk.DoubleVar(value=380.0)
        ttk.Entry(row, textvariable=self.y_max_var, width=10).pack(side=tk.LEFT, padx=5)
        milling_type_frame = ttk.LabelFrame(field_frame, text="Тип обработки", padding=5)
        milling_type_frame.pack(fill=tk.X, pady=5)
        self.milling_type_var = tk.StringVar(value="zigzag_x")
        row = ttk.Frame(milling_type_frame); row.pack(fill=tk.X, pady=2)
        ttk.Radiobutton(row, text="Зигзаг по X", variable=self.milling_type_var, value="zigzag_x").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(row, text="Зигзаг по Y", variable=self.milling_type_var, value="zigzag_y").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(row, text="От центра змейкой", variable=self.milling_type_var, value="center_spiral").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(row, text="Контурное", variable=self.milling_type_var, value="contour").pack(side=tk.LEFT, padx=5)
        direction_frame = ttk.LabelFrame(field_frame, text="Направление фрезерования", padding=5)
        direction_frame.pack(fill=tk.X, pady=5)
        self.milling_direction_var = tk.StringVar(value="climb")
        row = ttk.Frame(direction_frame); row.pack(fill=tk.X, pady=2)
        ttk.Radiobutton(row, text="Попутное (climb)", variable=self.milling_direction_var, value="climb").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(row, text="Встречное (conventional)", variable=self.milling_direction_var, value="conventional").pack(side=tk.LEFT, padx=5)
        contour_direction_frame = ttk.LabelFrame(field_frame, text="Направление контурной обработки", padding=5)
        contour_direction_frame.pack(fill=tk.X, pady=5)
        self.contour_direction_var = tk.StringVar(value="outside_in")
        row = ttk.Frame(contour_direction_frame); row.pack(fill=tk.X, pady=2)
        ttk.Radiobutton(row, text="От края к центру", variable=self.contour_direction_var, value="outside_in").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(row, text="От центра к краю", variable=self.contour_direction_var, value="inside_out").pack(side=tk.LEFT, padx=5)
        tool_frame = ttk.LabelFrame(params_frame, text="🔧 Фреза", padding=5)
        tool_frame.pack(fill=tk.X, pady=5)
        row = ttk.Frame(tool_frame); row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="Диаметр (мм):", width=15).pack(side=tk.LEFT)
        self.tool_diam_var = tk.DoubleVar(value=6.0)
        ttk.Entry(row, textvariable=self.tool_diam_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text="№ инструмента:", width=15).pack(side=tk.LEFT)
        self.tool_num_var = tk.IntVar(value=2)
        ttk.Entry(row, textvariable=self.tool_num_var, width=10).pack(side=tk.LEFT, padx=5)
        row = ttk.Frame(tool_frame); row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="Шаг (stepover):", width=15).pack(side=tk.LEFT)
        self.stepover_var = tk.DoubleVar(value=3.0)
        ttk.Entry(row, textvariable=self.stepover_var, width=10).pack(side=tk.LEFT, padx=5)
        z_frame = ttk.LabelFrame(params_frame, text="📏 Глубина обработки", padding=5)
        z_frame.pack(fill=tk.X, pady=5)
        row = ttk.Frame(z_frame); row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="Z старт:", width=10).pack(side=tk.LEFT)
        self.z_start_var = tk.DoubleVar(value=0.0)
        ttk.Entry(row, textvariable=self.z_start_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text="Z конец:", width=10).pack(side=tk.LEFT)
        self.z_end_var = tk.DoubleVar(value=-0.6)
        ttk.Entry(row, textvariable=self.z_end_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text="Шаг по Z:", width=10).pack(side=tk.LEFT)
        self.z_step_var = tk.DoubleVar(value=0.05)
        ttk.Entry(row, textvariable=self.z_step_var, width=10).pack(side=tk.LEFT, padx=5)
        row = ttk.Frame(z_frame); row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="Безопасная Z:", width=15).pack(side=tk.LEFT)
        self.safe_z_var = tk.DoubleVar(value=25.0)
        ttk.Entry(row, textvariable=self.safe_z_var, width=10).pack(side=tk.LEFT, padx=5)
        feed_frame = ttk.LabelFrame(params_frame, text="⚡ Подачи и скорость", padding=5)
        feed_frame.pack(fill=tk.X, pady=5)
        row = ttk.Frame(feed_frame); row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="Подача XY:", width=15).pack(side=tk.LEFT)
        self.feed_xy_var = tk.IntVar(value=800)
        ttk.Entry(row, textvariable=self.feed_xy_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text="Подача Z:", width=15).pack(side=tk.LEFT)
        self.feed_z_var = tk.IntVar(value=80)
        ttk.Entry(row, textvariable=self.feed_z_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text="Обороты:", width=10).pack(side=tk.LEFT)
        self.spindle_var = tk.IntVar(value=4000)
        ttk.Entry(row, textvariable=self.spindle_var, width=10).pack(side=tk.LEFT, padx=5)
        file_frame = ttk.LabelFrame(params_frame, text=" Разбивка на файлы", padding=5)
        file_frame.pack(fill=tk.X, pady=5)
        row = ttk.Frame(file_frame); row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="Проходов на файл:", width=20).pack(side=tk.LEFT)
        self.passes_var = tk.IntVar(value=5)
        ttk.Entry(row, textvariable=self.passes_var, width=10).pack(side=tk.LEFT, padx=5)
        row = ttk.Frame(file_frame); row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="Папка:", width=10).pack(side=tk.LEFT)
        self.dir_var = tk.StringVar(value=os.path.expanduser("~"))
        ttk.Entry(row, textvariable=self.dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(row, text="📂", command=self._open_output_folder, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="...", command=self._select_dir, width=3).pack(side=tk.LEFT)
        btn_frame = ttk.LabelFrame(top_frame, text="Действия", padding=10)
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        ttk.Button(btn_frame, text=" Проверить параметры", command=self._validate, width=25).pack(pady=5)
        ttk.Button(btn_frame, text="🚀 Генерировать", command=self._generate, width=25).pack(pady=5)
        log_frame = ttk.LabelFrame(main_frame, text="📋 Лог операций", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        log_btn_frame = ttk.Frame(log_frame)
        log_btn_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(log_btn_frame, text="📋 Копировать выделенное", command=self._copy_log_selection).pack(side=tk.LEFT, padx=2)
        ttk.Button(log_btn_frame, text="📋 Копировать весь лог", command=self._copy_all_log).pack(side=tk.LEFT, padx=2)
        ttk.Button(log_btn_frame, text="🗑️ Очистить лог", command=self._clear_log).pack(side=tk.LEFT, padx=2)
        ttk.Button(log_btn_frame, text="💾 Сохранить лог", command=self._save_log_manual).pack(side=tk.LEFT, padx=2)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, font=('Consolas', 10), height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.tag_configure("info", foreground="black")
        self.log_text.tag_configure("success", foreground="green")
        self.log_text.tag_configure("error", foreground="red")
        self.log_text.tag_configure("warning", foreground="orange")
        self.log_text.tag_configure("highlight", foreground="blue", font=('Consolas', 10, 'bold'))
        self._log(" G-Code Studio готов к работе", "info")
        self._log("📋 Заполните параметры и нажмите 'Проверить параметры' или 'Генерировать'", "info")

    def _setup_viewer_tab(self):
        if not MATPLOTLIB_AVAILABLE:
            label = ttk.Label(self.viewer_tab, text="⚠ Matplotlib не установлен!", font=('Arial', 14))
            label.pack(expand=True)
            return
        
        control_frame = ttk.Frame(self.viewer_tab)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(control_frame, text="📂 Открыть файл", command=self._open_file).pack(side=tk.LEFT, padx=5)
        
        anim_frame = ttk.LabelFrame(control_frame, text="🎬 Анимация", padding=5)
        anim_frame.pack(side=tk.LEFT, padx=10)
        
        self.btn_play = ttk.Button(anim_frame, text="▶ Play", command=self._anim_play, width=8)
        self.btn_play.pack(side=tk.LEFT, padx=2)
        
        self.btn_pause = ttk.Button(anim_frame, text="⏸ Пауза", command=self._anim_pause, width=8, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT, padx=2)
        
        self.btn_stop = ttk.Button(anim_frame, text=" Стоп", command=self._anim_stop, width=8, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=2)
        
        speed_frame = ttk.Frame(anim_frame)
        speed_frame.pack(side=tk.LEFT, padx=10)
        ttk.Label(speed_frame, text="Скорость:").pack(side=tk.LEFT)
        self.speed_var = tk.IntVar(value=2)
        ttk.Combobox(speed_frame, textvariable=self.speed_var, values=[1, 2, 5, 10, 20, 50], width=4, state="readonly").pack(side=tk.LEFT, padx=3)
        
        ttk.Label(control_frame, text="Проекция:").pack(side=tk.LEFT, padx=(20, 5))
        self.projection_var = tk.StringVar(value="XY")
        projection_combo = ttk.Combobox(control_frame, textvariable=self.projection_var,
                                        values=["XY", "XZ", "YZ"], state="readonly", width=6)
        projection_combo.pack(side=tk.LEFT)
        projection_combo.bind('<<ComboboxSelected>>', lambda e: self._update_plot())
        
        self.file_label = ttk.Label(control_frame, text="Файл не загружен", foreground="gray")
        self.file_label.pack(side=tk.LEFT, padx=20)
        
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(self.viewer_tab, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, padx=10, pady=2)
        
        self.coord_label = ttk.Label(self.viewer_tab, 
                                      text=" Текущие координаты: X: 0.000  Y: 0.000  Z: 0.000", 
                                      font=('Consolas', 11, 'bold'), foreground='blue')
        self.coord_label.pack(fill=tk.X, padx=10, pady=2)
        
        self.status_label = ttk.Label(self.viewer_tab, text="Статус: Ожидание", foreground='gray')
        self.status_label.pack(fill=tk.X, padx=10, pady=2)
        
        # Разделённая область: график слева, код справа
        content_frame = ttk.Frame(self.viewer_tab)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Левая часть - график
        plot_frame = ttk.Frame(content_frame)
        plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        NavigationToolbar2Tk(self.canvas, plot_frame).update()
        
        # Правая часть - код с подсветкой
        code_frame = ttk.LabelFrame(content_frame, text="📄 G-код (выполняемая строка подсвечивается)", padding=5)
        code_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        code_scroll = ttk.Scrollbar(code_frame, orient=tk.VERTICAL)
        code_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.code_text = tk.Text(code_frame, wrap=tk.NONE, font=('Consolas', 10),
                                 yscrollcommand=code_scroll.set, state=tk.DISABLED,
                                 bg='#1e1e1e', fg='#d4d4d4', insertbackground='white')
        self.code_text.pack(fill=tk.BOTH, expand=True)
        code_scroll.config(command=self.code_text.yview)
        
        self.code_text.tag_configure(self.highlight_tag, background='#264f78', foreground='white')
        
        self.line_info_label = ttk.Label(code_frame, text="Строка: -", foreground='red')
        self.line_info_label.pack(fill=tk.X, pady=(5, 0))

    def _highlight_code_line(self, line_num: int):
        self.code_text.tag_remove(self.highlight_tag, "1.0", tk.END)
        if line_num <= 0 or line_num > len(self.code_lines):
            self.line_info_label.config(text="Строка: -")
            return
        start_idx = f"{line_num}.0"
        end_idx = f"{line_num}.end"
        self.code_text.tag_add(self.highlight_tag, start_idx, end_idx)
        self.code_text.see(start_idx)
        if line_num <= len(self.code_lines):
            line_content = self.code_lines[line_num - 1].strip()
            self.line_info_label.config(text=f"Строка {line_num}: {line_content[:50]}")

    def _display_code(self):
        self.code_text.config(state=tk.NORMAL)
        self.code_text.delete("1.0", tk.END)
        for i, line in enumerate(self.code_lines, 1):
            line_with_num = f"{i:4d} │ {line}\n"
            self.code_text.insert(tk.END, line_with_num)
        self.code_text.config(state=tk.DISABLED)

    def _anim_play(self):
        if not self.current_points:
            messagebox.showwarning("Внимание", "Сначала загрузите G-код файл!")
            return
        if self.anim_paused:
            self.anim_paused = False
            self.anim_running = True
            self.btn_play.config(state=tk.DISABLED)
            self.btn_pause.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.NORMAL)
            self.status_label.config(text="Статус: ▶ Воспроизведение", foreground='green')
            self._animate_step()
            return
        self.anim_frame = 0
        self.anim_running = True
        self.anim_paused = False
        self.btn_play.config(state=tk.DISABLED)
        self.btn_pause.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.NORMAL)
        self.status_label.config(text="Статус: ▶ Воспроизведение", foreground='green')
        self._animate_step()

    def _anim_pause(self):
        self.anim_paused = True
        self.anim_running = False
        if self.anim_after_id:
            self.root.after_cancel(self.anim_after_id)
            self.anim_after_id = None
        self.btn_play.config(state=tk.NORMAL)
        self.btn_pause.config(state=tk.DISABLED)
        self.status_label.config(text="Статус: ⏸ Пауза", foreground='orange')

    def _anim_stop(self):
        self.anim_running = False
        self.anim_paused = False
        if self.anim_after_id:
            self.root.after_cancel(self.anim_after_id)
            self.anim_after_id = None
        self.btn_play.config(state=tk.NORMAL)
        self.btn_pause.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.coord_label.config(text=" Текущие координаты: X: 0.000  Y: 0.000  Z: 0.000")
        self.status_label.config(text="Статус: ⏹ Остановлено", foreground='red')
        self._highlight_code_line(0)
        self._update_plot()

    def _animate_step(self):
        if not self.anim_running:
            return
        speed = self.speed_var.get()
        self.anim_frame = min(self.anim_frame + speed, len(self.current_points))
        end_idx = self.anim_frame
        total = len(self.current_points)
        pct = (end_idx / total * 100) if total > 0 else 0
        self.progress_var.set(pct)
        
        if end_idx > 0 and end_idx <= len(self.current_points):
            cur = self.current_points[end_idx - 1]
            mode = "G0 (Холостой)" if cur.rapid else "G1 (Рабочий)"
            color = 'red' if cur.rapid else 'blue'
            self.coord_label.config(
                text=f"📍 X: {cur.x:.3f}  Y: {cur.y:.3f}  Z: {cur.z:.3f}  |  {mode}",
                foreground=color
            )
            self._highlight_code_line(cur.line_number)
        
        self.ax.clear()
        all_x = [p.x for p in self.current_points]
        all_y = [p.y for p in self.current_points]
        self.ax.plot(all_x, all_y, color='lightgray', linewidth=0.3, alpha=0.5)
        
        passed_x = [p.x for p in self.current_points[:end_idx]]
        passed_y = [p.y for p in self.current_points[:end_idx]]
        if passed_x:
            self.ax.plot(passed_x, passed_y, color='blue', linewidth=1.0, alpha=0.7, label='Траектория')
        
        tool_r = self.params.tool_diameter / 2.0
        step = max(1, len(self.current_points[:end_idx]) // 500)
        for i in range(0, end_idx, step):
            pt = self.current_points[i]
            if not pt.rapid:
                circle = Circle((pt.x, pt.y), tool_r, color='green', alpha=0.15, linewidth=0)
                self.ax.add_patch(circle)
        
        if end_idx > 0:
            cur = self.current_points[end_idx - 1]
            self.ax.plot(cur.x, cur.y, 'ro', markersize=14, zorder=10, label='Фреза')
            tool_circle = Circle((cur.x, cur.y), tool_r, fill=False, color='red', linewidth=1.5, zorder=9)
            self.ax.add_patch(tool_circle)
            self.ax.set_title(f'Анимация обработки | Z={cur.z:.3f} мм')
        
        margin = 20
        self.ax.set_xlim(self.params.x_min - margin, self.params.x_max + margin)
        self.ax.set_ylim(self.params.y_min - margin, self.params.y_max + margin)
        self.ax.set_xlabel('X (мм)')
        self.ax.set_ylabel('Y (мм)')
        self.ax.set_aspect('equal')
        self.ax.grid(True, alpha=0.3)
        self.ax.legend(loc='upper right', fontsize=8)
        self.canvas.draw_idle()
        
        if end_idx >= total:
            self.anim_running = False
            self.btn_play.config(state=tk.NORMAL)
            self.btn_pause.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.DISABLED)
            self.status_label.config(text="Статус: ✅ Завершено", foreground='green')
        else:
            self.anim_after_id = self.root.after(30, self._animate_step)

    def _log(self, message: str, tag: str = "info"):
        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.see(tk.END)

    def _log_file_links(self, filepath: str):
        filename = os.path.basename(filepath)
        self.view_link_counter += 1
        view_tag = f"viewlink_{self.view_link_counter}"
        self.view_links[view_tag] = filepath
        self.viz_link_counter += 1
        viz_tag = f"vizlink_{self.viz_link_counter}"
        self.viz_links[viz_tag] = filepath
        self.log_text.tag_configure(view_tag, foreground="blue", underline=True)
        self.log_text.tag_bind(view_tag, "<Enter>", lambda e: self.log_text.config(cursor="hand2"))
        self.log_text.tag_bind(view_tag, "<Leave>", lambda e: self.log_text.config(cursor=""))
        self.log_text.tag_bind(view_tag, "<Button-1>", lambda e, t=view_tag: self._on_view_link_click(e, t))
        self.log_text.tag_configure(viz_tag, foreground="green", underline=True)
        self.log_text.tag_bind(viz_tag, "<Enter>", lambda e: self.log_text.config(cursor="hand2"))
        self.log_text.tag_bind(viz_tag, "<Leave>", lambda e: self.log_text.config(cursor=""))
        self.log_text.tag_bind(viz_tag, "<Button-1>", lambda e, t=viz_tag: self._on_viz_link_click(e, t))
        self.log_text.insert(tk.END, f"   📄 {filename} — ", "info")
        self.log_text.insert(tk.END, "просмотр", view_tag)
        self.log_text.insert(tk.END, " | ", "info")
        self.log_text.insert(tk.END, "визуализатор", viz_tag)
        self.log_text.insert(tk.END, "\n", "info")
        self.log_text.see(tk.END)

    def _on_view_link_click(self, event, tag_name=None):
        if not tag_name:
            idx = self.log_text.index(f"@{event.x},{event.y}")
            for t in self.log_text.tag_names(idx):
                if t.startswith("viewlink_"): tag_name = t; break
        if tag_name and tag_name in self.view_links:
            self._open_code_viewer(self.view_links[tag_name])

    def _on_viz_link_click(self, event, tag_name=None):
        if not tag_name:
            idx = self.log_text.index(f"@{event.x},{event.y}")
            for t in self.log_text.tag_names(idx):
                if t.startswith("vizlink_"): tag_name = t; break
        if tag_name and tag_name in self.viz_links:
            self._load_file_to_viewer(self.viz_links[tag_name])

    def _open_code_viewer(self, filepath):
        if os.path.exists(filepath):
            GCodeViewerWindow(self.root, filepath)
            self._log(f"📖 Открыто окно просмотра: {os.path.basename(filepath)}", "info")

    def _open_output_folder(self):
        folder_path = self.dir_var.get()
        if not folder_path:
            messagebox.showwarning("Предупреждение", "Папка не указана!")
            return
        if not os.path.exists(folder_path):
            try:
                os.makedirs(folder_path, exist_ok=True)
                self._log(f"📁 Создана папка: {folder_path}", "info")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))
                return
        try:
            if sys.platform == 'win32': os.startfile(folder_path)
            elif sys.platform == 'darwin': subprocess.Popen(['open', folder_path])
            else: subprocess.Popen(['xdg-open', folder_path])
            self._log(f"📂 Открыта папка: {folder_path}", "success")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _load_file_to_viewer(self, filepath: str):
        if not MATPLOTLIB_AVAILABLE: return
        self._log(f"📥 Загрузка: {os.path.basename(filepath)}", "info")
        self.current_points, self.code_lines = self.parser.parse_file(filepath)
        if not self.current_points:
            self._log(" Файл пуст", "warning"); return
        self._display_code()
        self.file_label.config(text=os.path.basename(filepath), foreground="black")
        self.notebook.select(self.viewer_tab)
        self._update_plot()
        self._log(f"✅ Загружено точек: {len(self.current_points)}, строк кода: {len(self.code_lines)}", "success")

    def _copy_log_selection(self):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.log_text.get(tk.SEL_FIRST, tk.SEL_END))
            self._log("✅ Выделенный текст скопирован", "success")
        except tk.TclError:
            self._log("⚠ Ничего не выделено", "warning")

    def _copy_all_log(self):
        c = self.log_text.get("1.0", tk.END).strip()
        if c:
            self.root.clipboard_clear()
            self.root.clipboard_append(c)
            self._log("✅ Весь лог скопирован", "success")
        else:
            self._log("⚠ Лог пуст", "warning")

    def _clear_log(self):
        self.log_text.delete("1.0", tk.END)
        self._log("🗑️ Лог очищен", "info")

    def _save_log_manual(self):
        c = self.log_text.get("1.0", tk.END).strip()
        if not c:
            self._log("⚠ Лог пуст", "warning")
            return
        fp = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if fp:
            try:
                with open(fp, 'w', encoding='utf-8') as f: f.write(c)
                self._log(f" Лог сохранён: {fp}", "success")
            except Exception as e:
                self._log(f"❌ Ошибка сохранения: {e}", "error")

    def _save_log_to_dir(self, d):
        c = self.log_text.get("1.0", tk.END).strip()
        if c:
            with open(os.path.join(d, "log.txt"), 'w', encoding='utf-8') as f: f.write(c)

    def _update_params(self):
        try:
            self.params = MillingParams(
                x_min=self.x_min_var.get(), x_max=self.x_max_var.get(),
                y_min=self.y_min_var.get(), y_max=self.y_max_var.get(),
                tool_diameter=self.tool_diam_var.get(), stepover=self.stepover_var.get(),
                z_start=self.z_start_var.get(), z_end=self.z_end_var.get(),
                z_step=self.z_step_var.get(), safe_z=self.safe_z_var.get(),
                feed_xy=self.feed_xy_var.get(), feed_z=self.feed_z_var.get(),
                tool_number=self.tool_num_var.get(), spindle_speed=self.spindle_var.get(),
                passes_per_file=self.passes_var.get(), milling_type=self.milling_type_var.get(),
                milling_direction=self.milling_direction_var.get(),
                contour_direction=self.contour_direction_var.get()
            )
            self.generator.params = self.params
            return True
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
            return False

    def _validate(self):
        if not self._update_params(): return
        valid, msg = self.generator.validate_params()
        overlap = self.generator.calculate_overlap_percent()
        self._log("=" * 60, "highlight")
        self._log("🔍 АНАЛИЗ ПАРАМЕТРОВ", "highlight")
        self._log("=" * 60, "highlight")
        if valid:
            self._log(f"✅ Параметры корректны", "success")
            self._log(f"📐 Поле: {self.params.x_max-self.params.x_min:.0f} × {self.params.y_max-self.params.y_min:.0f} мм", "info")
            self._log(f"🔧 Фреза: Ø{self.params.tool_diameter} мм, шаг: {self.params.stepover} мм, перекрытие: {overlap:.0f}%", "info")
        else:
            self._log(f"❌ {msg}", "error")
        self._log("=" * 60, "highlight")

    def _select_dir(self):
        d = filedialog.askdirectory()
        if d: self.dir_var.set(d)

    def _generate(self):
        if not self._update_params(): return
        d = self.dir_var.get()
        if not d: messagebox.showerror("Ошибка", "Выберите папку"); return
        self._log("=" * 60, "highlight")
        self._log(" ГЕНЕРАЦИЯ", "highlight")
        self._log(f"📂 Путь: {os.path.abspath(d)}", "info")
        self._log("=" * 60, "highlight")
        success, files = self.generator.generate_to_files(d)
        if success:
            self._log(f"✅ Создано файлов: {len(files)}", "success")
            for fp in files: self._log_file_links(fp)
            self._save_log_to_dir(d)
        else:
            self._log("❌ Ошибка", "error")
        self._log("=" * 60, "highlight")

    def _open_file(self):
        fp = filedialog.askopenfilename(filetypes=[("G-code", "*.nc *.gcode *.txt"), ("All", "*.*")])
        if fp: self._load_file_to_viewer(fp)

    def _update_plot(self):
        if not MATPLOTLIB_AVAILABLE or not self.current_points: return
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        proj = self.projection_var.get()
        rx = [p.x for p in self.current_points if p.rapid]
        ry = [p.y for p in self.current_points if p.rapid]
        rz = [p.z for p in self.current_points if p.rapid]
        wx = [p.x for p in self.current_points if not p.rapid]
        wy = [p.y for p in self.current_points if not p.rapid]
        wz = [p.z for p in self.current_points if not p.rapid]
        if proj == "XY":
            if rx: self.ax.scatter(rx, ry, c='red', s=2, alpha=0.3, label='G0')
            if wx: self.ax.scatter(wx, wy, c='blue', s=2, alpha=0.6, label='G1')
            self.ax.set_xlabel('X'); self.ax.set_ylabel('Y')
            self.ax.set_aspect('equal')
        elif proj == "XZ":
            if rx: self.ax.scatter(rx, rz, c='red', s=2, alpha=0.3, label='G0')
            if wx: self.ax.scatter(wx, wz, c='blue', s=2, alpha=0.6, label='G1')
            self.ax.set_xlabel('X'); self.ax.set_ylabel('Z')
        elif proj == "YZ":
            if ry: self.ax.scatter(ry, rz, c='red', s=2, alpha=0.3, label='G0')
            if wy: self.ax.scatter(wy, wz, c='blue', s=2, alpha=0.6, label='G1')
            self.ax.set_xlabel('Y'); self.ax.set_ylabel('Z')
        self.ax.legend(loc='upper right', fontsize=8)
        self.ax.grid(True, alpha=0.3)
        self.canvas.draw_idle()


def main():
    root = tk.Tk()
    GCodeStudio(root)
    root.mainloop()


if __name__ == "__main__":
    main()