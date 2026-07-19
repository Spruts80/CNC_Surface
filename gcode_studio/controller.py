"""
Основной контроллер G-Code Studio.
Полная версия с поддержкой 3D-анимации, цилиндром фрезы,
автозагрузкой/сохранением настроек по умолчанию.
"""
import os
import sys
import subprocess
import threading
import queue
import math
import json
import tempfile
from datetime import datetime
from typing import List

import numpy as np
from matplotlib.collections import LineCollection
import matplotlib.ticker as mticker

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import (
        FigureCanvasTkAgg,
        NavigationToolbar2Tk,
    )
    from matplotlib.figure import Figure
    from matplotlib.patches import Circle
    from mpl_toolkits.mplot3d import Axes3D
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from .models import MillingParams, GCodePoint
from .generator import GCodeGenerator
from .parser import GCodeParser
from .viewer_window import GCodeViewerWindow
from .config import (
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT,
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    TAB_GENERATOR_TITLE, TAB_VIEWER_TITLE,
    DEFAULT_X_MIN, DEFAULT_X_MAX, DEFAULT_Y_MIN, DEFAULT_Y_MAX,
    DEFAULT_TOOL_DIAMETER, DEFAULT_STEPOVER,
    DEFAULT_Z_START, DEFAULT_Z_END, DEFAULT_Z_STEP, DEFAULT_SAFE_Z,
    DEFAULT_FEED_XY, DEFAULT_FEED_Z, DEFAULT_RAPID_FEED,
    DEFAULT_TOOL_NUMBER, DEFAULT_SPINDLE_SPEED,
    DEFAULT_PASSES_PER_FILE, DEFAULT_ALLOWANCE, DEFAULT_BACKTRACK_ENABLED,
    DEFAULT_MILLING_TYPE, DEFAULT_MILLING_DIRECTION,
    DEFAULT_CONTOUR_DIRECTION, DEFAULT_PROJECTION, PROJECTIONS,
    MILLING_TYPES, MILLING_DIRECTIONS, CONTOUR_DIRECTIONS,
    MILLING_TYPE_FILE_NAMES,
    ANIMATION_SPEEDS, DEFAULT_ANIMATION_SPEED, MIN_ANIMATION_SPEED,
    ANIMATION_INTERVAL_MS, ANIMATION_SKIP_DRAWING_DELAY,
    QUEUE_POLL_INTERVAL_MS, RESIZE_DEBOUNCE_MS, TOOL_PATH_SAMPLE_DIVISOR,
    FIGURE_WIDTH, FIGURE_HEIGHT, FIGURE_DPI, VIEW_MARGIN,
    COLOR_RAPID, COLOR_WORKING, COLOR_TOOL_PATH, COLOR_TOOL_MARKER,
    COLOR_TRAJECTORY_BG,
    SCATTER_ALPHA_RAPID, SCATTER_ALPHA_WORKING,
    LINE_WIDTH_TRAJECTORY, LINE_WIDTH_PASSED,
    LINE_ALPHA_TRAJECTORY, LINE_ALPHA_PASSED,
    TOOL_PATH_ALPHA, TOOL_MARKER_SIZE, TOOL_OUTLINE_WIDTH, GRID_ALPHA,
    CODE_BG_COLOR, CODE_FG_COLOR, CODE_FONT,
    CURRENT_LINE_BG, CURRENT_LINE_FG,
    HOVER_LINE_BG, HOVER_LINE_FG,
    LOG_FONT, LOG_HEIGHT,
    LOG_COLOR_INFO, LOG_COLOR_SUCCESS, LOG_COLOR_ERROR,
    LOG_COLOR_WARNING, LOG_COLOR_HIGHLIGHT,
    LOG_SEPARATOR, LOG_READY_MSG, LOG_HINT_MSG,
    LOG_SEPARATOR_CHAR, LOG_LINE_FORMAT,
    BTN_VALIDATE_TEXT, BTN_VALIDATE_WIDTH,
    BTN_GENERATE_TEXT, BTN_GENERATE_BUSY_TEXT, BTN_GENERATE_WIDTH,
    BTN_PLAY_TEXT, BTN_PAUSE_TEXT, BTN_STOP_TEXT,
    BTN_STEP_BACK_TEXT, BTN_STEP_FWD_TEXT, BTN_WIDTH,
    STATUS_WAITING, STATUS_PLAYING, STATUS_PAUSED,
    STATUS_STOPPED, STATUS_FINISHED,
    COORD_DEFAULT_TEXT, FILE_NOT_LOADED_TEXT,
    FILE_LOADING_TEXT, FILE_EMPTY_TEXT,
    LOG_FILE_PREFIX, LOG_DATE_FORMAT, LOG_DATE_FORMAT_ALT,
    MSG_NO_FILE_TITLE, MSG_NO_FILE_TEXT, MSG_ERROR_TITLE,
    MSG_SELECT_FOLDER, MSG_FOLDER_NOT_SET,
    MSG_GENERATION_ERROR, MSG_LOG_EMPTY, MSG_NOTHING_SELECTED,
    # Константы для визуализации фрезы
    TOOL_LENGTH_FACTOR,
    TOOL_CYLINDER_RESOLUTION,
    TOOL_CYLINDER_ALPHA,
    TOOL_CYLINDER_COLOR,
    # Файл настроек по умолчанию
    DEFAULT_SETTINGS_FILE,
)


