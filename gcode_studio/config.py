"""
Конфигурация G-Code Studio.

Содержит все константы, значения по умолчанию и настройки интерфейса.
Централизованное хранение параметров упрощает поддержку и модификацию.
"""


# ============================================================
# Параметры обработки по умолчанию
# ============================================================

DEFAULT_X_MIN = 0.0
DEFAULT_X_MAX = 280.0
DEFAULT_Y_MIN = 0.0
DEFAULT_Y_MAX = 380.0
DEFAULT_TOOL_DIAMETER = 6.0
DEFAULT_STEPOVER = 3.0
DEFAULT_Z_START = 0.0
DEFAULT_Z_END = -0.6
DEFAULT_Z_STEP = 0.05
DEFAULT_SAFE_Z = 25.0
DEFAULT_FEED_XY = 800
DEFAULT_FEED_Z = 80
DEFAULT_TOOL_NUMBER = 2
DEFAULT_SPINDLE_SPEED = 4000
DEFAULT_PASSES_PER_FILE = 5
DEFAULT_ALLOWANCE = 0.0

# Тип обработки по умолчанию
DEFAULT_MILLING_TYPE = "zigzag_x"
DEFAULT_MILLING_DIRECTION = "climb"
DEFAULT_CONTOUR_DIRECTION = "outside_in"


# ============================================================
# Словари типов обработки (значение → отображаемое имя)
# ============================================================

MILLING_TYPES = {
    "zigzag_x": "Зигзаг по X",
    "zigzag_y": "Зигзаг по Y",
    "center_spiral": "От центра змейкой",
    "contour": "Контурное",
}

MILLING_DIRECTIONS = {
    "climb": "Попутное (Чистовая обработка)",
    "conventional": "Встречное (Черновая обработка)",
}

CONTOUR_DIRECTIONS = {
    "outside_in": "От края к центру",
    "inside_out": "От центра к краю",
}

# Маппинг для имён файлов логов
MILLING_TYPE_FILE_NAMES = {
    "zigzag_x": "zigzag_x",
    "zigzag_y": "zigzag_y",
    "center_spiral": "center_spiral",
    "contour": "contour",
}


# ============================================================
# Настройки анимации
# ============================================================

ANIMATION_SPEEDS = [1, 2, 5, 10, 20, 50]
DEFAULT_ANIMATION_SPEED = 2
ANIMATION_INTERVAL_MS = 30          # Интервал между кадрами (мс)
ANIMATION_SKIP_DRAWING_DELAY = 30   # Задержка при пропуске кадра (мс)
QUEUE_POLL_INTERVAL_MS = 100        # Интервал опроса очереди задач (мс)
RESIZE_DEBOUNCE_MS = 100            # Задержка перерисовки при resize (мс)
TOOL_PATH_SAMPLE_DIVISOR = 500      # Делитель для сэмплирования "следа фрезы"


# ============================================================
# Настройки визуализации (matplotlib)
# ============================================================

FIGURE_WIDTH = 8
FIGURE_HEIGHT = 6
FIGURE_DPI = 100
VIEW_MARGIN = 20                    # Отступ от границ поля (мм)

# Цвета траекторий
COLOR_RAPID = 'red'                 # Холостые перемещения (G0)
COLOR_WORKING = 'blue'              # Рабочие перемещения (G1)
COLOR_TOOL_PATH = 'green'           # След фрезы (обработанная область)
COLOR_TOOL_MARKER = 'red'           # Маркер текущей позиции фрезы
COLOR_TRAJECTORY_BG = 'lightgray'   # Фоновая линия полной траектории

# Точки scatter
SCATTER_SIZE = 2
SCATTER_ALPHA_RAPID = 0.3
SCATTER_ALPHA_WORKING = 0.6

# Линии
LINE_WIDTH_TRAJECTORY = 0.3
LINE_WIDTH_PASSED = 1.0
LINE_ALPHA_TRAJECTORY = 0.5
LINE_ALPHA_PASSED = 0.7

# След фрезы
TOOL_PATH_ALPHA = 0.2
TOOL_MARKER_SIZE = 14
TOOL_OUTLINE_WIDTH = 1.5

# Сетка
GRID_ALPHA = 0.3


# ============================================================
# Цвета текстового редактора G-кода
# ============================================================

