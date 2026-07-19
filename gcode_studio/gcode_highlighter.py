"""
Подсветка синтаксиса G-кода (оптимизированная версия).
"""
import re
import tkinter as tk


class GCodeHighlighter:
    COLORS = {
        'G_command': '#569CD6',
        'M_command': '#C586C0',
        'coordinate': '#9CDCFE',
        'feed': '#CE9178',
        'spindle': '#B5CEA8',
        'line_number': '#808080',
        'comment': '#6A9955',
        'percent': '#FFD700',
        'default': '#D4D4D4',
    }

    PATTERNS = [
        (r'^\s*%.*$', 'percent'),
        (r';.*$', 'comment'),
        (r'\bN\d+\b', 'line_number'),
        (r'\bG\d+\.?\d*\b', 'G_command'),
        (r'\bM\d+\.?\d*\b', 'M_command'),
        (r'\b[XYZABC][-+]?\d*\.?\d+\b', 'coordinate'),
        (r'\bF\d+\.?\d*\b', 'feed'),
        (r'\bS\d+\.?\d*\b', 'spindle'),
    ]

    def __init__(self, text_widget: tk.Text, theme: str = 'dark'):
        self.text_widget = text_widget
        self.theme = theme
        self.compiled_patterns = [(re.compile(pattern), tag_name) for pattern, tag_name in self.PATTERNS]
        self._setup_tags()

    def _setup_tags(self):
        for tag_name, color in self.COLORS.items():
            self.text_widget.tag_configure(tag_name, foreground=color)

    def highlight(self, start: str = "1.0", end: str = None):
        if end is None:
            end = self.text_widget.index(tk.END)
        for tag_name in self.COLORS.keys():
            self.text_widget.tag_remove(tag_name, "1.0", tk.END)
        start_line = int(start.split('.')[0])
        end_line = int(end.split('.')[0])
        for line_num in range(start_line, end_line + 1):
            line_start = f"{line_num}.0"
            line_end = f"{line_num}.end"
            line_text = self.text_widget.get(line_start, line_end)
            if not line_text:
                continue
            for pattern, tag_name in self.compiled_patterns:
                for match in pattern.finditer(line_text):
                    start_col = match.start()
                    end_col = match.end()
                    self.text_widget.tag_add(tag_name, f"{line_num}.{start_col}", f"{line_num}.{end_col}")
            if line_num % 100 == 0:
                self.text_widget.update_idletasks()


class GCodeViewerWithHighlight:
    def __init__(self, parent, filepath: str, theme: str = 'dark'):
        import os
        from tkinter import filedialog, messagebox

        self.parent = parent
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.theme = theme
        self._search_pos = "1.0"

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.content = f.read()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
            return

        self.window = tk.Toplevel(parent)
        self.window.title(f"Просмотр: {self.filename}")
        self.window.geometry("1200x800")
        self._setup_ui()
        self._apply_highlighting()

    def _setup_ui(self):
        from tkinter import ttk

        control_frame = ttk.Frame(self.window)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(control_frame, text="Тема:").pack(side=tk.LEFT, padx=5)
        self.theme_var = tk.StringVar(value=self.theme)
        theme_combo = ttk.Combobox(control_frame, textvariable=self.theme_var,
                                   values=['dark', 'light'], state="readonly", width=10)
        theme_combo.pack(side=tk.LEFT, padx=5)
        theme_combo.bind('<<ComboboxSelected>>', lambda e: self._change_theme())

        ttk.Label(control_frame, text="Найти:").pack(side=tk.LEFT, padx=(20, 5))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(control_frame, textvariable=self.search_var, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind('<Return>', lambda e: self._find_next())

        ttk.Button(control_frame, text="▶ Найти", command=self._find_next, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(control_frame, text=" Сброс", command=self._reset_search, width=10).pack(side=tk.LEFT, padx=2)

        self.search_status = ttk.Label(control_frame, text="Найдено: 0", foreground="gray")
        self.search_status.pack(side=tk.RIGHT, padx=10)

        text_frame = ttk.Frame(self.window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        y_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        bg_color = '#1E1E1E' if self.theme == 'dark' else '#FFFFFF'
        fg_color = '#D4D4D4' if self.theme == 'dark' else '#000000'

        self.text_widget = tk.Text(text_frame, wrap=tk.NONE, font=('Consolas', 11),
                                   yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set,
                                   bg=bg_color, fg=fg_color, insertbackground=fg_color)
        self.text_widget.pack(fill=tk.BOTH, expand=True)
        y_scroll.config(command=self.text_widget.yview)
        x_scroll.config(command=self.text_widget.xview)
        self.text_widget.insert(tk.END, self.content)
        self.text_widget.config(state=tk.DISABLED)

        self.highlighter = GCodeHighlighter(self.text_widget, self.theme)

        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="💾 Сохранить как...", command=self._save_as).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="📋 Копировать всё", command=self._copy_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=" Копировать выделенное", command=self._copy_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="❌ Закрыть", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

    def _apply_highlighting(self):
        self.text_widget.config(state=tk.NORMAL)
        self.highlighter.highlight()
        self.text_widget.config(state=tk.DISABLED)

    def _change_theme(self):
        self.theme = self.theme_var.get()
        self.highlighter = GCodeHighlighter(self.text_widget, self.theme)
        self._apply_highlighting()

    def _find_next(self):
        search_text = self.search_var.get()
        if not search_text:
            from tkinter import messagebox
            messagebox.showinfo("Поиск", "Введите текст для поиска")
            return
        self.text_widget.config(state=tk.NORMAL)
        pos = self.text_widget.search(search_text, self._search_pos, stopindex=tk.END)
        if pos:
            end_pos = self.text_widget.index(f"{pos}+{len(search_text)}c")
            self.text_widget.tag_remove("found", "1.0", tk.END)
            self.text_widget.tag_add("found", pos, end_pos)
            self.text_widget.tag_configure("found", background="yellow", foreground="black")
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
                self.text_widget.tag_configure("found", background="yellow", foreground="black")
                self.text_widget.see(pos)
                self.text_widget.mark_set(tk.INSERT, end_pos)
                self._search_pos = end_pos
                self.search_status.config(text=f"Найдено в позиции {pos} (с начала)", foreground="green")
            else:
                self.search_status.config(text="Не найдено", foreground="red")
                self._search_pos = "1.0"
        self.text_widget.config(state=tk.DISABLED)

    def _reset_search(self):
        self.search_var.set("")
        self._search_pos = "1.0"
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.tag_remove("found", "1.0", tk.END)
        self.text_widget.config(state=tk.DISABLED)
        self.search_status.config(text="Найдено: 0", foreground="gray")

    def _save_as(self):
        from tkinter import filedialog
        filepath = filedialog.asksaveasfilename(defaultextension=".nc",
                                                filetypes=[("G-code", "*.nc"), ("Text", "*.txt")])
        if filepath:
            self.text_widget.config(state=tk.NORMAL)
            content = self.text_widget.get("1.0", tk.END).rstrip('\n')
            self.text_widget.config(state=tk.DISABLED)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

    def _copy_all(self):
        self.text_widget.config(state=tk.NORMAL)
        content = self.text_widget.get("1.0", tk.END).rstrip('\n')
        self.text_widget.config(state=tk.DISABLED)
        self.window.clipboard_clear()
        self.window.clipboard_append(content)

    def _copy_selected(self):
        try:
            self.text_widget.config(state=tk.NORMAL)
            selected = self.text_widget.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.text_widget.config(state=tk.DISABLED)
            self.window.clipboard_clear()
            self.window.clipboard_append(selected)
        except tk.TclError:
            pass