class GCodeStudio:
    """Основной контроллер приложения G-Code Studio."""

    def __init__(self, root):
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        self.params = MillingParams()
        self.generator = GCodeGenerator(self.params)
        self.parser = GCodeParser()

        self.current_points: List[GCodePoint] = []
        self.code_lines: List[str] = []
        self.points_x: List[float] = []
        self.points_y: List[float] = []
        self.points_z: List[float] = []
        self.points_rapid: List[bool] = []

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

        self.theme = 'dark'
        self._search_pos = "1.0"

        self._setup_ui()
        # Загружаем настройки по умолчанию (если есть файл)
        self._load_default_settings()
        self._process_queue()

    # ----------------------------------------------------------------
    # Обработка очереди
    # ----------------------------------------------------------------
    def _process_queue(self):
        try:
            while True:
                task = self.task_queue.get_nowait()
                if task["type"] == "generation_done":
                    self._on_generation_done(task["success"], task["files"])
                elif task["type"] == "file_loaded":
                    self._on_file_loaded(
                        task["points"], task["lines"], task["filename"]
                    )
        except queue.Empty:
            pass
        self.root.after(QUEUE_POLL_INTERVAL_MS, self._process_queue)

    # ----------------------------------------------------------------
    # Создание интерфейса
    # ----------------------------------------------------------------
    def _setup_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.generator_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.generator_tab, text=TAB_GENERATOR_TITLE)
        self._setup_generator_tab()

        self.viewer_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.viewer_tab, text=TAB_VIEWER_TITLE)
        self._setup_viewer_tab()

    def _setup_generator_tab(self):
        main_frame = ttk.Frame(self.generator_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X)

        params_frame = ttk.LabelFrame(top_frame, text="Параметры обработки", padding=5)
        params_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 3))

        left_col = ttk.Frame(params_frame)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 3))

        # Поле обработки
        field_frame = ttk.LabelFrame(left_col, text="📐 Поле обработки", padding=3)
        field_frame.pack(fill=tk.X, pady=2)
        row = ttk.Frame(field_frame)
        row.pack(fill=tk.X, pady=1)
        ttk.Label(row, text="X мин:", width=10).pack(side=tk.LEFT)
        self.x_min_var = tk.DoubleVar(value=DEFAULT_X_MIN)
        ttk.Entry(row, textvariable=self.x_min_var, width=10).pack(side=tk.LEFT, padx=3)
        ttk.Label(row, text="X макс:", width=10).pack(side=tk.LEFT)
        self.x_max_var = tk.DoubleVar(value=DEFAULT_X_MAX)
        ttk.Entry(row, textvariable=self.x_max_var, width=10).pack(side=tk.LEFT, padx=3)

        row = ttk.Frame(field_frame)
        row.pack(fill=tk.X, pady=1)
        ttk.Label(row, text="Y мин:", width=10).pack(side=tk.LEFT)
        self.y_min_var = tk.DoubleVar(value=DEFAULT_Y_MIN)
        ttk.Entry(row, textvariable=self.y_min_var, width=10).pack(side=tk.LEFT, padx=3)
        ttk.Label(row, text="Y макс:", width=10).pack(side=tk.LEFT)
        self.y_max_var = tk.DoubleVar(value=DEFAULT_Y_MAX)
        ttk.Entry(row, textvariable=self.y_max_var, width=10).pack(side=tk.LEFT, padx=3)

        # Тип обработки
        milling_type_frame = ttk.LabelFrame(left_col, text="Тип обработки", padding=3)
        milling_type_frame.pack(fill=tk.X, pady=2)
        self.milling_type_var = tk.StringVar(value=DEFAULT_MILLING_TYPE)
        row = ttk.Frame(milling_type_frame)
        row.pack(fill=tk.X, pady=1)
        for val, label in MILLING_TYPES.items():
            ttk.Radiobutton(row, text=label, variable=self.milling_type_var, value=val).pack(side=tk.LEFT, padx=3)

        # Направление фрезерования
        direction_frame = ttk.LabelFrame(left_col, text="Направление фрезерования", padding=3)
        direction_frame.pack(fill=tk.X, pady=2)
        self.milling_direction_var = tk.StringVar(value=DEFAULT_MILLING_DIRECTION)
        row = ttk.Frame(direction_frame)
        row.pack(fill=tk.X, pady=1)
        for val, label in MILLING_DIRECTIONS.items():
            ttk.Radiobutton(row, text=label, variable=self.milling_direction_var, value=val).pack(side=tk.LEFT, padx=3)

        # Режим обработки (Строгание)
        backtrack_frame = ttk.LabelFrame(left_col, text=" Режим обработки", padding=3)
        backtrack_frame.pack(fill=tk.X, pady=2)
        row = ttk.Frame(backtrack_frame)
        row.pack(fill=tk.X, pady=1)
        self.backtrack_var = tk.BooleanVar(value=DEFAULT_BACKTRACK_ENABLED)
        ttk.Checkbutton(
            row,
            text="Строгание (подъём между проходами)",
            variable=self.backtrack_var,
            command=self._on_backtrack_changed
        ).pack(side=tk.LEFT, padx=3)

        # Направление контурной обработки
        contour_direction_frame = ttk.LabelFrame(left_col, text="Направление контурной обработки", padding=3)
        contour_direction_frame.pack(fill=tk.X, pady=2)
        self.contour_direction_var = tk.StringVar(value=DEFAULT_CONTOUR_DIRECTION)
        row = ttk.Frame(contour_direction_frame)
        row.pack(fill=tk.X, pady=1)
        for val, label in CONTOUR_DIRECTIONS.items():
            ttk.Radiobutton(row, text=label, variable=self.contour_direction_var, value=val).pack(side=tk.LEFT, padx=3)

        right_col = ttk.Frame(params_frame)
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(3, 0))

        # Фреза
        tool_frame = ttk.LabelFrame(right_col, text="🔧 Фреза", padding=3)
        tool_frame.pack(fill=tk.X, pady=2)
        row = ttk.Frame(tool_frame)
        row.pack(fill=tk.X, pady=1)
        ttk.Label(row, text="Диаметр (мм):", width=15).pack(side=tk.LEFT)
        self.tool_diam_var = tk.DoubleVar(value=DEFAULT_TOOL_DIAMETER)
        ttk.Entry(row, textvariable=self.tool_diam_var, width=10).pack(side=tk.LEFT, padx=3)
        ttk.Label(row, text="№ инструмента:", width=15).pack(side=tk.LEFT)
        self.tool_num_var = tk.IntVar(value=DEFAULT_TOOL_NUMBER)
        ttk.Entry(row, textvariable=self.tool_num_var, width=10).pack(side=tk.LEFT, padx=3)

        row = ttk.Frame(tool_frame)
        row.pack(fill=tk.X, pady=1)
        ttk.Label(row, text="Шаг (stepover):", width=15).pack(side=tk.LEFT)
        self.stepover_var = tk.DoubleVar(value=DEFAULT_STEPOVER)
        ttk.Entry(row, textvariable=self.stepover_var, width=10).pack(side=tk.LEFT, padx=3)

        # Припуск
        allowance_frame = ttk.LabelFrame(right_col, text="📏 Припуск", padding=3)
        allowance_frame.pack(fill=tk.X, pady=2)
        row = ttk.Frame(allowance_frame)
        row.pack(fill=tk.X, pady=1)
        ttk.Label(row, text="Припуск (мм):", width=15).pack(side=tk.LEFT)
        self.allowance_var = tk.DoubleVar(value=DEFAULT_ALLOWANCE)
        ttk.Entry(row, textvariable=self.allowance_var, width=10).pack(side=tk.LEFT, padx=3)
        ttk.Label(row, text="(0 = без выхода за границы)", foreground="gray").pack(side=tk.LEFT, padx=3)

        # Глубина обработки
        z_frame = ttk.LabelFrame(right_col, text="📏 Глубина обработки", padding=3)
        z_frame.pack(fill=tk.X, pady=2)
        row = ttk.Frame(z_frame)
        row.pack(fill=tk.X, pady=1)
        ttk.Label(row, text="Z старт:", width=10).pack(side=tk.LEFT)
        self.z_start_var = tk.DoubleVar(value=DEFAULT_Z_START)
        ttk.Entry(row, textvariable=self.z_start_var, width=10).pack(side=tk.LEFT, padx=3)
        ttk.Label(row, text="Z конец:", width=10).pack(side=tk.LEFT)
        self.z_end_var = tk.DoubleVar(value=DEFAULT_Z_END)
        ttk.Entry(row, textvariable=self.z_end_var, width=10).pack(side=tk.LEFT, padx=3)
        ttk.Label(row, text="Шаг по Z:", width=10).pack(side=tk.LEFT)
        self.z_step_var = tk.DoubleVar(value=DEFAULT_Z_STEP)
        ttk.Entry(row, textvariable=self.z_step_var, width=10).pack(side=tk.LEFT, padx=3)

        row = ttk.Frame(z_frame)
        row.pack(fill=tk.X, pady=1)
        ttk.Label(row, text="Безопасная Z:", width=15).pack(side=tk.LEFT)
        self.safe_z_var = tk.DoubleVar(value=DEFAULT_SAFE_Z)
        ttk.Entry(row, textvariable=self.safe_z_var, width=10).pack(side=tk.LEFT, padx=3)

        # Подачи и скорость
        feed_frame = ttk.LabelFrame(right_col, text="⚡ Подачи и скорость", padding=3)
        feed_frame.pack(fill=tk.X, pady=2)
        row = ttk.Frame(feed_frame)
        row.pack(fill=tk.X, pady=1)
        ttk.Label(row, text="Подача XY:", width=15).pack(side=tk.LEFT)
        self.feed_xy_var = tk.IntVar(value=DEFAULT_FEED_XY)
        ttk.Entry(row, textvariable=self.feed_xy_var, width=10).pack(side=tk.LEFT, padx=3)
        ttk.Label(row, text="Подача Z:", width=15).pack(side=tk.LEFT)
        self.feed_z_var = tk.IntVar(value=DEFAULT_FEED_Z)
        ttk.Entry(row, textvariable=self.feed_z_var, width=10).pack(side=tk.LEFT, padx=3)
        ttk.Label(row, text="Обороты:", width=10).pack(side=tk.LEFT)
        self.spindle_var = tk.IntVar(value=DEFAULT_SPINDLE_SPEED)
        ttk.Entry(row, textvariable=self.spindle_var, width=10).pack(side=tk.LEFT, padx=3)

        row = ttk.Frame(feed_frame)
        row.pack(fill=tk.X, pady=1)
        ttk.Label(row, text="G0 скорость:", width=15).pack(side=tk.LEFT)
        self.rapid_feed_var = tk.IntVar(value=DEFAULT_RAPID_FEED)
        ttk.Entry(row, textvariable=self.rapid_feed_var, width=10).pack(side=tk.LEFT, padx=3)
        ttk.Label(row, text="мм/мин (быстрые перемещения)", foreground="gray").pack(side=tk.LEFT, padx=3)

        # Разбивка на файлы
        file_frame = ttk.LabelFrame(right_col, text="📁 Разбивка на файлы", padding=3)
        file_frame.pack(fill=tk.X, pady=2)
        row = ttk.Frame(file_frame)
        row.pack(fill=tk.X, pady=1)
        ttk.Label(row, text="Проходов на файл:", width=20).pack(side=tk.LEFT)
        self.passes_var = tk.IntVar(value=DEFAULT_PASSES_PER_FILE)
        ttk.Entry(row, textvariable=self.passes_var, width=10).pack(side=tk.LEFT, padx=3)

        row = ttk.Frame(file_frame)
        row.pack(fill=tk.X, pady=1)
        ttk.Label(row, text="Папка:", width=10).pack(side=tk.LEFT)
        self.dir_var = tk.StringVar(value=os.path.expanduser("~"))
        ttk.Entry(row, textvariable=self.dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        ttk.Button(row, text="📂", command=self._open_output_folder, width=3).pack(side=tk.LEFT, padx=1)
        ttk.Button(row, text="...", command=self._select_dir, width=2).pack(side=tk.LEFT)

        # Кнопки действий
        btn_frame = ttk.LabelFrame(top_frame, text="Действия", padding=5)
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(3, 0))

        ttk.Button(btn_frame, text=BTN_VALIDATE_TEXT, command=self._validate, width=BTN_VALIDATE_WIDTH).pack(pady=2)
        self.btn_generate = ttk.Button(btn_frame, text=BTN_GENERATE_TEXT, command=self._generate, width=BTN_GENERATE_WIDTH)
        self.btn_generate.pack(pady=2)
        # Кнопка сохранения в файл по умолчанию
        ttk.Button(btn_frame, text="💾 Сохранить настройки", command=self._save_settings, width=BTN_VALIDATE_WIDTH).pack(pady=2)
        # Кнопка сохранения как...
        ttk.Button(btn_frame, text="💾 Сохранить как...", command=self._save_settings_as, width=BTN_VALIDATE_WIDTH).pack(pady=2)
        # Кнопка загрузки из файла
        ttk.Button(btn_frame, text="📂 Загрузить настройки", command=self._load_settings, width=BTN_VALIDATE_WIDTH).pack(pady=2)

        # Лог
        log_frame = ttk.LabelFrame(main_frame, text="📋 Лог операций", padding=3)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(3, 0))

        log_btn_frame = ttk.Frame(log_frame)
        log_btn_frame.pack(fill=tk.X, pady=(0, 3))
        ttk.Button(log_btn_frame, text="📋 Копировать выделенное", command=self._copy_log_selection).pack(side=tk.LEFT, padx=1)
        ttk.Button(log_btn_frame, text="📋 Копировать весь лог", command=self._copy_all_log).pack(side=tk.LEFT, padx=1)
        ttk.Button(log_btn_frame, text="🗑️ Очистить лог", command=self._clear_log).pack(side=tk.LEFT, padx=1)
        ttk.Button(log_btn_frame, text="💾 Сохранить лог", command=self._save_log_manual).pack(side=tk.LEFT, padx=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, font=LOG_FONT, height=6)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.log_text.tag_configure("info", foreground=LOG_COLOR_INFO)
        self.log_text.tag_configure("success", foreground=LOG_COLOR_SUCCESS)
        self.log_text.tag_configure("error", foreground=LOG_COLOR_ERROR)
        self.log_text.tag_configure("warning", foreground=LOG_COLOR_WARNING)
        self.log_text.tag_configure("highlight", foreground=LOG_COLOR_HIGHLIGHT, font=('Consolas', 10, 'bold'))

        self._log(LOG_READY_MSG, "info")
        self._log(LOG_HINT_MSG, "info")

    def _setup_viewer_tab(self):
        if not MATPLOTLIB_AVAILABLE:
            ttk.Label(self.viewer_tab, text="⚠ Matplotlib не установлен!", font=("Arial", 14)).pack(expand=True)
            return

        control_frame = ttk.Frame(self.viewer_tab)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(control_frame, text="📂 Открыть файл", command=self._open_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="📊 Статистика", command=self._show_statistics).pack(side=tk.LEFT, padx=5)

        self.btn_edit = ttk.Button(control_frame, text="✏️ Редактировать", command=self._toggle_edit_mode)
        self.btn_edit.pack(side=tk.LEFT, padx=5)
        self.btn_apply_edit = ttk.Button(control_frame, text="✅ Применить", command=self._apply_edit, state=tk.DISABLED)
        self.btn_apply_edit.pack(side=tk.LEFT, padx=5)

        anim_frame = ttk.LabelFrame(control_frame, text=" Анимация", padding=5)
        anim_frame.pack(side=tk.LEFT, padx=10)

        self.btn_play = ttk.Button(anim_frame, text=BTN_PLAY_TEXT, command=self._anim_play, width=BTN_WIDTH)
        self.btn_play.pack(side=tk.LEFT, padx=2)
        self.btn_pause = ttk.Button(anim_frame, text=BTN_PAUSE_TEXT, command=self._anim_pause, width=BTN_WIDTH, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT, padx=2)
        self.btn_stop = ttk.Button(anim_frame, text=BTN_STOP_TEXT, command=self._anim_stop, width=BTN_WIDTH, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=2)

        step_frame = ttk.Frame(anim_frame)
        step_frame.pack(side=tk.LEFT, padx=10)
        self.btn_step_back = ttk.Button(step_frame, text=BTN_STEP_BACK_TEXT, command=self._anim_step_back, width=BTN_WIDTH, state=tk.DISABLED)
        self.btn_step_back.pack(side=tk.LEFT, padx=2)
        self.btn_step_fwd = ttk.Button(step_frame, text=BTN_STEP_FWD_TEXT, command=self._anim_step_forward, width=BTN_WIDTH, state=tk.DISABLED)
        self.btn_step_fwd.pack(side=tk.LEFT, padx=2)

        speed_frame = ttk.Frame(anim_frame)
        speed_frame.pack(side=tk.LEFT, padx=10)
        ttk.Label(speed_frame, text="Скорость:").pack(side=tk.LEFT)
        self.speed_var = tk.IntVar(value=DEFAULT_ANIMATION_SPEED)
        ttk.Combobox(speed_frame, textvariable=self.speed_var, values=ANIMATION_SPEEDS, width=4, state="readonly").pack(side=tk.LEFT, padx=3)

        ttk.Label(control_frame, text="Проекция:").pack(side=tk.LEFT, padx=(20, 5))
        self.projection_var = tk.StringVar(value=DEFAULT_PROJECTION)
        projection_combo = ttk.Combobox(control_frame, textvariable=self.projection_var, values=PROJECTIONS, state="readonly", width=6)
        projection_combo.pack(side=tk.LEFT)
        projection_combo.bind("<<ComboboxSelected>>", lambda e: self._on_projection_changed())

        self.file_label = ttk.Label(control_frame, text=FILE_NOT_LOADED_TEXT, foreground="gray")
        self.file_label.pack(side=tk.LEFT, padx=20)

        self.progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(self.viewer_tab, variable=self.progress_var, maximum=100).pack(fill=tk.X, padx=10, pady=2)

        self.coord_label = ttk.Label(self.viewer_tab, text=COORD_DEFAULT_TEXT, font=("Consolas", 11, "bold"), foreground="blue")
        self.coord_label.pack(fill=tk.X, padx=10, pady=2)

        self.status_label = ttk.Label(self.viewer_tab, text=STATUS_WAITING, foreground="gray")
        self.status_label.pack(fill=tk.X, padx=10, pady=2)

        content_frame = ttk.Frame(self.viewer_tab)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        plot_frame = ttk.Frame(content_frame)
        plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.fig = Figure(figsize=(FIGURE_WIDTH, FIGURE_HEIGHT), dpi=FIGURE_DPI)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        NavigationToolbar2Tk(self.canvas, plot_frame).update()
        self.canvas.get_tk_widget().bind("<Configure>", self._on_window_resize)

        code_frame = ttk.LabelFrame(content_frame, text=" G-код (клик по строке → переход к точке)", padding=5)
        code_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

        code_scroll = ttk.Scrollbar(code_frame, orient=tk.VERTICAL)
        code_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.code_text = tk.Text(
            code_frame,
            wrap=tk.NONE,
            font=CODE_FONT,
            yscrollcommand=code_scroll.set,
            state=tk.DISABLED,
            bg=CODE_BG_COLOR,
            fg=CODE_FG_COLOR,
            cursor="hand2",
        )
        self.code_text.pack(fill=tk.BOTH, expand=True)
        code_scroll.config(command=self.code_text.yview)

        self.code_text.tag_configure("current_line", background=CURRENT_LINE_BG, foreground=CURRENT_LINE_FG)
        self.code_text.tag_configure("hover_line", background=HOVER_LINE_BG, foreground=HOVER_LINE_FG)

        self.code_text.bind("<Button-1>", self._on_code_click)
        self.code_text.bind("<Motion>", self._on_code_hover)
        self.code_text.bind("<Leave>", lambda e: self._clear_hover())

    # ----------------------------------------------------------------
    # Обработка resize
    # ----------------------------------------------------------------
    def _on_window_resize(self, event):
        if self._resize_after_id:
            self.root.after_cancel(self._resize_after_id)
        self._resize_after_id = self.root.after(RESIZE_DEBOUNCE_MS, self._update_plot)

    # ----------------------------------------------------------------
    # Клик и наведение по коду
    # ----------------------------------------------------------------
    def _on_code_click(self, event):
        if not self.current_points or not self.code_lines:
            return
        try:
            line_idx = int(self.code_text.index(f"@{event.x},{event.y}").split(".")[0])
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
        self.status_label.config(text=f"Статус: Переход к строке {line_idx}", foreground="purple")

    def _on_code_hover(self, event):
        try:
            line_idx = int(self.code_text.index(f"@{event.x},{event.y}").split(".")[0])
        except Exception:
            return
        self._clear_hover()
        if 1 <= line_idx <= len(self.code_lines):
            self.code_text.tag_add("hover_line", f"{line_idx}.0", f"{line_idx}.end")

    def _clear_hover(self):
        self.code_text.tag_remove("hover_line", "1.0", tk.END)

    # ----------------------------------------------------------------
    # Анимация (поддержка XY, XZ, YZ, 3D с цилиндром)
    # ----------------------------------------------------------------
    def _render_at_frame(self, end_idx: int, highlight_line=None):
        if not self.current_points:
            return

        proj = self.projection_var.get()
        total = len(self.current_points)
        pct = (end_idx / total * 100) if total > 0 else 0
        self.progress_var.set(pct)

        # Выбираем координаты для проекции
        if proj == 'XY':
            xs, ys, zs = self.points_x, self.points_y, self.points_z
            x_label, y_label = 'X', 'Y'
            is_3d = False
        elif proj == 'XZ':
            xs, ys, zs = self.points_x, self.points_z, self.points_y
            x_label, y_label = 'X', 'Z'
            is_3d = False
        elif proj == 'YZ':
            xs, ys, zs = self.points_y, self.points_z, self.points_x
            x_label, y_label = 'Y', 'Z'
            is_3d = False
        elif proj == '3D':
            xs, ys, zs = self.points_x, self.points_y, self.points_z
            x_label, y_label = 'X', 'Y'
            is_3d = True
        else:
            xs, ys, zs = self.points_x, self.points_y, self.points_z
            x_label, y_label = 'X', 'Y'
            is_3d = False

        # При end_idx == 0 показываем первую точку
        if 0 <= end_idx <= total:
            cur_idx = max(0, end_idx - 1)
            cur = self.current_points[cur_idx]
            mode = "G0 (Холостой)" if cur.rapid else "G1 (Рабочий)"
            color = COLOR_RAPID if cur.rapid else COLOR_WORKING
            position_info = " (начало)" if end_idx == 0 else ""
            if proj == 'XY':
                coord_text = f"📍 X: {cur.x:.3f}  Y: {cur.y:.3f}  Z: {cur.z:.3f}"
            elif proj == 'XZ':
                coord_text = f"📍 X: {cur.x:.3f}  Z: {cur.z:.3f}  Y: {cur.y:.3f}"
            elif proj == 'YZ':
                coord_text = f"📍 Y: {cur.y:.3f}  Z: {cur.z:.3f}  X: {cur.x:.3f}"
            else:  # 3D
                coord_text = f"📍 X: {cur.x:.3f}  Y: {cur.y:.3f}  Z: {cur.z:.3f}"
            self.coord_label.config(
                text=f"{coord_text}  |  {mode}{position_info}",
                foreground=color,
            )
            if highlight_line is None:
                highlight_line = cur.line_number

        self._is_drawing = True
        try:
            self.ax.clear()

            if is_3d:
                # 3D-анимация с цилиндром фрезы
                self.ax = self.fig.add_subplot(111, projection='3d')
                # Вся траектория – серая линия
                self.ax.plot(xs, ys, zs, color=COLOR_TRAJECTORY_BG, linewidth=0.5, alpha=0.5)
                # Пройденный путь – синяя линия
                if end_idx > 0:
                    self.ax.plot(xs[:end_idx], ys[:end_idx], zs[:end_idx],
                                 color=COLOR_WORKING, linewidth=1.0, alpha=0.7)
                # Рабочие и холостые точки (до текущей позиции)
                if end_idx > 0:
                    rapid_x = [xs[i] for i in range(end_idx) if self.points_rapid[i]]
                    rapid_y = [ys[i] for i in range(end_idx) if self.points_rapid[i]]
                    rapid_z = [zs[i] for i in range(end_idx) if self.points_rapid[i]]
                    work_x = [xs[i] for i in range(end_idx) if not self.points_rapid[i]]
                    work_y = [ys[i] for i in range(end_idx) if not self.points_rapid[i]]
                    work_z = [zs[i] for i in range(end_idx) if not self.points_rapid[i]]
                    if rapid_x:
                        self.ax.scatter(rapid_x, rapid_y, rapid_z, c='red', s=2, alpha=0.3, label='G0')
                    if work_x:
                        self.ax.scatter(work_x, work_y, work_z, c='blue', s=2, alpha=0.6, label='G1')

                # Текущая позиция: рисуем цилиндр фрезы
                if end_idx > 0:
                    cur_idx = min(end_idx - 1, total - 1)
                    cx, cy, cz = xs[cur_idx], ys[cur_idx], zs[cur_idx]
                    radius = self.params.tool_diameter / 2.0
                    height = radius * 2 * TOOL_LENGTH_FACTOR

                    res = TOOL_CYLINDER_RESOLUTION
                    theta = np.linspace(0, 2 * np.pi, res)
                    x_cyl = np.outer(np.cos(theta), np.array([0, 1])) * radius + cx
                    y_cyl = np.outer(np.sin(theta), np.array([0, 1])) * radius + cy
                    z_cyl = np.outer(np.ones(res), np.array([0, height])) + cz

                    self.ax.plot_surface(x_cyl, y_cyl, z_cyl,
                                         color=TOOL_CYLINDER_COLOR,
                                         alpha=TOOL_CYLINDER_ALPHA,
                                         rstride=1, cstride=1, shade=True)

                    circle_bottom = np.linspace(0, 2*np.pi, res)
                    x_bot = radius * np.cos(circle_bottom) + cx
                    y_bot = radius * np.sin(circle_bottom) + cy
                    z_bot = np.full_like(x_bot, cz)
                    self.ax.plot(x_bot, y_bot, z_bot, color='gray', linewidth=0.8, alpha=0.6)
                    x_top = radius * np.cos(circle_bottom) + cx
                    y_top = radius * np.sin(circle_bottom) + cy
                    z_top = np.full_like(x_top, cz + height)
                    self.ax.plot(x_top, y_top, z_top, color='gray', linewidth=0.8, alpha=0.6)

                    self.ax.text(cx, cy, cz + height + 5, f'  {cur.line_number}',
                                 color='white', fontsize=8, zorder=11)

                self.ax.set_xlabel('X')
                self.ax.set_ylabel('Y')
                self.ax.set_zlabel('Z')
                self.ax.legend(loc="upper right", fontsize=8)
                self.ax.set_box_aspect([1, 1, 0.5])
                self.ax.autoscale()

                for axis in [self.ax.xaxis, self.ax.yaxis, self.ax.zaxis]:
                    axis.set_major_locator(mticker.MaxNLocator(6))
                    axis.set_major_formatter(mticker.ScalarFormatter(useOffset=False))
                    axis.get_major_formatter().set_scientific(False)
                    axis.get_major_formatter().set_useOffset(False)

            else:
                # 2D-проекции
                self.ax = self.fig.add_subplot(111)
                self.ax.plot(xs, ys, color=COLOR_TRAJECTORY_BG, linewidth=LINE_WIDTH_TRAJECTORY, alpha=LINE_ALPHA_TRAJECTORY)
                if end_idx > 0:
                    self.ax.plot(xs[:end_idx], ys[:end_idx], color=COLOR_WORKING, linewidth=LINE_WIDTH_PASSED, alpha=LINE_ALPHA_PASSED)

                if proj == 'XY':
                    bbox = self.ax.get_window_extent()
                    x_range = self.params.x_max - self.params.x_min
                    if x_range > 0:
                        points_per_mm = bbox.width / x_range
                        tool_diameter_pts = self.params.tool_diameter * points_per_mm
                    else:
                        tool_diameter_pts = self.params.tool_diameter * 2.5
                else:
                    tool_diameter_pts = self.params.tool_diameter * 2.5

                work_indices = [i for i in range(end_idx) if not self.points_rapid[i]]
                if len(work_indices) > 1:
                    working_x = [xs[i] for i in work_indices]
                    working_y = [ys[i] for i in work_indices]
                    points_array = np.column_stack([working_x, working_y])
                    segments = np.stack([points_array[:-1], points_array[1:]], axis=1)
                    lc = LineCollection(segments, linewidths=tool_diameter_pts, colors=COLOR_TOOL_PATH,
                                        alpha=TOOL_PATH_ALPHA, capstyle="round", joinstyle="round")
                    self.ax.add_collection(lc)

                if end_idx > 0:
                    cur_idx = min(end_idx - 1, total - 1)
                    cx, cy = xs[cur_idx], ys[cur_idx]
                    self.ax.plot(cx, cy, "ro", markersize=TOOL_MARKER_SIZE, zorder=10)
                    if proj == 'XY':
                        tool_r = self.params.tool_diameter / 2.0
                        self.ax.add_patch(Circle((cx, cy), tool_r, fill=False, color=COLOR_TOOL_MARKER,
                                                 linewidth=TOOL_OUTLINE_WIDTH, zorder=9))

                if proj == 'XY':
                    self.ax.set_xlim(self.params.x_min - VIEW_MARGIN, self.params.x_max + VIEW_MARGIN)
                    self.ax.set_ylim(self.params.y_min - VIEW_MARGIN, self.params.y_max + VIEW_MARGIN)
                    self.ax.set_aspect('equal')
                else:
                    if xs:
                        x_min, x_max = min(xs), max(xs)
                        margin_x = (x_max - x_min) * 0.05 if x_max != x_min else 1
                        self.ax.set_xlim(x_min - margin_x, x_max + margin_x)
                    if ys:
                        y_min, y_max = min(ys), max(ys)
                        margin_y = (y_max - y_min) * 0.05 if y_max != y_min else 1
                        self.ax.set_ylim(y_min - margin_y, y_max + margin_y)

                self.ax.set_xlabel(x_label)
                self.ax.set_ylabel(y_label)
                self.ax.grid(True, alpha=GRID_ALPHA)

                self.ax.xaxis.set_major_locator(mticker.MaxNLocator(6))
                self.ax.xaxis.set_major_formatter(mticker.ScalarFormatter(useOffset=False))
                self.ax.xaxis.get_major_formatter().set_scientific(False)
                self.ax.xaxis.get_major_formatter().set_useOffset(False)

                self.ax.yaxis.set_major_locator(mticker.MaxNLocator(6))
                self.ax.yaxis.set_major_formatter(mticker.ScalarFormatter(useOffset=False))
                self.ax.yaxis.get_major_formatter().set_scientific(False)
                self.ax.yaxis.get_major_formatter().set_useOffset(False)

            # Заголовок
            if end_idx > 0:
                cur_idx = min(end_idx - 1, total - 1)
                cur = self.current_points[cur_idx]
                pos_text = f"{x_label}: {cur.x:.2f}  {y_label}: {cur.y:.2f}" if not is_3d else f"X:{cur.x:.2f} Y:{cur.y:.2f} Z:{cur.z:.2f}"
                self.ax.set_title(f"Анимация | {pos_text}  | Строка {cur.line_number}{' (начало)' if end_idx == 1 else ''}")

            self.canvas.draw_idle()

        except Exception as e:
            self._log(f"❌ Ошибка отрисовки: {e}", "error")
        finally:
            self._is_drawing = False

        if highlight_line:
            self._highlight_code_line(highlight_line)

    def _on_projection_changed(self):
        if self.anim_running or self.anim_paused:
            self._render_at_frame(self.anim_frame)
        else:
            self._update_plot()

    # ----------------------------------------------------------------
    # Управление анимацией
    # ----------------------------------------------------------------
    def _anim_play(self):
        if not self.current_points:
            messagebox.showwarning(MSG_NO_FILE_TITLE, MSG_NO_FILE_TEXT)
            return
        if self.anim_paused:
            self.anim_paused = False
            self.anim_running = True
            self._update_step_buttons()
            self.status_label.config(text=STATUS_PLAYING, foreground="green")
            self._animate_step()
            return
        self.anim_frame = 0
        self.anim_running = True
        self.anim_paused = False
        self._update_step_buttons()
        self.status_label.config(text=STATUS_PLAYING, foreground="green")
        self._animate_step()

    def _anim_pause(self):
        self.anim_paused = True
        self.anim_running = False
        if self.anim_after_id:
            self.root.after_cancel(self.anim_after_id)
        self._update_step_buttons()
        self.status_label.config(text=STATUS_PAUSED, foreground="orange")

    def _anim_stop(self):
        self.anim_running = False
        self.anim_paused = False
        self.anim_frame = 0
        if self.anim_after_id:
            self.root.after_cancel(self.anim_after_id)
        self.progress_var.set(0)
        self.coord_label.config(text=COORD_DEFAULT_TEXT)
        self._update_step_buttons()
        self.status_label.config(text=STATUS_STOPPED, foreground="red")
        self.code_text.tag_remove("current_line", "1.0", tk.END)
        self._update_plot()

    def _anim_step_forward(self):
        if not self.current_points:
            return
        self.anim_frame = min(self.anim_frame + 1, len(self.current_points))
        self._render_at_frame(self.anim_frame)
        self.status_label.config(text=f"Статус: Шаг вперёд ({self.anim_frame}/{len(self.current_points)})", foreground="purple")

    def _anim_step_back(self):
        if not self.current_points:
            return
        self.anim_frame = max(0, self.anim_frame - 1)
        self._render_at_frame(self.anim_frame)
        self.status_label.config(text=f"Статус: Шаг назад ({self.anim_frame}/{len(self.current_points)})", foreground="purple")

    def _update_step_buttons(self):
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
        if not self.anim_running:
            return
        if self._is_drawing:
            self.anim_after_id = self.root.after(ANIMATION_SKIP_DRAWING_DELAY, self._animate_step)
            return
        speed = self.speed_var.get()
        if speed < MIN_ANIMATION_SPEED:
            speed = MIN_ANIMATION_SPEED
            self.speed_var.set(speed)
            self._log(f"⚠ Скорость анимации была <= 0, установлено значение {speed}", "warning")
        total = len(self.current_points)
        self.anim_frame = max(0, min(self.anim_frame + speed, total))
        self._render_at_frame(self.anim_frame)
        if self.anim_frame >= total:
            self.anim_running = False
            self.anim_paused = False
            self._update_step_buttons()
            self.status_label.config(text=STATUS_FINISHED, foreground="green")
        else:
            self.anim_after_id = self.root.after(ANIMATION_INTERVAL_MS, self._animate_step)

    # ----------------------------------------------------------------
    # Подсветка и отображение кода
    # ----------------------------------------------------------------
    def _highlight_code_line(self, line_num: int):
        self.code_text.tag_remove("current_line", "1.0", tk.END)
        if line_num <= 0 or line_num > len(self.code_lines):
            return
        start_idx = f"{line_num}.0"
        end_idx = f"{line_num}.end"
        self.code_text.tag_add("current_line", start_idx, end_idx)
        self.code_text.see(start_idx)

    def _display_code(self):
        self.code_text.config(state=tk.NORMAL)
        self.code_text.delete("1.0", tk.END)
        for i, line in enumerate(self.code_lines, 1):
            self.code_text.insert(tk.END, LOG_LINE_FORMAT.format(i=i, line=line) + "\n")
        self.code_text.config(state=tk.DISABLED if self.btn_edit.cget('text') == "✏️ Редактировать" else tk.NORMAL)

    # ----------------------------------------------------------------
    # Логирование
    # ----------------------------------------------------------------
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
                if t.startswith("viewlink_"):
                    tag_name = t
                    break
        if tag_name and tag_name in self.view_links:
            filepath = self.view_links[tag_name]
            if os.path.exists(filepath):
                try:
                    GCodeViewerWindow(self.root, filepath, theme=self.theme)
                except Exception as e:
                    self._log(f"❌ Ошибка открытия окна просмотра: {e}", "error")
            else:
                messagebox.showerror("Ошибка", f"Файл не найден:\n{filepath}")

    def _on_viz_link_click(self, event, tag_name=None):
        if not tag_name:
            idx = self.log_text.index(f"@{event.x},{event.y}")
            for t in self.log_text.tag_names(idx):
                if t.startswith("vizlink_"):
                    tag_name = t
                    break
        if tag_name and tag_name in self.viz_links:
            self._load_file_to_viewer(self.viz_links[tag_name])

    # ----------------------------------------------------------------
    # Работа с папками
    # ----------------------------------------------------------------
    def _open_output_folder(self):
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
            if sys.platform == "win32":
                os.startfile(folder_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder_path])
            else:
                subprocess.Popen(["xdg-open", folder_path])
        except Exception as e:
            messagebox.showerror(MSG_ERROR_TITLE, str(e))

    def _select_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.dir_var.set(d)

    def _on_backtrack_changed(self):
        enabled = self.backtrack_var.get()
        if enabled:
            self._log("🔄 Включён режим 'Строгание' — фреза будет подниматься между проходами", "info")
        else:
            self._log("🔄 Включён режим 'Непрерывный зигзаг'", "info")

    # ----------------------------------------------------------------
    # Параметры и валидация
    # ----------------------------------------------------------------
    def _update_params(self):
        try:
            self.params = MillingParams(
                x_min=self.x_min_var.get(),
                x_max=self.x_max_var.get(),
                y_min=self.y_min_var.get(),
                y_max=self.y_max_var.get(),
                tool_diameter=self.tool_diam_var.get(),
                stepover=self.stepover_var.get(),
                z_start=self.z_start_var.get(),
                z_end=self.z_end_var.get(),
                z_step=self.z_step_var.get(),
                safe_z=self.safe_z_var.get(),
                feed_xy=self.feed_xy_var.get(),
                feed_z=self.feed_z_var.get(),
                rapid_feed=self.rapid_feed_var.get(),
                tool_number=self.tool_num_var.get(),
                spindle_speed=self.spindle_var.get(),
                passes_per_file=self.passes_var.get(),
                milling_type=self.milling_type_var.get(),
                milling_direction=self.milling_direction_var.get(),
                contour_direction=self.contour_direction_var.get(),
                allowance=self.allowance_var.get(),
                backtrack_enabled=self.backtrack_var.get(),
            )
            self.generator.params = self.params
            return True
        except Exception as e:
            messagebox.showerror(MSG_ERROR_TITLE, str(e))
            return False

    def _validate(self):
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
            self._log(f" Подача G0: {self.params.rapid_feed} мм/мин", "info")
            if self.params.backtrack_enabled:
                self._log("🔄 Режим: Строгание (подъём между проходами)", "info")
            else:
                self._log("🔄 Режим: Непрерывный зигзаг", "info")
            if self.current_points:
                time_str = self._calculate_machining_time()
                self._log(f"⏱️ Расчётное время обработки: {time_str}", "highlight")
        else:
            self._log(f"❌ {msg}", "error")
        self._log(LOG_SEPARATOR, "highlight")

    def _calculate_machining_time(self) -> str:
        if not self.current_points or len(self.current_points) < 2:
            return "0 мин 0 сек"
        total_time_min = 0.0
        prev_pt = self.current_points[0]
        for i in range(1, len(self.current_points)):
            curr_pt = self.current_points[i]
            dx = curr_pt.x - prev_pt.x
            dy = curr_pt.y - prev_pt.y
            dz = curr_pt.z - prev_pt.z
            distance = math.sqrt(dx**2 + dy**2 + dz**2)
            if distance < 0.001:
                prev_pt = curr_pt
                continue
            if curr_pt.rapid:
                speed = self.params.rapid_feed
            else:
                if abs(dz) > 0.001:
                    speed = self.params.feed_z
                else:
                    speed = self.params.feed_xy
            if speed <= 0:
                speed = 1
            total_time_min += distance / speed
            prev_pt = curr_pt
        minutes = int(total_time_min)
        seconds = int(round((total_time_min - minutes) * 60))
        if seconds == 60:
            minutes += 1
            seconds = 0
        return f"{minutes} мин {seconds} сек"

    # ----------------------------------------------------------------
    # Генерация
    # ----------------------------------------------------------------
    def _generate(self):
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
        try:
            success, files = self.generator.generate_to_files(output_dir)
            self.task_queue.put({"type": "generation_done", "success": success, "files": files})
        except Exception:
            self.task_queue.put({"type": "generation_done", "success": False, "files": []})

    def _on_generation_done(self, success: bool, files: List[str]):
        self._is_generating = False
        self.btn_generate.config(state=tk.NORMAL, text=BTN_GENERATE_TEXT)
        if success:
            self._log(f"✅ Создано файлов: {len(files)}", "success")
            for fp in files:
                self._log_file_links(fp)
        else:
            self._log(MSG_GENERATION_ERROR, "error")

    # ----------------------------------------------------------------
    # Загрузка и парсинг
    # ----------------------------------------------------------------
    def _open_file(self):
        fp = filedialog.askopenfilename(filetypes=[("G-code", "*.nc *.gcode *.txt"), ("All", "*.*")])
        if fp:
            self.file_label.config(text=FILE_LOADING_TEXT, foreground="orange")
            thread = threading.Thread(target=self._parse_file_worker, args=(fp,), daemon=True)
            thread.start()

    def _parse_file_worker(self, filepath: str):
        try:
            points, lines = self.parser.parse_file(filepath)
            self.task_queue.put({"type": "file_loaded", "points": points, "lines": lines, "filename": os.path.basename(filepath)})
        except Exception:
            self.task_queue.put({"type": "file_loaded", "points": [], "lines": [], "filename": ""})

    def _on_file_loaded(self, points: List[GCodePoint], lines: List[str], filename: str):
        if not points:
            self.file_label.config(text=FILE_EMPTY_TEXT, foreground="red")
            self._log("❌ Файл пуст или не содержит координат", "error")
            return
        self.current_points = points
        self.code_lines = lines
        self.points_x = [p.x for p in points]
        self.points_y = [p.y for p in points]
        self.points_z = [p.z for p in points]
        self.points_rapid = [p.rapid for p in points]
        self.anim_frame = 0
        self.anim_running = False
        self.anim_paused = False
        self._update_step_buttons()
        self._display_code()
        self.file_label.config(text=filename, foreground="black")
        self.notebook.select(self.viewer_tab)
        self._search_pos = "1.0"
        self._update_plot()
        self._log(f"✅ Загружено точек: {len(points)}, строк: {len(lines)}", "success")
        time_str = self._calculate_machining_time()
        self._log(f"⏱️ Расчётное время обработки файла: {time_str}", "highlight")
        self._show_statistics()

    def _load_file_to_viewer(self, filepath: str):
        self._log(f"📥 Загрузка: {os.path.basename(filepath)}", "info")
        try:
            points, lines = self.parser.parse_file(filepath)
        except Exception as e:
            self._log(f"❌ Ошибка загрузки: {e}", "error")
            return
        if not points:
            self._log("❌ Файл пуст или не содержит координат", "error")
            return
        self.current_points = points
        self.code_lines = lines
        self.points_x = [p.x for p in points]
        self.points_y = [p.y for p in points]
        self.points_z = [p.z for p in points]
        self.points_rapid = [p.rapid for p in points]
        self.anim_frame = 0
        self.anim_running = False
        self.anim_paused = False
        self._update_step_buttons()
        self._display_code()
        self.file_label.config(text=os.path.basename(filepath), foreground="black")
        self.notebook.select(self.viewer_tab)
        self._search_pos = "1.0"
        self._update_plot()
        time_str = self._calculate_machining_time()
        self._log(f"⏱️ Расчётное время обработки файла: {time_str}", "highlight")
        self._show_statistics()

    # ----------------------------------------------------------------
    # Статистика
    # ----------------------------------------------------------------
    def _calculate_statistics(self) -> dict:
        if not self.current_points:
            return {}
        points = self.current_points
        total_rapid_dist = 0.0
        total_work_dist = 0.0
        max_step = 0.0
        min_z = float('inf')
        max_z = -float('inf')
        prev = points[0]
        for i in range(1, len(points)):
            curr = points[i]
            dx = curr.x - prev.x
            dy = curr.y - prev.y
            dz = curr.z - prev.z
            dist = math.sqrt(dx*dx + dy*dy + dz*dz)
            if curr.rapid:
                total_rapid_dist += dist
            else:
                total_work_dist += dist
            if dist > max_step:
                max_step = dist
            if curr.z < min_z:
                min_z = curr.z
            if curr.z > max_z:
                max_z = curr.z
            prev = curr
        total_dist = total_rapid_dist + total_work_dist
        return {
            "total_points": len(points),
            "total_dist": total_dist,
            "rapid_dist": total_rapid_dist,
            "work_dist": total_work_dist,
            "max_step": max_step,
            "min_z": min_z,
            "max_z": max_z,
        }

    def _show_statistics(self):
        stats = self._calculate_statistics()
        if not stats:
            self._log("⚠ Нет данных для статистики", "warning")
            return
        self._log(LOG_SEPARATOR, "highlight")
        self._log("📊 СТАТИСТИКА ТРАЕКТОРИИ", "highlight")
        self._log(f"📌 Количество точек: {stats['total_points']}", "info")
        self._log(f"📏 Общая длина пути: {stats['total_dist']:.2f} мм", "info")
        self._log(f"   ➜ Рабочий путь: {stats['work_dist']:.2f} мм", "info")
        self._log(f"   ➜ Холостой путь: {stats['rapid_dist']:.2f} мм", "info")
        self._log(f"📐 Максимальный шаг между точками: {stats['max_step']:.3f} мм", "info")
        self._log(f"📉 Минимальная Z: {stats['min_z']:.3f} мм", "info")
        self._log(f"📈 Максимальная Z: {stats['max_z']:.3f} мм", "info")
        self._log(LOG_SEPARATOR, "highlight")

    # ----------------------------------------------------------------
    # Импорт/экспорт настроек (с поддержкой файла по умолчанию)
    # ----------------------------------------------------------------
    def _load_default_settings(self):
        """Загружает настройки из файла по умолчанию (DEFAULT_SETTINGS_FILE)."""
        if os.path.exists(DEFAULT_SETTINGS_FILE):
            try:
                with open(DEFAULT_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                self._apply_settings(settings)
                self._log(f"📂 Загружены настройки по умолчанию из {DEFAULT_SETTINGS_FILE}", "info")
            except Exception as e:
                self._log(f"⚠ Ошибка загрузки настроек по умолчанию: {e}", "warning")
        else:
            self._log("ℹ️ Файл настроек по умолчанию не найден, используются значения по умолчанию", "info")

    def _apply_settings(self, settings):
        """Применяет загруженные настройки к UI-переменным."""
        self.x_min_var.set(settings.get("x_min", DEFAULT_X_MIN))
        self.x_max_var.set(settings.get("x_max", DEFAULT_X_MAX))
        self.y_min_var.set(settings.get("y_min", DEFAULT_Y_MIN))
        self.y_max_var.set(settings.get("y_max", DEFAULT_Y_MAX))
        self.tool_diam_var.set(settings.get("tool_diameter", DEFAULT_TOOL_DIAMETER))
        self.stepover_var.set(settings.get("stepover", DEFAULT_STEPOVER))
        self.z_start_var.set(settings.get("z_start", DEFAULT_Z_START))
        self.z_end_var.set(settings.get("z_end", DEFAULT_Z_END))
        self.z_step_var.set(settings.get("z_step", DEFAULT_Z_STEP))
        self.safe_z_var.set(settings.get("safe_z", DEFAULT_SAFE_Z))
        self.feed_xy_var.set(settings.get("feed_xy", DEFAULT_FEED_XY))
        self.feed_z_var.set(settings.get("feed_z", DEFAULT_FEED_Z))
        self.rapid_feed_var.set(settings.get("rapid_feed", DEFAULT_RAPID_FEED))
        self.tool_num_var.set(settings.get("tool_number", DEFAULT_TOOL_NUMBER))
        self.spindle_var.set(settings.get("spindle_speed", DEFAULT_SPINDLE_SPEED))
        self.passes_var.set(settings.get("passes_per_file", DEFAULT_PASSES_PER_FILE))
        self.milling_type_var.set(settings.get("milling_type", DEFAULT_MILLING_TYPE))
        self.milling_direction_var.set(settings.get("milling_direction", DEFAULT_MILLING_DIRECTION))
        self.contour_direction_var.set(settings.get("contour_direction", DEFAULT_CONTOUR_DIRECTION))
        self.allowance_var.set(settings.get("allowance", DEFAULT_ALLOWANCE))
        self.backtrack_var.set(settings.get("backtrack_enabled", DEFAULT_BACKTRACK_ENABLED))
        self.dir_var.set(settings.get("output_dir", os.path.expanduser("~")))
        self._update_params()

    def _save_settings(self):
        """Сохраняет текущие настройки в файл по умолчанию (без диалога)."""
        settings = self._collect_settings()
        try:
            with open(DEFAULT_SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            self._log(f"💾 Настройки сохранены в {DEFAULT_SETTINGS_FILE}", "success")
        except Exception as e:
            self._log(f"❌ Ошибка сохранения настроек: {e}", "error")

    def _save_settings_as(self):
        """Сохраняет настройки в выбранный пользователем файл."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not filepath:
            return
        settings = self._collect_settings()
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            self._log(f"💾 Настройки сохранены в {os.path.basename(filepath)}", "success")
        except Exception as e:
            self._log(f"❌ Ошибка сохранения: {e}", "error")

    def _load_settings(self):
        """Загружает настройки из выбранного пользователем файла."""
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not filepath:
            return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            self._apply_settings(settings)
            self._log(f"📂 Настройки загружены из {os.path.basename(filepath)}", "success")
        except Exception as e:
            self._log(f"❌ Ошибка загрузки: {e}", "error")

    def _collect_settings(self):
        """Собирает текущие настройки в словарь."""
        return {
            "x_min": self.x_min_var.get(),
            "x_max": self.x_max_var.get(),
            "y_min": self.y_min_var.get(),
            "y_max": self.y_max_var.get(),
            "tool_diameter": self.tool_diam_var.get(),
            "stepover": self.stepover_var.get(),
            "z_start": self.z_start_var.get(),
            "z_end": self.z_end_var.get(),
            "z_step": self.z_step_var.get(),
            "safe_z": self.safe_z_var.get(),
            "feed_xy": self.feed_xy_var.get(),
            "feed_z": self.feed_z_var.get(),
            "rapid_feed": self.rapid_feed_var.get(),
            "tool_number": self.tool_num_var.get(),
            "spindle_speed": self.spindle_var.get(),
            "passes_per_file": self.passes_var.get(),
            "milling_type": self.milling_type_var.get(),
            "milling_direction": self.milling_direction_var.get(),
            "contour_direction": self.contour_direction_var.get(),
            "allowance": self.allowance_var.get(),
            "backtrack_enabled": self.backtrack_var.get(),
            "output_dir": self.dir_var.get(),
        }

    # ----------------------------------------------------------------
    # Редактирование G-кода (вкладка визуализатора)
    # ----------------------------------------------------------------
    def _toggle_edit_mode(self):
        if self.code_text.cget('state') == tk.DISABLED:
            self.code_text.config(state=tk.NORMAL)
            self.btn_apply_edit.config(state=tk.NORMAL)
            self.btn_edit.config(text="🔒 Закрыть редактирование")
            self._log("✏️ Режим редактирования включён", "info")
        else:
            self.code_text.config(state=tk.DISABLED)
            self.btn_apply_edit.config(state=tk.DISABLED)
            self.btn_edit.config(text="✏️ Редактировать")
            self._log("🔒 Режим редактирования выключен", "info")

    def _apply_edit(self):
        if self.code_text.cget('state') == tk.DISABLED:
            return
        content = self.code_text.get("1.0", tk.END)
        lines = []
        for line in content.splitlines():
            if line.strip() and '│' in line:
                parts = line.split('│', 1)
                if len(parts) == 2:
                    lines.append(parts[1].strip())
            else:
                lines.append(line.strip())
        lines = [ln for ln in lines if ln]
        if not lines:
            self._log("❌ Нет строк для парсинга", "error")
            return
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.nc', delete=False, encoding='utf-8') as f:
                f.write('\n'.join(lines))
                tmp_path = f.name
            points, _ = self.parser.parse_file(tmp_path)
            os.unlink(tmp_path)
            if not points:
                self._log("❌ После редактирования не удалось получить точки", "error")
                return
            self.current_points = points
            self.code_lines = lines
            self.points_x = [p.x for p in points]
            self.points_y = [p.y for p in points]
            self.points_z = [p.z for p in points]
            self.points_rapid = [p.rapid for p in points]
            self.anim_frame = 0
            self.anim_running = False
            self.anim_paused = False
            self._update_step_buttons()
            self._update_plot()
            self._log(f"✅ Траектория обновлена, точек: {len(points)}", "success")
            self._display_code()
            self._show_statistics()
        except Exception as e:
            self._log(f"❌ Ошибка применения изменений: {e}", "error")

    # ----------------------------------------------------------------
    # Визуализация (статический график)
    # ----------------------------------------------------------------
    def _update_plot(self):
        if not MATPLOTLIB_AVAILABLE or not self.current_points:
            return
        if self._is_drawing:
            return

        self._is_drawing = True
        try:
            self.fig.clear()
            proj = self.projection_var.get()

            total_points = len(self.points_x)
            step = 1
            if proj == "3D" and total_points > 5000:
                step = max(1, total_points // 5000)

            indices = list(range(0, total_points, step))
            if indices and indices[-1] != total_points - 1:
                indices.append(total_points - 1)

            xs = [self.points_x[i] for i in indices]
            ys = [self.points_y[i] for i in indices]
            zs = [self.points_z[i] for i in indices]
            rapids = [self.points_rapid[i] for i in indices]

            if proj == "3D":
                self.ax = self.fig.add_subplot(111, projection='3d')
                self.ax.plot(xs, ys, zs, color='lightgray', linewidth=0.5, alpha=0.7)
                rapid_idx = [i for i, r in enumerate(rapids) if r]
                work_idx = [i for i, r in enumerate(rapids) if not r]
                if rapid_idx:
                    self.ax.plot([xs[i] for i in rapid_idx],
                                 [ys[i] for i in rapid_idx],
                                 [zs[i] for i in rapid_idx],
                                 'r.', markersize=1.5, alpha=SCATTER_ALPHA_RAPID, label='G0')
                if work_idx:
                    self.ax.plot([xs[i] for i in work_idx],
                                 [ys[i] for i in work_idx],
                                 [zs[i] for i in work_idx],
                                 'b.', markersize=1.5, alpha=SCATTER_ALPHA_WORKING, label='G1')
                self.ax.set_xlabel('X')
                self.ax.set_ylabel('Y')
                self.ax.set_zlabel('Z')
                self.ax.legend(loc="upper right", fontsize=8)
                self.ax.set_box_aspect([1,1,0.5])
                self.ax.autoscale()

                for axis in [self.ax.xaxis, self.ax.yaxis, self.ax.zaxis]:
                    axis.set_major_locator(mticker.MaxNLocator(6))
                    axis.set_major_formatter(mticker.ScalarFormatter(useOffset=False))
                    axis.get_major_formatter().set_scientific(False)
                    axis.get_major_formatter().set_useOffset(False)

            else:
                self.ax = self.fig.add_subplot(111)
                if proj == "XY":
                    self.ax.plot(xs, ys, color='lightgray', linewidth=0.5, alpha=0.7)
                    rapid_data = ([xs[i] for i, r in enumerate(rapids) if r],
                                  [ys[i] for i, r in enumerate(rapids) if r])
                    work_data = ([xs[i] for i, r in enumerate(rapids) if not r],
                                 [ys[i] for i, r in enumerate(rapids) if not r])
                    self.ax.set_xlabel('X')
                    self.ax.set_ylabel('Y')
                    self.ax.set_aspect('equal')
                elif proj == "XZ":
                    self.ax.plot(xs, zs, color='lightgray', linewidth=0.5, alpha=0.7)
                    rapid_data = ([xs[i] for i, r in enumerate(rapids) if r],
                                  [zs[i] for i, r in enumerate(rapids) if r])
                    work_data = ([xs[i] for i, r in enumerate(rapids) if not r],
                                 [zs[i] for i, r in enumerate(rapids) if not r])
                    self.ax.set_xlabel('X')
                    self.ax.set_ylabel('Z')
                elif proj == "YZ":
                    self.ax.plot(ys, zs, color='lightgray', linewidth=0.5, alpha=0.7)
                    rapid_data = ([ys[i] for i, r in enumerate(rapids) if r],
                                  [zs[i] for i, r in enumerate(rapids) if r])
                    work_data = ([ys[i] for i, r in enumerate(rapids) if not r],
                                 [zs[i] for i, r in enumerate(rapids) if not r])
                    self.ax.set_xlabel('Y')
                    self.ax.set_ylabel('Z')
                else:
                    return

                if rapid_data[0]:
                    self.ax.plot(rapid_data[0], rapid_data[1],
                                 'r.', markersize=1.5, alpha=SCATTER_ALPHA_RAPID, label='G0')
                if work_data[0]:
                    self.ax.plot(work_data[0], work_data[1],
                                 'b.', markersize=1.5, alpha=SCATTER_ALPHA_WORKING, label='G1')

                all_x = xs if proj in ('XY','XZ') else ys
                all_y = zs if proj in ('XZ','YZ') else ys
                if all_x and all_y:
                    x_min, x_max = min(all_x), max(all_x)
                    y_min, y_max = min(all_y), max(all_y)
                    margin_x = (x_max - x_min) * 0.05 if x_max != x_min else 1
                    margin_y = (y_max - y_min) * 0.05 if y_max != y_min else 1
                    self.ax.set_xlim(x_min - margin_x, x_max + margin_x)
                    self.ax.set_ylim(y_min - margin_y, y_max + margin_y)

                self.ax.legend(loc="upper right", fontsize=8)
                self.ax.grid(True, alpha=GRID_ALPHA)

                self.ax.xaxis.set_major_locator(mticker.MaxNLocator(6))
                self.ax.xaxis.set_major_formatter(mticker.ScalarFormatter(useOffset=False))
                self.ax.xaxis.get_major_formatter().set_scientific(False)
                self.ax.xaxis.get_major_formatter().set_useOffset(False)

                self.ax.yaxis.set_major_locator(mticker.MaxNLocator(6))
                self.ax.yaxis.set_major_formatter(mticker.ScalarFormatter(useOffset=False))
                self.ax.yaxis.get_major_formatter().set_scientific(False)
                self.ax.yaxis.get_major_formatter().set_useOffset(False)

            self.canvas.draw_idle()
        except Exception as e:
            self._log(f"❌ Ошибка обновления графика: {e}", "error")
        finally:
            self._is_drawing = False

    # ----------------------------------------------------------------
    # Управление логом
    # ----------------------------------------------------------------
    def _copy_log_selection(self):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.log_text.get(tk.SEL_FIRST, tk.SEL_END))
            self._log("✅ Выделенный текст скопирован", "success")
        except tk.TclError:
            self._log(MSG_NOTHING_SELECTED, "warning")

    def _copy_all_log(self):
        content = self.log_text.get("1.0", tk.END).strip()
        if content:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self._log("✅ Весь лог скопирован", "success")
        else:
            self._log(MSG_LOG_EMPTY, "warning")

    def _clear_log(self):
        self.log_text.delete("1.0", tk.END)
        self._log("🗑️ Лог очищен", "info")

    def _save_log_manual(self):
        content = self.log_text.get("1.0", tk.END).strip()
        if not content:
            self._log(MSG_LOG_EMPTY, "warning")
            return
        now = datetime.now()
        date_str = now.strftime(LOG_DATE_FORMAT)
        try:
            milling_type = self.milling_type_var.get()
            type_name = MILLING_TYPE_FILE_NAMES.get(milling_type, "unknown")
        except Exception:
            type_name = "log"
        default_name = f"{LOG_FILE_PREFIX}_{date_str}_{type_name}.txt"
        fp = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=default_name,
                                          filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if fp:
            try:
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(content)
                self._log(f"💾 Лог сохранён: {os.path.basename(fp)}", "success")
            except Exception as e:
                self._log(f"❌ Ошибка сохранения: {e}", "error")