CODE_BG_COLOR = '#1e1e1e'           # Фон редактора (тёмная тема)
CODE_FG_COLOR = '#d4d4d4'           # Цвет текста
CODE_FONT = ('Consolas', 10)

# Подсветка текущей строки
CURRENT_LINE_BG = '#264f78'
CURRENT_LINE_FG = 'white'

# Подсветка при наведении
HOVER_LINE_BG = '#3a3a3a'
HOVER_LINE_FG = 'white'

# Подсветка поиска
SEARCH_FOUND_BG = 'yellow'
SEARCH_FOUND_FG = 'black'


# ============================================================
# Цвета лога
# ============================================================

LOG_FONT = ('Consolas', 10)
LOG_HEIGHT = 10

LOG_COLOR_INFO = "black"
LOG_COLOR_SUCCESS = "green"
LOG_COLOR_ERROR = "red"
LOG_COLOR_WARNING = "orange"
LOG_COLOR_HIGHLIGHT = "blue"


# ============================================================
# Настройки главного окна
# ============================================================

WINDOW_TITLE = "G-Code Studio - Финальная версия"
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
WINDOW_MIN_WIDTH = 1100
WINDOW_MIN_HEIGHT = 700

# Вкладки
TAB_GENERATOR_TITLE = "⚙ Генератор"
TAB_VIEWER_TITLE = "👁 Визуализатор"

# Проекция по умолчанию
DEFAULT_PROJECTION = "XY"
PROJECTIONS = ["XY", "XZ", "YZ"]

# Кнопки генератора
BTN_VALIDATE_TEXT = "🔍 Проверить параметры"
BTN_VALIDATE_WIDTH = 25
BTN_GENERATE_TEXT = "🚀 Генерировать"
BTN_GENERATE_BUSY_TEXT = "⏳ Генерация..."
BTN_GENERATE_WIDTH = 25

# Кнопки анимации
BTN_PLAY_TEXT = "▶ Play"
BTN_PAUSE_TEXT = "⏸ Пауза"
BTN_STOP_TEXT = "⏹ Стоп"
BTN_STEP_BACK_TEXT = "◀ Назад"
BTN_STEP_FWD_TEXT = "Вперёд ▶"
BTN_WIDTH = 8

# Статусы анимации
STATUS_WAITING = "Статус: Ожидание"
STATUS_PLAYING = "Статус: ▶ Воспроизведение"
STATUS_PAUSED = "Статус: ⏸ Пауза (используйте ◀ ▶ для пошагового)"
STATUS_STOPPED = "Статус: ⏹ Остановлено"
STATUS_FINISHED = "Статус: ✅ Завершено"

# Координаты по умолчанию
COORD_DEFAULT_TEXT = "📍 Текущие координаты: X: 0.000  Y: 0.000  Z: 0.000"
FILE_NOT_LOADED_TEXT = "Файл не загружен"
FILE_LOADING_TEXT = "⏳ Загрузка..."
FILE_EMPTY_TEXT = "Файл пуст"


# ============================================================
# Форматирование G-кода
# ============================================================

GCODE_LINE_NUM_STEP = 5             # Шаг нумерации строк
GCODE_LINE_NUM_START = 40           # Начальный номер строки (после заголовка)
GCODE_PROGRAM_NUM_START = 1000      # Начальный номер программы (Oxxxx)
GCODE_EPSILON = 0.0001              # Допуск сравнения координат
GCODE_CENTER_EPSILON = 0.001        # Допуск для проверки центра
GCODE_Z_PRECISION = 3               # Точность Z (знаков после запятой)
GCODE_COORD_PRECISION = 3           # Точность координат (знаков после запятой)


# ============================================================
# Форматирование лога
# ============================================================

LOG_SEPARATOR = "=" * 60
LOG_READY_MSG = "🎯 G-Code Studio готов к работе"
LOG_HINT_MSG = "📋 Заполните параметры и нажмите 'Проверить параметры' или 'Генерировать'"
LOG_SEPARATOR_CHAR = "│"            # Разделитель в отображении кода
LOG_LINE_FORMAT = "{i:4d} │ {line}" # Формат строки кода в редакторе


# ============================================================
# Форматирование имён файлов
# ============================================================

