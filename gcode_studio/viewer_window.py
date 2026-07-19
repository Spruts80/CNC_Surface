"""
Окно просмотра G-кода с подсветкой синтаксиса и возможностью редактирования.
"""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from .gcode_highlighter import GCodeHighlighter


class GCodeViewerWindow:
    def __init__(self, parent, filepath: str, theme: str = 'dark'):
        self.parent = parent
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.theme = theme
        self._search_pos = "1.0"
        self.is_editable = False

        # Проверка существования файла
        if not os.path.exists(filepath):
            messagebox.showerror("Ошибка", f"Файл не найден:\n{filepath}")
            return

        # Чтение файла с обработкой ошибок
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.content = f.read()
        except UnicodeDecodeError:
            # Пробуем другую кодировку
            try:
                with open(filepath, 'r', encoding='cp1251') as f:
                    self.content = f.read()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось прочитать файл (кодировка):\n{e}")
                return
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть файл:\n{e}")
            return

        # Если файл пустой – показываем предупреждение
        if not self.content.strip():
            messagebox.showwarning("Внимание", "Файл пуст или содержит только пробелы.")
            # Всё равно создаём окно, но с пустым содержимым

        # Создаём окно
        self.window = tk.Toplevel(parent)
        self.window.title(f"Просмотр: {self.filename}")
        self.window.geometry("1200x800")
        self._setup_ui()
        self._apply_highlighting()

    def _setup_ui(self):
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

        # Текстовый виджет
        text_frame = ttk.Frame(self.window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        y_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Цвета в зависимости от темы
        if self.theme == 'dark':
            bg_color = '#1E1E1E'
            fg_color = '#D4D4D4'
        else:
            bg_color = '#FFFFFF'
            fg_color = '#000000'

        self.text_widget = tk.Text(
            text_frame,
            wrap=tk.NONE,
            font=('Consolas', 11),
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
            bg=bg_color,
            fg=fg_color,
            insertbackground=fg_color,
            state=tk.NORMAL  # Сначала делаем доступным для вставки
        )
        self.text_widget.pack(fill=tk.BOTH, expand=True)
        y_scroll.config(command=self.text_widget.yview)
        x_scroll.config(command=self.text_widget.xview)

        # Вставляем содержимое
        self.text_widget.insert("1.0", self.content)
        # Принудительно обновляем виджет
        self.text_widget.update_idletasks()

        # Блокируем для чтения (если не в режиме редактирования)
        self.text_widget.config(state=tk.DISABLED)

        self.text_widget.tag_configure("found", background="yellow", foreground="black")

        # Инициализация подсветки
        self.highlighter = GCodeHighlighter(self.text_widget, theme=self.theme)

        # Кнопки действий
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        self.btn_edit = ttk.Button(btn_frame, text="✏️ Редактировать", command=self._toggle_edit_mode)
        self.btn_edit.pack(side=tk.LEFT, padx=5)

        self.btn_save = ttk.Button(btn_frame, text="💾 Сохранить", command=self._save_file, state=tk.DISABLED)
        self.btn_save.pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="💾 Сохранить как...", command=self._save_as).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="📋 Копировать всё", command=self._copy_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=" Копировать выделенное", command=self._copy_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="❌ Закрыть", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        # Для отладки – если содержимое пустое, покажем предупреждение
        if not self.content.strip():
            # Можно добавить информационную надпись
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.insert("1.0", "Файл пуст или не содержит текста.")
            self.text_widget.config(state=tk.DISABLED)

    def _toggle_edit_mode(self):
        if self.is_editable:
            self.text_widget.config(state=tk.DISABLED)
            self.btn_edit.config(text="✏️ Редактировать")
            self.btn_save.config(state=tk.DISABLED)
            self.is_editable = False
            self.window.title(f"Просмотр: {self.filename}")
            self._apply_highlighting()
        else:
            self.text_widget.config(state=tk.NORMAL)
            self.btn_edit.config(text="🔒 Закрыть редактирование")
            self.btn_save.config(state=tk.NORMAL)
            self.is_editable = True
            self.window.title(f"✏️ Просмотр: {self.filename} [РЕДАКТИРУЕТСЯ]")
            for tag_name in self.highlighter.COLORS.keys():
                self.text_widget.tag_remove(tag_name, "1.0", tk.END)

    def _save_file(self):
        if not self.is_editable:
            return
        if not messagebox.askyesno(
            "Подтверждение сохранения",
            f"Вы действительно хотите перезаписать файл\n{self.filepath}\nс текущими изменениями?"
        ):
            return
        content = self.text_widget.get("1.0", tk.END).rstrip('\n')
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            messagebox.showinfo("Сохранено", f"Файл {self.filename} успешно сохранён.")
            self.window.title(f"Просмотр: {self.filename}")
            self._toggle_edit_mode()
        except Exception as e:
            messagebox.showerror("Ошибка сохранения", f"Не удалось сохранить файл:\n{e}")

    def _apply_highlighting(self):
        current_state = self.text_widget.cget('state')
        if current_state == tk.DISABLED:
            self.text_widget.config(state=tk.NORMAL)
        self.highlighter.highlight()
        if current_state == tk.DISABLED:
            self.text_widget.config(state=tk.DISABLED)

    def _find_next(self):
        search_text = self.search_var.get()
        if not search_text:
            messagebox.showinfo("Поиск", "Введите текст для поиска")
            return
        current_state = self.text_widget.cget('state')
        if current_state == tk.DISABLED:
            self.text_widget.config(state=tk.NORMAL)
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
                self._search_pos = "1.0"
        if current_state == tk.DISABLED:
            self.text_widget.config(state=tk.DISABLED)

    def _reset_search(self):
        self.search_var.set("")
        self._search_pos = "1.0"
        current_state = self.text_widget.cget('state')
        if current_state == tk.DISABLED:
            self.text_widget.config(state=tk.NORMAL)
        self.text_widget.tag_remove("found", "1.0", tk.END)
        if current_state == tk.DISABLED:
            self.text_widget.config(state=tk.DISABLED)
        self.search_status.config(text="Найдено: 0", foreground="gray")

    def _save_as(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".nc",
            filetypes=[("G-code", "*.nc"), ("Text", "*.txt")]
        )
        if filepath:
            current_state = self.text_widget.cget('state')
            if current_state == tk.DISABLED:
                self.text_widget.config(state=tk.NORMAL)
            content = self.text_widget.get("1.0", tk.END).rstrip('\n')
            if current_state == tk.DISABLED:
                self.text_widget.config(state=tk.DISABLED)
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("Сохранено", f"Файл сохранён как {os.path.basename(filepath)}")
            except Exception as e:
                messagebox.showerror("Ошибка сохранения", str(e))

    def _copy_all(self):
        current_state = self.text_widget.cget('state')
        if current_state == tk.DISABLED:
            self.text_widget.config(state=tk.NORMAL)
        content = self.text_widget.get("1.0", tk.END).rstrip('\n')
        if current_state == tk.DISABLED:
            self.text_widget.config(state=tk.DISABLED)
        self.window.clipboard_clear()
        self.window.clipboard_append(content)

    def _copy_selected(self):
        try:
            current_state = self.text_widget.cget('state')
            if current_state == tk.DISABLED:
                self.text_widget.config(state=tk.NORMAL)
            selected = self.text_widget.get(tk.SEL_FIRST, tk.SEL_LAST)
            if current_state == tk.DISABLED:
                self.text_widget.config(state=tk.DISABLED)
            self.window.clipboard_clear()
            self.window.clipboard_append(selected)
        except tk.TclError:
            pass