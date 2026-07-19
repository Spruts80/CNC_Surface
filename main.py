#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Точка входа G-Code Studio.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from gcode_studio.controller import GCodeStudio

def main():
    root = tk.Tk()
    app = GCodeStudio(root)
    root.mainloop()

if __name__ == "__main__":
    main()