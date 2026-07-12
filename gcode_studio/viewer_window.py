"""
Окно просмотра G-кода.

Предоставляет отдельное окно для просмотра, поиска,
копирования и сохранения содержимого файлов G-кода.
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .config import (
    CODE_FONT, SEARCH_FOUND_BG, SEARCH_FOUND_FG,
    MSG_SEARCH_TITLE, MSG_SEARCH_EMPTY,
    LOG_SEPARATOR_CHAR,
)


class GCodeViewerWindow:
    """Модальное окно просмотра файла G-кода.

    Содержит панель поиска, текстовый редактор с прокруткой
    и кнопки управления (сохранить, копировать, закрыть).
    """

    def __init__(self, parent, filepath: str):
        """Инициализация окна просмотра.

        Args:
            parent: Родительский виджет Tkinter
            filepath: Путь к файлу G-кода для отображения
        """
        self.parent = parent
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self._last_search = ""
        self._search_pos = "1.0"

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.content = f.read()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
            return

        self.window = tk.Toplevel(parent)
        self.window.title(f"Просмотр: {self.filename}")
        self.window.geometry("1000x750")
        self._setup_ui()

    def _setup_ui(self):
        """Создание интерфейса окна просмотра."""
        # Панель поиска
        search_frame = ttk.LabelFrame(self.window, text="🔍 Поиск", padding=5)
        search_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        search_row = ttk.Frame(search_frame)
        search_row.pack(fill=tk.X)

        ttk.Label(search_row, text="Найти:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_row, textvariable=self.search_var, width=40)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind('<Return>', lambda e: self._find_next())

        ttk.Button(search_row, text="▶ Найти", command=self._find_next, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_row, text="🔄 Сброс", command=self._reset_search, width=10).pack(side=tk.LEFT, padx=2)

        self.search_status = ttk.Label(search_row, text="Найдено: 0", foreground="gray")
        self.search_status.pack(side=tk.RIGHT, padx=10)

        # Текстовый виджет с прокруткой
        text_frame = ttk.Frame(self.window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        y_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.text_widget = tk.Text(
            text_frame, wrap=tk.NONE, font=CODE_FONT,
            yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set
        )
        self.text_widget.pack(fill=tk.BOTH, expand=True)
        y_scroll.config(command=self.text_widget.yview)
        x_scroll.config(command=self.text_widget.xview)
        self.text_widget.insert(tk.END, self.content)
        self.text_widget.tag_configure("found", background=SEARCH_FOUND_BG, foreground=SEARCH_FOUND_FG)

        # Кнопки действий
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text="💾 Сохранить как...", command=self._save_as).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="📋 Копировать всё", command=self._copy_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="📋 Копировать выделенное", command=self._copy_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="❌ Закрыть", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

    def _find_next(self):
        """Поиск следующего вхождения текста.

        Ищет от текущей позиции к концу файла,
        при достижении конца — начинает с начала.
        """
        search_text = self.search_var.get()
        if not search_text:
            messagebox.showinfo(MSG_SEARCH_TITLE, MSG_SEARCH_EMPTY)
            return

        # Ищем с текущей позиции
        pos = self.text_widget.search(search_text, self._search_pos, stopindex=tk.END)
        if pos:
            end_pos = self.text_widget.index(f"{pos}+{len(search_text)}c")
            self.text_widget.tag_remove("found", "1.0", tk.END)
            self.text_widget.tag_add("found", pos, end_pos)
            self.text_widget.see(pos)
            self.text_widget.mark_set(tk.INSERT, end_pos)
            self._search_pos = end_pos
            self.search_status.config(text=f"Найдено в позиции {pos}", foreground="green")
        else:
            # Если не найдено — ищем с начала
            pos = self.text_widget.search(search_text, "1.0", stopindex=tk.END)
            if pos:
                end_pos = self.text_widget.index(f"{pos}+{len(search_text)}c")
                self.text_widget.tag_remove("found", "1.0", tk.END)
                self.text_widget.tag_add("found", pos, end_pos)
                self.text_widget.see(pos)
                self.text_widget.mark_set(tk.INSERT, end_pos)
                self._search_pos = end_pos
                self.search_status.config(text=f"Найдено в позиции {pos} (с начала)", foreground="green")
            else:
                self.search_status.config(text="Не найдено", foreground="red")

    def _reset_search(self):
        """Сброс поиска и очистка подсветки."""
        self.search_var.set("")
        self._search_pos = "1.0"
        self.text_widget.tag_remove("found", "1.0", tk.END)
        self.search_status.config(text="Найдено: 0", foreground="gray")

    def _save_as(self):
        """Сохранение содержимого в новый файл."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".nc",
            filetypes=[("G-code", "*.nc"), ("Text", "*.txt")]
        )
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(self.text_widget.get("1.0", tk.END).rstrip('\n'))

    def _copy_all(self):
        """Копирование всего содержимого в буфер обмена."""
        self.window.clipboard_clear()
        self.window.clipboard_append(self.text_widget.get("1.0", tk.END).rstrip('\n'))

    def _copy_selected(self):
        """Копирование выделенного текста в буфер обмена."""
        try:
            selected = self.text_widget.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.window.clipboard_clear()
            self.window.clipboard_append(selected)
        except tk.TclError:
            pass