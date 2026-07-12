"""Основной контроллер G-Code Studio. Объединяет все компоненты приложения."""
import os
import sys
import subprocess
import threading
import queue
from datetime import datetime
from typing import List

import numpy as np
from matplotlib.collections import LineCollection

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

try:
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.figure import Figure
    from matplotlib.patches import Circle
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# gcode_studio/controller.py
# ✅ Относительные импорты
from .models import MillingParams, GCodePoint
from .generator import GCodeGenerator
from .parser import GCodeParser
from .viewer_window import GCodeViewerWindow
from .config import (
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    TAB_GENERATOR_TITLE, TAB_VIEWER_TITLE,
    DEFAULT_X_MIN, DEFAULT_X_MAX, DEFAULT_Y_MIN, DEFAULT_Y_MAX,
    DEFAULT_TOOL_DIAMETER, DEFAULT_STEPOVER, DEFAULT_Z_START,
    DEFAULT_Z_END, DEFAULT_Z_STEP, DEFAULT_SAFE_Z,
    DEFAULT_FEED_XY, DEFAULT_FEED_Z, DEFAULT_TOOL_NUMBER,
    DEFAULT_SPINDLE_SPEED, DEFAULT_PASSES_PER_FILE, DEFAULT_ALLOWANCE,
    DEFAULT_MILLING_TYPE, DEFAULT_MILLING_DIRECTION, DEFAULT_CONTOUR_DIRECTION,
    DEFAULT_PROJECTION, PROJECTIONS,
    MILLING_TYPES, MILLING_DIRECTIONS, CONTOUR_DIRECTIONS,
    ANIMATION_SPEEDS, DEFAULT_ANIMATION_SPEED,
    ANIMATION_INTERVAL_MS, ANIMATION_SKIP_DRAWING_DELAY,
    QUEUE_POLL_INTERVAL_MS, RESIZE_DEBOUNCE_MS,
    FIGURE_WIDTH, FIGURE_HEIGHT, FIGURE_DPI, VIEW_MARGIN,
    COLOR_RAPID, COLOR_WORKING, COLOR_TOOL_PATH, COLOR_TOOL_MARKER,
    COLOR_TRAJECTORY_BG, SCATTER_SIZE, SCATTER_ALPHA_RAPID,
    SCATTER_ALPHA_WORKING, LINE_WIDTH_TRAJECTORY, LINE_WIDTH_PASSED,
    LINE_ALPHA_TRAJECTORY, LINE_ALPHA_PASSED, TOOL_PATH_ALPHA,
    TOOL_MARKER_SIZE, TOOL_OUTLINE_WIDTH, GRID_ALPHA,
    CODE_BG_COLOR, CODE_FG_COLOR, CODE_FONT,
    CURRENT_LINE_BG, CURRENT_LINE_FG, HOVER_LINE_BG, HOVER_LINE_FG,
    LOG_FONT, LOG_HEIGHT, LOG_COLOR_INFO, LOG_COLOR_SUCCESS,
    LOG_COLOR_ERROR, LOG_COLOR_WARNING, LOG_COLOR_HIGHLIGHT,
    BTN_VALIDATE_TEXT, BTN_VALIDATE_WIDTH, BTN_GENERATE_TEXT,
    BTN_GENERATE_BUSY_TEXT, BTN_GENERATE_WIDTH,
    BTN_PLAY_TEXT, BTN_PAUSE_TEXT, BTN_STOP_TEXT,
    BTN_STEP_BACK_TEXT, BTN_STEP_FWD_TEXT, BTN_WIDTH,
    STATUS_WAITING, STATUS_PLAYING, STATUS_PAUSED, STATUS_STOPPED, STATUS_FINISHED,
    COORD_DEFAULT_TEXT, FILE_NOT_LOADED_TEXT, FILE_LOADING_TEXT, FILE_EMPTY_TEXT,
    LOG_SEPARATOR, LOG_READY_MSG, LOG_HINT_MSG, LOG_LINE_FORMAT,
    LOG_FILE_PREFIX, LOG_DATE_FORMAT,
    MSG_NO_FILE_TITLE, MSG_NO_FILE_TEXT, MSG_ERROR_TITLE, MSG_SELECT_FOLDER,
    MSG_GENERATION_ERROR, MSG_LOG_EMPTY, MSG_NOTHING_SELECTED,
)