FILE_PREFIX = "stol"                            # Префикс файлов G-кода
FILE_EXTENSION = ".nc"                          # Расширение файлов
LOG_FILE_PREFIX = "gcode_log"                   # Префикс файлов логов
LOG_DATE_FORMAT = "%d%m%Y_%H%M%S"              # Формат даты в имени лога
LOG_DATE_FORMAT_ALT = "%Y%m%d_%H%M%S"          # Альтернативный формат даты
HEADER_DATE_FORMAT = "%d.%m.%Y %H:%M:%S"       # Формат даты в заголовке G-кода


# ============================================================
# Заголовок G-кода
# ============================================================

HEADER_SEPARATOR = "; ============================================"
HEADER_TITLE = "; G-Code Studio - Параметры обработки"
HEADER_LABEL_DATE = "; Дата: "
HEADER_LABEL_FILE = "; Файл "
HEADER_LABEL_FILE_OF = " из "
HEADER_LABEL_TYPE = "; Тип обработки: "
HEADER_LABEL_DIRECTION = "; Направление фрезерования: "
HEADER_LABEL_CONTOUR_DIR = "; Направление контура: "
HEADER_LABEL_FIELD = "; Поле обработки:"
HEADER_LABEL_X_RANGE = ";   X: "
HEADER_LABEL_Y_RANGE = ";   Y: "
HEADER_LABEL_MM = " мм"
HEADER_LABEL_TOOL = "; Инструмент:"
HEADER_LABEL_TOOL_NUM = ";   Номер: T"
HEADER_LABEL_DIAMETER = ";   Диаметр: "
HEADER_LABEL_STEPOVER = ";   Шаг (stepover): "
HEADER_LABEL_OVERLAP = ";   Перекрытие: "
HEADER_LABEL_PERCENT = "%"
HEADER_LABEL_DEPTH = "; Глубина обработки:"
HEADER_LABEL_Z_START = ";   Z старт: "
HEADER_LABEL_Z_END = ";   Z конец: "
HEADER_LABEL_Z_STEP = ";   Шаг по Z: "
HEADER_LABEL_SAFE_Z = ";   Безопасная Z: "
HEADER_LABEL_PASSES = ";   Проходов в файле: "
HEADER_LABEL_MODES = "; Режимы:"
HEADER_LABEL_FEED_XY = ";   Подача XY: "
HEADER_LABEL_FEED_Z = ";   Подача Z: "
HEADER_LABEL_SPEED = ";   Обороты шпинделя: "
HEADER_LABEL_RPM = " об/мин"
HEADER_LABEL_MM_MIN = " мм/мин"
HEADER_LABEL_Z_LEVELS = "; Уровни Z в этом файле:"
HEADER_LABEL_Z_VALUE = ";   Z = "


# ============================================================
# G-код: стандартные команды
# ============================================================

GCODE_FILE_START = "%"
GCODE_FILE_END = "%"
GCODE_PROGRAM_END = "M30"

# Строки инициализации
GCODE_INIT_LINES = [
    "N5 G0 G40 G49 G80 G21",
    "N10 G0 G53 Z0",
    "N15 G0 G53 X0 Y0",
]

# Команды завершения
GCODE_TOOL_CHANGE_FMT = "N20 T{tool} M6"
GCODE_SPINDLE_ON_FMT = "N30 S{speed} M4"
GCODE_COOLANT_ON = "N35 M8"
GCODE_SAFE_Z_FMT = "N{ln} G0 Z{z}"
GCODE_RETRACT_FMT = "N{ln} G0 G53 Z35 M9"
GCODE_HOME_FMT = "N{ln} G0 G53 X0 Y0 M5"


# ============================================================
# Сообщения
# ============================================================

MSG_NO_FILE_TITLE = "Внимание"
MSG_NO_FILE_TEXT = "Сначала загрузите G-код файл!"
MSG_SEARCH_TITLE = "Поиск"
MSG_SEARCH_EMPTY = "Введите текст для поиска"
MSG_ERROR_TITLE = "Ошибка"
MSG_SELECT_FOLDER = "Выберите папку"
MSG_FOLDER_NOT_SET = "Папка не указана!"
MSG_GENERATION_ERROR = "❌ Ошибка генерации"
MSG_LOG_EMPTY = "⚠ Лог пуст"
MSG_NOTHING_SELECTED = "⚠ Ничего не выделено"