class GCodeStudio:
    """Основной контроллер приложения G-Code Studio."""

    def __init__(self, root):
        """Инициализация контроллера."""
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        self.params = MillingParams()
        self.generator = GCodeGenerator(self.params)
        self.parser = GCodeParser()

        self.current_points: List[GCodePoint] = []
        self.code_lines: List[str] = []

        self.task_queue = queue.Queue()
        self._is_generating = False
        self._is_drawing = False
        self._resize_after_id = None

        self.anim_running = False
        self.anim_paused = False
        self.anim_frame = 0
        self.anim_after_id = None

        self.view_link_counter = 0
        self.viz_link_counter = 0
        self.view_links = {}
        self.viz_links = {}

        self._setup_ui()
        self._process_queue()

    def _process_queue(self):
        """Обработка задач из очереди в главном потоке."""
        try:
            while True:
                task = self.task_queue.get_nowait()
                if task['type'] == 'generation_done':
                    self._on_generation_done(task['success'], task['files'])
                elif task['type'] == 'file_loaded':
                    self._on_file_loaded(task['points'], task['lines'], task['filename'])
        except queue.Empty:
            pass
        self.root.after(QUEUE_POLL_INTERVAL_MS, self._process_queue)

    def _setup_ui(self):
        """Создание основного интерфейса с вкладками."""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.generator_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.generator_tab, text=TAB_GENERATOR_TITLE)
        self._setup_generator_tab()

        self.viewer_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.viewer_tab, text=TAB_VIEWER_TITLE)
        self._setup_viewer_tab()

    def _setup_generator_tab(self):
        """Создание вкладки генератора."""
        main_frame = ttk.Frame(self.generator_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X)

        params_frame = ttk.LabelFrame(top_frame, text="Параметры обработки", padding=10)
        params_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Поле обработки
        field_frame = ttk.LabelFrame(params_frame, text="📐 Поле обработки", padding=5)
        field_frame.pack(fill=tk.X, pady=5)

        row = ttk.Frame(field_frame); row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="X мин:", width=10).pack(side=tk.LEFT)
        self.x_min_var = tk.DoubleVar(value=DEFAULT_X_MIN)
        ttk.Entry(row, textvariable=self.x_min_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text="X макс:", width=10).pack(side=tk.LEFT)
        self.x_max_var = tk.DoubleVar(value=DEFAULT_X_MAX)
        ttk.Entry(row, textvariable=self.x_max_var, width=10).pack(side=tk.LEFT, padx=5)

        row = ttk.Frame(field_frame); row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="Y мин:", width=10).pack(side=tk.LEFT)
        self.y_min_var = tk.DoubleVar(value=DEFAULT_Y_MIN)
        ttk.Entry(row, textvariable=self.y_min_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text="Y макс:", width=10).pack(side=tk.LEFT)
        self.y_max_var = tk.DoubleVar(value=DEFAULT_Y_MAX)
        ttk.Entry(row, textvariable=self.y_max_var, width=10).pack(side=tk.LEFT, padx=5)

        # Тип обработки
        milling_type_frame = ttk.LabelFrame(field_frame, text="Тип обработки", padding=5)
        milling_type_frame.pack(fill=tk.X, pady=5)
        self.milling_type_var = tk.StringVar(value=DEFAULT_MILLING_TYPE)
        row = ttk.Frame(milling_type_frame); row.pack(fill=tk.X, pady=2)
        for val, label in MILLING_TYPES.items():
            ttk.Radiobutton(row, text=label, variable=self.milling_type_var, value=val).pack(side=tk.LEFT, padx=5)

        # Направление фрезерования
        direction_frame = ttk.LabelFrame(field_frame, text="Направление фрезерования", padding=5)
        direction_frame.pack(fill=tk.X, pady=5)
        self.milling_direction_var = tk.StringVar(value=DEFAULT_MILLING_DIRECTION)
        row = ttk.Frame(direction_frame); row.pack(fill=tk.X, pady=2)
        for val, label in MILLING_DIRECTIONS.items():
            ttk.Radiobutton(row, text=label, variable=self.milling_direction_var, value=val).pack(side=tk.LEFT, padx=5)

        # Направление контурной обработки
        contour_direction_frame = ttk.LabelFrame(field_frame, text="Направление контурной обработки", padding=5)
        contour_direction_frame.pack(fill=tk.X, pady=5)
        self.contour_direction_var = tk.StringVar(value=DEFAULT_CONTOUR_DIRECTION)
        row = ttk.Frame(contour_direction_frame); row.pack(fill=tk.X, pady=2)
        for val, label in CONTOUR_DIRECTIONS.items():
            ttk.Radiobutton(row, text=label, variable=self.contour_direction_var, value=val).pack(side=tk.LEFT, padx=5)

        # Фреза
        tool_frame = ttk.LabelFrame(params_frame, text="🔧 Фреза", padding=5)
        tool_frame.pack(fill=tk.X, pady=5)

        row = ttk.Frame(tool_frame); row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="Диаметр (мм):", width=15).pack(side=tk.LEFT)
        self.tool_diam_var = tk.DoubleVar(value=DEFAULT_TOOL_DIAMETER)
        ttk.Entry(row, textvariable=self.tool_diam_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text="№ инструмента:", width=15).pack(side=tk.LEFT)
        self.tool_num_var = tk.IntVar(value=DEFAULT_TOOL_NUMBER)
        ttk.Entry(row, textvariable=self.tool_num_var, width=10).pack(side=tk.LEFT, padx=5)

        row = ttk.Frame(tool_frame); row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="Шаг (stepover):", width=15).pack(side=tk.LEFT)
        self.stepover_var = tk.DoubleVar(value=DEFAULT_STEPOVER)
        ttk.Entry(row, textvariable=self.stepover_var, width=10).pack(side=tk.LEFT, padx=5)

        # Припуск
        allowance_frame = ttk.LabelFrame(params_frame, text="📏 Припуск", padding=5)
        allowance_frame.pack(fill=tk.X, pady=5)
        row = ttk.Frame(allowance_frame); row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="Припуск (мм):", width=15).pack(side=tk.LEFT)
        self.allowance_var = tk.DoubleVar(value=DEFAULT_ALLOWANCE)
        ttk.Entry(row, textvariable=self.allowance_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text="(0 = без выхода за границы)", foreground="gray").pack(side=tk.LEFT, padx=5)

        # Глубина обработки
        z_frame = ttk.LabelFrame(params_frame, text="📏 Глубина обработки", padding=5)
        z_frame.pack(fill=tk.X, pady=5)

        row = ttk.Frame(z_frame); row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="Z старт:", width=10).pack(side=tk.LEFT)
        self.z_start_var = tk.DoubleVar(value=DEFAULT_Z_START)
        ttk.Entry(row, textvariable=self.z_start_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text="Z конец:", width=10).pack(side=tk.LEFT)
        self.z_end_var = tk.DoubleVar(value=DEFAULT_Z_END)
        ttk.Entry(row, textvariable=self.z_end_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text="Шаг по Z:", width=10).pack(side=tk.LEFT)
        self.z_step_var = tk.DoubleVar(value=DEFAULT_Z_STEP)
        ttk.Entry(row, textvariable=self.z_step_var, width=10).pack(side=tk.LEFT, padx=5)

        row = ttk.Frame(z_frame); row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="Безопасная Z:", width=15).pack(side=tk.LEFT)
        self.safe_z_var = tk.DoubleVar(value=DEFAULT_SAFE_Z)
        ttk.Entry(row, textvariable=self.safe_z_var, width=10).pack(side=tk.LEFT, padx=5)

        # Подачи и скорость
        feed_frame = ttk.LabelFrame(params_frame, text="⚡ Подачи и скорость", padding=5)
        feed_frame.pack(fill=tk.X, pady=5)

        row = ttk.Frame(feed_frame); row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="Подача XY:", width=15).pack(side=tk.LEFT)
        self.feed_xy_var = tk.IntVar(value=DEFAULT_FEED_XY)
        ttk.Entry(row, textvariable=self.feed_xy_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text="Подача Z:", width=15).pack(side=tk.LEFT)
        self.feed_z_var = tk.IntVar(value=DEFAULT_FEED_Z)
        ttk.Entry(row, textvariable=self.feed_z_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text="Обороты:", width=10).pack(side=tk.LEFT)
        self.spindle_var = tk.IntVar(value=DEFAULT_SPINDLE_SPEED)
        ttk.Entry(row, textvariable=self.spindle_var, width=10).pack(side=tk.LEFT, padx=5)

        # Разбивка на файлы
        file_frame = ttk.LabelFrame(params_frame, text="📁 Разбивка на файлы", padding=5)
        file_frame.pack(fill=tk.X, pady=5)

        row = ttk.Frame(file_frame); row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="Проходов на файл:", width=20).pack(side=tk.LEFT)
        self.passes_var = tk.IntVar(value=DEFAULT_PASSES_PER_FILE)
        ttk.Entry(row, textvariable=self.passes_var, width=10).pack(side=tk.LEFT, padx=5)

        row = ttk.Frame(file_frame); row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="Папка:", width=10).pack(side=tk.LEFT)
        self.dir_var = tk.StringVar(value=os.path.expanduser("~"))
        ttk.Entry(row, textvariable=self.dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(row, text="📂", command=self._open_output_folder, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="...", command=self._select_dir, width=3).pack(side=tk.LEFT)

        # Кнопки действий
        btn_frame = ttk.LabelFrame(top_frame, text="Действия", padding=10)
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        ttk.Button(btn_frame, text=BTN_VALIDATE_TEXT, command=self._validate, width=BTN_VALIDATE_WIDTH).pack(pady=5)
        self.btn_generate = ttk.Button(btn_frame, text=BTN_GENERATE_TEXT, command=self._generate, width=BTN_GENERATE_WIDTH)
        self.btn_generate.pack(pady=5)

        # Лог операций
        log_frame = ttk.LabelFrame(main_frame, text="📋 Лог операций", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        log_btn_frame = ttk.Frame(log_frame)
        log_btn_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(log_btn_frame, text="📋 Копировать выделенное", command=self._copy_log_selection).pack(side=tk.LEFT, padx=2)
        ttk.Button(log_btn_frame, text="📋 Копировать весь лог", command=self._copy_all_log).pack(side=tk.LEFT, padx=2)
        ttk.Button(log_btn_frame, text="🗑️ Очистить лог", command=self._clear_log).pack(side=tk.LEFT, padx=2)
        ttk.Button(log_btn_frame, text="💾 Сохранить лог", command=self._save_log_manual).pack(side=tk.LEFT, padx=2)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, font=LOG_FONT, height=LOG_HEIGHT)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.tag_configure("info", foreground=LOG_COLOR_INFO)
        self.log_text.tag_configure("success", foreground=LOG_COLOR_SUCCESS)
        self.log_text.tag_configure("error", foreground=LOG_COLOR_ERROR)
        self.log_text.tag_configure("warning", foreground=LOG_COLOR_WARNING)
        self.log_text.tag_configure("highlight", foreground=LOG_COLOR_HIGHLIGHT, font=('Consolas', 10, 'bold'))

        self._log(LOG_READY_MSG, "info")
        self._log(LOG_HINT_MSG, "info")

    def _setup_viewer_tab(self):
        """Создание вкладки визуализатора."""
        if not MATPLOTLIB_AVAILABLE:
            ttk.Label(self.viewer_tab, text="⚠ Matplotlib не установлен!", font=('Arial', 14)).pack(expand=True)
            return

        control_frame = ttk.Frame(self.viewer_tab)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(control_frame, text="📂 Открыть файл", command=self._open_file).pack(side=tk.LEFT, padx=5)

        # Анимация
        anim_frame = ttk.LabelFrame(control_frame, text="🎬 Анимация", padding=5)
        anim_frame.pack(side=tk.LEFT, padx=10)

        self.btn_play = ttk.Button(anim_frame, text=BTN_PLAY_TEXT, command=self._anim_play, width=BTN_WIDTH)
        self.btn_play.pack(side=tk.LEFT, padx=2)
        self.btn_pause = ttk.Button(anim_frame, text=BTN_PAUSE_TEXT, command=self._anim_pause, width=BTN_WIDTH, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT, padx=2)
        self.btn_stop = ttk.Button(anim_frame, text=BTN_STOP_TEXT, command=self._anim_stop, width=BTN_WIDTH, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=2)

        # Пошаговое выполнение
        step_frame = ttk.Frame(anim_frame)
        step_frame.pack(side=tk.LEFT, padx=10)
        self.btn_step_back = ttk.Button(step_frame, text=BTN_STEP_BACK_TEXT, command=self._anim_step_back, width=BTN_WIDTH, state=tk.DISABLED)
        self.btn_step_back.pack(side=tk.LEFT, padx=2)
        self.btn_step_fwd = ttk.Button(step_frame, text=BTN_STEP_FWD_TEXT, command=self._anim_step_forward, width=BTN_WIDTH, state=tk.DISABLED)
        self.btn_step_fwd.pack(side=tk.LEFT, padx=2)

        # Скорость
        speed_frame = ttk.Frame(anim_frame)
        speed_frame.pack(side=tk.LEFT, padx=10)
        ttk.Label(speed_frame, text="Скорость:").pack(side=tk.LEFT)
        self.speed_var = tk.IntVar(value=DEFAULT_ANIMATION_SPEED)
        ttk.Combobox(speed_frame, textvariable=self.speed_var, values=ANIMATION_SPEEDS, width=4, state="readonly").pack(side=tk.LEFT, padx=3)

        # Проекция
        ttk.Label(control_frame, text="Проекция:").pack(side=tk.LEFT, padx=(20, 5))
        self.projection_var = tk.StringVar(value=DEFAULT_PROJECTION)
        projection_combo = ttk.Combobox(control_frame, textvariable=self.projection_var, values=PROJECTIONS, state="readonly", width=6)
        projection_combo.pack(side=tk.LEFT)
        projection_combo.bind('<<ComboboxSelected>>', lambda e: self._update_plot())

        self.file_label = ttk.Label(control_frame, text=FILE_NOT_LOADED_TEXT, foreground="gray")
        self.file_label.pack(side=tk.LEFT, padx=20)

        # Прогресс-бар
        self.progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(self.viewer_tab, variable=self.progress_var, maximum=100).pack(fill=tk.X, padx=10, pady=2)

        # Координаты
        self.coord_label = ttk.Label(self.viewer_tab, text=COORD_DEFAULT_TEXT, font=('Consolas', 11, 'bold'), foreground='blue')
        self.coord_label.pack(fill=tk.X, padx=10, pady=2)

        # Статус
        self.status_label = ttk.Label(self.viewer_tab, text=STATUS_WAITING, foreground='gray')
        self.status_label.pack(fill=tk.X, padx=10, pady=2)

        # Основной контент
        content_frame = ttk.Frame(self.viewer_tab)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # График
        plot_frame = ttk.Frame(content_frame)
        plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.fig = Figure(figsize=(FIGURE_WIDTH, FIGURE_HEIGHT), dpi=FIGURE_DPI)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        NavigationToolbar2Tk(self.canvas, plot_frame).update()
        self.canvas.get_tk_widget().bind('<Configure>', self._on_window_resize)

        # Редактор G-кода
        code_frame = ttk.LabelFrame(content_frame, text="📄 G-код (клик по строке → переход к точке)", padding=5)
        code_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

        code_scroll = ttk.Scrollbar(code_frame, orient=tk.VERTICAL)
        code_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.code_text = tk.Text(
            code_frame, wrap=tk.NONE, font=CODE_FONT,
            yscrollcommand=code_scroll.set, state=tk.DISABLED,
            bg=CODE_BG_COLOR, fg=CODE_FG_COLOR, cursor='hand2'
        )
        self.code_text.pack(fill=tk.BOTH, expand=True)
        code_scroll.config(command=self.code_text.yview)

        self.code_text.tag_configure("current_line", background=CURRENT_LINE_BG, foreground=CURRENT_LINE_FG)
        self.code_text.tag_configure("hover_line", background=HOVER_LINE_BG, foreground=HOVER_LINE_FG)

        self.code_text.bind('<Button-1>', self._on_code_click)
        self.code_text.bind('<Motion>', self._on_code_hover)
        self.code_text.bind('<Leave>', lambda e: self._clear_hover())

    # ================================================================
    # Resize
    # ================================================================
    def _on_window_resize(self, event):
        """Обработчик изменения размера окна с debounce."""
        if self._resize_after_id:
            self.root.after_cancel(self._resize_after_id)
        self._resize_after_id = self.root.after(RESIZE_DEBOUNCE_MS, self._update_plot)

    # ================================================================
    # Клик и наведение по коду
    # ================================================================
    def _on_code_click(self, event):
        """Обработчик клика по строке кода — переход к точке."""
        if not self.current_points or not self.code_lines:
            return
        try:
            line_idx = int(self.code_text.index(f"@{event.x},{event.y}").split('.')[0])
        except Exception:
            return
        if line_idx < 1 or line_idx > len(self.code_lines):
            return

        target = None
        for pt in self.current_points:
            if pt.line_number == line_idx:
                target = pt
                break
        if target is None:
            for pt in self.current_points:
                if pt.line_number >= line_idx:
                    target = pt
                    break
        if target is None:
            return

        if self.anim_running:
            self._anim_pause()

        for i, pt in enumerate(self.current_points):
            if pt.line_number == line_idx or (i > 0 and self.current_points[i-1].line_number < line_idx <= pt.line_number):
                self.anim_frame = i + 1
                break

        self._render_at_frame(self.anim_frame, highlight_line=line_idx)
        self.status_label.config(text=f"Статус: Переход к строке {line_idx}", foreground='purple')

    def _on_code_hover(self, event):
        """Подсветка строки при наведении."""
        try:
            line_idx = int(self.code_text.index(f"@{event.x},{event.y}").split('.')[0])
        except Exception:
            return
        self._clear_hover()
        if 1 <= line_idx <= len(self.code_lines):
            self.code_text.tag_add("hover_line", f"{line_idx}.0", f"{line_idx}.end")

    def _clear_hover(self):
        """Очистка подсветки при наведении."""
        self.code_text.tag_remove("hover_line", "1.0", tk.END)

    # ================================================================
    # Отрисовка кадра
    # ================================================================
    def _render_at_frame(self, end_idx: int, highlight_line: int = None):
        """Отрисовка состояния на заданном кадре (оптимизированная)."""
        if not self.current_points:
            return

        total = len(self.current_points)
        pct = (end_idx / total * 100) if total > 0 else 0
        self.progress_var.set(pct)

        if end_idx > 0 and end_idx <= total:
            cur = self.current_points[end_idx - 1]
            mode = "G0 (Холостой)" if cur.rapid else "G1 (Рабочий)"
            color = COLOR_RAPID if cur.rapid else COLOR_WORKING
            self.coord_label.config(
                text=f"📍 X: {cur.x:.3f}  Y: {cur.y:.3f}  Z: {cur.z:.3f}  |  {mode}",
                foreground=color
            )
            if highlight_line is None:
                highlight_line = cur.line_number

        self._is_drawing = True
        try:
            self.ax.clear()

            # 1. Вся траектория
            all_x = [p.x for p in self.current_points]
            all_y = [p.y for p in self.current_points]
            self.ax.plot(all_x, all_y, color=COLOR_TRAJECTORY_BG, linewidth=LINE_WIDTH_TRAJECTORY, alpha=LINE_ALPHA_TRAJECTORY)

            # 2. Пройденный путь
            passed_x = [p.x for p in self.current_points[:end_idx]]
            passed_y = [p.y for p in self.current_points[:end_idx]]
            if passed_x:
                self.ax.plot(passed_x, passed_y, color=COLOR_WORKING, linewidth=LINE_WIDTH_PASSED, alpha=LINE_ALPHA_PASSED)

            # 3. Точный расчёт масштаба
            bbox = self.ax.get_window_extent()
            x_range = self.params.x_max - self.params.x_min
            if x_range > 0:
                points_per_mm = bbox.width / x_range
                tool_diameter_pts = self.params.tool_diameter * points_per_mm
            else:
                tool_diameter_pts = self.params.tool_diameter * 2.5

            # 4. Обработанная область через LineCollection
            working_x = [p.x for p in self.current_points[:end_idx] if not p.rapid]
            working_y = [p.y for p in self.current_points[:end_idx] if not p.rapid]

            if len(working_x) > 1:
                points_array = np.column_stack([working_x, working_y])
                segments = np.stack([points_array[:-1], points_array[1:]], axis=1)
                lc = LineCollection(
                    segments,
                    linewidths=tool_diameter_pts,
                    colors=COLOR_TOOL_PATH,
                    alpha=TOOL_PATH_ALPHA,
                    capstyle='round',
                    joinstyle='round'
                )
                self.ax.add_collection(lc)

            # 5. Текущая позиция фрезы
            if end_idx > 0:
                cur = self.current_points[end_idx - 1]
                self.ax.plot(cur.x, cur.y, 'ro', markersize=TOOL_MARKER_SIZE, zorder=10)
                tool_r = self.params.tool_diameter / 2.0
                self.ax.add_patch(Circle(
                    (cur.x, cur.y), tool_r,
                    fill=False, color=COLOR_TOOL_MARKER,
                    linewidth=TOOL_OUTLINE_WIDTH, zorder=9
                ))
                self.ax.set_title(f'Анимация | Z={cur.z:.3f} мм | Строка {cur.line_number}')

            self.ax.set_xlim(self.params.x_min - VIEW_MARGIN, self.params.x_max + VIEW_MARGIN)
            self.ax.set_ylim(self.params.y_min - VIEW_MARGIN, self.params.y_max + VIEW_MARGIN)
            self.ax.set_aspect('equal')
            self.ax.grid(True, alpha=GRID_ALPHA)
            self.canvas.draw_idle()
        finally:
            self._is_drawing = False

        if highlight_line:
            self._highlight_code_line(highlight_line)

    # ================================================================
    # Анимация
    # ================================================================
    def _anim_play(self):
        """Запуск или возобновление анимации."""
        if not self.current_points:
            messagebox.showwarning(MSG_NO_FILE_TITLE, MSG_NO_FILE_TEXT)
            return
        if self.anim_paused:
            self.anim_paused = False
            self.anim_running = True
            self._update_step_buttons()
            self.status_label.config(text=STATUS_PLAYING, foreground='green')
            self._animate_step()
            return
        self.anim_frame = 0
        self.anim_running = True
        self.anim_paused = False
        self._update_step_buttons()
        self.status_label.config(text=STATUS_PLAYING, foreground='green')
        self._animate_step()

    def _anim_pause(self):
        """Пауза анимации."""
        self.anim_paused = True
        self.anim_running = False
        if self.anim_after_id:
            self.root.after_cancel(self.anim_after_id)
        self._update_step_buttons()
        self.status_label.config(text=STATUS_PAUSED, foreground='orange')

    def _anim_stop(self):
        """Полная остановка анимации."""
        self.anim_running = False
        self.anim_paused = False
        self.anim_frame = 0
        if self.anim_after_id:
            self.root.after_cancel(self.anim_after_id)
        self.progress_var.set(0)
        self.coord_label.config(text=COORD_DEFAULT_TEXT)
        self._update_step_buttons()
        self.status_label.config(text=STATUS_STOPPED, foreground='red')
        self.code_text.tag_remove("current_line", "1.0", tk.END)
        self._update_plot()

    def _anim_step_forward(self):
        """Шаг вперёд на 1 точку."""
        if not self.current_points:
            return
        self.anim_frame = min(self.anim_frame + 1, len(self.current_points))
        self._render_at_frame(self.anim_frame)
        self.status_label.config(text=f"Статус: Шаг вперёд ({self.anim_frame}/{len(self.current_points)})", foreground='purple')

    def _anim_step_back(self):
        """Шаг назад на 1 точку."""
        if not self.current_points:
            return
        self.anim_frame = max(0, self.anim_frame - 1)
        self._render_at_frame(self.anim_frame)
        self.status_label.config(text=f"Статус: Шаг назад ({self.anim_frame}/{len(self.current_points)})", foreground='purple')

    def _update_step_buttons(self):
        """Обновить состояние кнопок шагов."""
        if self.anim_paused:
            self.btn_step_back.config(state=tk.NORMAL)
            self.btn_step_fwd.config(state=tk.NORMAL)
            self.btn_play.config(state=tk.NORMAL)
            self.btn_pause.config(state=tk.DISABLED)
        elif self.anim_running:
            self.btn_play.config(state=tk.DISABLED)
            self.btn_pause.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.NORMAL)
            self.btn_step_back.config(state=tk.DISABLED)
            self.btn_step_fwd.config(state=tk.DISABLED)
        else:
            self.btn_play.config(state=tk.NORMAL)
            self.btn_pause.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.DISABLED)
            self.btn_step_back.config(state=tk.DISABLED)
            self.btn_step_fwd.config(state=tk.DISABLED)

    def _animate_step(self):
        """Один шаг анимации."""
        if not self.anim_running:
            return
        if self._is_drawing:
            self.anim_after_id = self.root.after(ANIMATION_SKIP_DRAWING_DELAY, self._animate_step)
            return

        speed = self.speed_var.get()
        self.anim_frame = min(self.anim_frame + speed, len(self.current_points))
        end_idx = self.anim_frame
        total = len(self.current_points)

        self._render_at_frame(end_idx)

        if end_idx >= total:
            self.anim_running = False
            self.anim_paused = False
            self._update_step_buttons()
            self.status_label.config(text=STATUS_FINISHED, foreground='green')
        else:
            self.anim_after_id = self.root.after(ANIMATION_INTERVAL_MS, self._animate_step)

    # ================================================================
    # Подсветка и отображение кода
    # ================================================================
    def _highlight_code_line(self, line_num: int):
        """Подсветка строки в редакторе G-кода."""
        self.code_text.tag_remove("current_line", "1.0", tk.END)
        if line_num <= 0 or line_num > len(self.code_lines):
            return
        start_idx = f"{line_num}.0"
        end_idx = f"{line_num}.end"
        self.code_text.tag_add("current_line", start_idx, end_idx)
        self.code_text.see(start_idx)

    def _display_code(self):
        """Отображение G-кода в редакторе с нумерацией строк."""
        self.code_text.config(state=tk.NORMAL)
        self.code_text.delete("1.0", tk.END)
        for i, line in enumerate(self.code_lines, 1):
            self.code_text.insert(tk.END, LOG_LINE_FORMAT.format(i=i, line=line) + "\n")
        self.code_text.config(state=tk.DISABLED)

    # ================================================================
    # Логирование
    # ================================================================
    def _log(self, message: str, tag: str = "info"):
        """Добавление сообщения в лог."""
        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.see(tk.END)

    def _log_file_links(self, filepath: str):
        """Логирование ссылки на файл с кликабельными кнопками."""
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
        """Обработчик клика по ссылке 'просмотр'."""
        if not tag_name:
            idx = self.log_text.index(f"@{event.x},{event.y}")
            for t in self.log_text.tag_names(idx):
                if t.startswith("viewlink_"):
                    tag_name = t
                    break
        if tag_name and tag_name in self.view_links:
            if os.path.exists(self.view_links[tag_name]):
                GCodeViewerWindow(self.root, self.view_links[tag_name])

    def _on_viz_link_click(self, event, tag_name=None):
        """Обработчик клика по ссылке 'визуализатор'."""
        if not tag_name:
            idx = self.log_text.index(f"@{event.x},{event.y}")
            for t in self.log_text.tag_names(idx):
                if t.startswith("vizlink_"):
                    tag_name = t
                    break
        if tag_name and tag_name in self.viz_links:
            self._load_file_to_viewer(self.viz_links[tag_name])

    # ================================================================
    # Файлы и папки
    # ================================================================
    def _open_output_folder(self):
        """Открытие папки вывода в файловом менеджере."""
        folder_path = self.dir_var.get()
        if not folder_path:
            return
        if not os.path.exists(folder_path):
            try:
                os.makedirs(folder_path, exist_ok=True)
            except Exception as e:
                messagebox.showerror(MSG_ERROR_TITLE, str(e))
                return
        try:
            if sys.platform == 'win32':
                os.startfile(folder_path)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', folder_path])
            else:
                subprocess.Popen(['xdg-open', folder_path])
        except Exception as e:
            messagebox.showerror(MSG_ERROR_TITLE, str(e))

    def _select_dir(self):
        """Выбор директории через диалог."""
        d = filedialog.askdirectory()
        if d:
            self.dir_var.set(d)

    # ================================================================
    # Параметры и валидация
    # ================================================================
    def _update_params(self):
        """Чтение параметров из UI в объект MillingParams."""
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
                contour_direction=self.contour_direction_var.get(),
                allowance=self.allowance_var.get()
            )
            self.generator.params = self.params
            return True
        except Exception as e:
            messagebox.showerror(MSG_ERROR_TITLE, str(e))
            return False

    def _validate(self):
        """Валидация параметров и вывод результата в лог."""
        if not self._update_params():
            return
        valid, msg = self.generator.validate_params()
        overlap = self.generator.calculate_overlap_percent()

        self._log(LOG_SEPARATOR, "highlight")
        self._log("🔍 АНАЛИЗ ПАРАМЕТРОВ", "highlight")

        if valid:
            self._log("✅ Параметры корректны", "success")
            self._log(f"📐 Поле: {self.params.x_max - self.params.x_min:.0f} × {self.params.y_max - self.params.y_min:.0f} мм", "info")
            self._log(f"🔧 Фреза: Ø{self.params.tool_diameter} мм, шаг: {self.params.stepover} мм, перекрытие: {overlap:.0f}%", "info")
        else:
            self._log(f"❌ {msg}", "error")

        self._log(LOG_SEPARATOR, "highlight")

    # ================================================================
    # Генерация G-кода (многопоточная)
    # ================================================================
    def _generate(self):
        """Запуск генерации G-кода в отдельном потоке."""
        if self._is_generating:
            return
        if not self._update_params():
            return
        d = self.dir_var.get()
        if not d:
            messagebox.showerror(MSG_ERROR_TITLE, MSG_SELECT_FOLDER)
            return

        self._is_generating = True
        self.btn_generate.config(state=tk.DISABLED, text=BTN_GENERATE_BUSY_TEXT)
        self._log("🚀 НАЧАЛО ГЕНЕРАЦИИ (в отдельном потоке)", "highlight")

        thread = threading.Thread(target=self._generate_worker, args=(d,), daemon=True)
        thread.start()

    def _generate_worker(self, output_dir: str):
        """Рабочий поток генерации G-кода."""
        try:
            success, files = self.generator.generate_to_files(output_dir)
            self.task_queue.put({'type': 'generation_done', 'success': success, 'files': files})
        except Exception:
            self.task_queue.put({'type': 'generation_done', 'success': False, 'files': []})

    def _on_generation_done(self, success: bool, files: List[str]):
        """Обработка завершения генерации."""
        self._is_generating = False
        self.btn_generate.config(state=tk.NORMAL, text=BTN_GENERATE_TEXT)

        if success:
            self._log(f"✅ Создано файлов: {len(files)}", "success")
            for fp in files:
                self._log_file_links(fp)
        else:
            self._log(MSG_GENERATION_ERROR, "error")

    # ================================================================
    # Загрузка и парсинг файлов
    # ================================================================
    def _open_file(self):
        """Открытие файла G-кода через диалог."""
        fp = filedialog.askopenfilename(filetypes=[("G-code", "*.nc *.gcode *.txt"), ("All", "*.*")])
        if fp:
            self.file_label.config(text=FILE_LOADING_TEXT, foreground="orange")
            thread = threading.Thread(target=self._parse_file_worker, args=(fp,), daemon=True)
            thread.start()

    def _parse_file_worker(self, filepath: str):
        """Рабочий поток парсинга файла G-кода."""
        try:
            points, lines = self.parser.parse_file(filepath)
            self.task_queue.put({
                'type': 'file_loaded',
                'points': points,
                'lines': lines,
                'filename': os.path.basename(filepath)
            })
        except Exception:
            self.task_queue.put({'type': 'file_loaded', 'points': [], 'lines': [], 'filename': ''})

    def _on_file_loaded(self, points: List[GCodePoint], lines: List[str], filename: str):
        """Обработка завершения загрузки файла."""
        if not points:
            self.file_label.config(text=FILE_EMPTY_TEXT, foreground="red")
            return

        self.current_points = points
        self.code_lines = lines
        self.anim_frame = 0
        self.anim_running = False
        self.anim_paused = False
        self._update_step_buttons()
        self._display_code()
        self.file_label.config(text=filename, foreground="black")
        self.notebook.select(self.viewer_tab)
        self._update_plot()
        self._log(f"✅ Загружено точек: {len(points)}, строк: {len(lines)}", "success")

    def _load_file_to_viewer(self, filepath: str):
        """Загрузка файла напрямую в визуализатор."""
        self._log(f"📥 Загрузка: {os.path.basename(filepath)}", "info")
        self.current_points, self.code_lines = self.parser.parse_file(filepath)
        if not self.current_points:
            return
        self.anim_frame = 0
        self.anim_running = False
        self.anim_paused = False
        self._update_step_buttons()
        self._display_code()
        self.file_label.config(text=os.path.basename(filepath), foreground="black")
        self.notebook.select(self.viewer_tab)
        self._update_plot()

    # ================================================================
    # Визуализация (статический график)
    # ================================================================
    def _update_plot(self):
        """Обновление статического графика траектории."""
        if not MATPLOTLIB_AVAILABLE or not self.current_points:
            return
        if self._is_drawing:
            return

        self._is_drawing = True
        try:
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
                if rx: self.ax.scatter(rx, ry, c=COLOR_RAPID, s=SCATTER_SIZE, alpha=SCATTER_ALPHA_RAPID, label='G0')
                if wx: self.ax.scatter(wx, wy, c=COLOR_WORKING, s=SCATTER_SIZE, alpha=SCATTER_ALPHA_WORKING, label='G1')
                self.ax.set_xlabel('X')
                self.ax.set_ylabel('Y')
                self.ax.set_aspect('equal')
            elif proj == "XZ":
                if rx: self.ax.scatter(rx, rz, c=COLOR_RAPID, s=SCATTER_SIZE, alpha=SCATTER_ALPHA_RAPID, label='G0')
                if wx: self.ax.scatter(wx, wz, c=COLOR_WORKING, s=SCATTER_SIZE, alpha=SCATTER_ALPHA_WORKING, label='G1')
                self.ax.set_xlabel('X')
                self.ax.set_ylabel('Z')
            elif proj == "YZ":
                if ry: self.ax.scatter(ry, rz, c=COLOR_RAPID, s=SCATTER_SIZE, alpha=SCATTER_ALPHA_RAPID, label='G0')
                if wy: self.ax.scatter(wy, wz, c=COLOR_WORKING, s=SCATTER_SIZE, alpha=SCATTER_ALPHA_WORKING, label='G1')
                self.ax.set_xlabel('Y')
                self.ax.set_ylabel('Z')

            self.ax.legend(loc='upper right', fontsize=8)
            self.ax.grid(True, alpha=GRID_ALPHA)
            self.canvas.draw_idle()
        finally:
            self._is_drawing = False

    # ================================================================
    # Управление логом
    # ================================================================
    def _copy_log_selection(self):
        """Копирование выделенного текста лога."""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.log_text.get(tk.SEL_FIRST, tk.SEL_END))
            self._log("✅ Выделенный текст скопирован", "success")
        except tk.TclError:
            self._log(MSG_NOTHING_SELECTED, "warning")

    def _copy_all_log(self):
        """Копирование всего лога."""
        c = self.log_text.get("1.0", tk.END).strip()
        if c:
            self.root.clipboard_clear()
            self.root.clipboard_append(c)
            self._log("✅ Весь лог скопирован", "success")
        else:
            self._log(MSG_LOG_EMPTY, "warning")

    def _clear_log(self):
        """Очистка лога."""
        self.log_text.delete("1.0", tk.END)
        self._log("🗑️ Лог очищен", "info")

    def _save_log_manual(self):
        """Сохранение лога в файл с автоматическим именем."""
        c = self.log_text.get("1.0", tk.END).strip()
        if not c:
            self._log(MSG_LOG_EMPTY, "warning")
            return

        now = datetime.now()
        date_str = now.strftime(LOG_DATE_FORMAT)

        try:
            milling_type = self.milling_type_var.get()
            type_name = {
                "zigzag_x": "zigzag_x",
                "zigzag_y": "zigzag_y",
                "center_spiral": "center_spiral",
                "contour": "contour"
            }.get(milling_type, "unknown")
        except Exception:
            type_name = "log"

        default_name = f"{LOG_FILE_PREFIX}_{date_str}_{type_name}.txt"

        fp = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if fp:
            try:
                with open(fp, 'w', encoding='utf-8') as f:
                    f.write(c)
                self._log(f"💾 Лог сохранён: {os.path.basename(fp)}", "success")
            except Exception as e:
                self._log(f"❌ Ошибка сохранения: {e}", "error")