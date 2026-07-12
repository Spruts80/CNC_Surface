#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G-Code Studio — Генератор и визуализатор G-кода для ЧПУ.

Скрипт установки пакета.
Использование:
    pip install .           # Установка
    pip install -e .        # Режим разработчика
    python setup.py sdist   # Создание архива
"""

from setuptools import setup, find_packages
import os

# Чтение README для длинного описания
def read_readme():
    here = os.path.abspath(os.path.dirname(__file__))
    try:
        with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "G-Code Studio — генератор и визуализатор G-кода для ЧПУ."


# Чтение requirements.txt
def read_requirements():
    here = os.path.abspath(os.path.dirname(__file__))
    req_path = os.path.join(here, 'requirements.txt')
    try:
        with open(req_path, encoding='utf-8') as f:
            return [
                line.strip()
                for line in f
                if line.strip() and not line.startswith('#')
            ]
    except FileNotFoundError:
        return ['matplotlib>=3.5.0', 'numpy>=1.21.0']


setup(
    # ============================================================
    # Основная информация
    # ============================================================
    name='gcode-studio',
    version='1.0.0',
    description='Генератор и визуализатор G-кода для фрезерных станков с ЧПУ',
    long_description=read_readme(),
    long_description_content_type='text/markdown',
    author='G-Code Studio Team',
    author_email='gcode.studio@example.com',
    url='https://github.com/Spruts80/CNC_Surface',
    license='MIT',

    # ============================================================
    # Классификаторы для PyPI
    # ============================================================
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Manufacturing',
        'Intended Audience :: End Users/Desktop',
        'Topic :: Scientific/Engineering',
        'Topic :: Scientific/Engineering :: Human Machine Interfaces',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: MacOS',
        'Operating System :: POSIX :: Linux',
        'Natural Language :: Russian',
    ],
    keywords='gcode cnc milling g-code generator visualizer',

    # ============================================================
    # Пакеты и модули
    # ============================================================
    packages=find_packages(exclude=['tests', 'tests.*', 'build', 'dist']),
    py_modules=['main'],  # main.py в корне проекта

    # ============================================================
    # Зависимости
    # ============================================================
    python_requires='>=3.7',
    install_requires=read_requirements(),

    # ============================================================
    # Точки входа (команды для запуска)
    # ============================================================
    entry_points={
        'console_scripts': [
            'gcode-studio=main:main',
        ],
        'gui_scripts': [
            'gcode-studio-gui=main:main',
        ],
    },

    # ============================================================
    # Включаемые данные (иконки, ресурсы)
    # ============================================================
    package_data={
        '': ['*.ico', '*.png', '*.jpg'],
    },
    data_files=[
        ('', ['app_icon.ico']) if os.path.exists('app_icon.ico') else ('', []),
    ],
    include_package_data=True,
    zip_safe=False,

    # ============================================================
    # Дополнительные параметры
    # ============================================================
    project_urls={
        'Bug Reports': 'https://github.com/Spruts80/CNC_Surface/issues',
        'Source': 'https://github.com/Spruts80/CNC_Surface',
        'Documentation': 'https://github.com/Spruts80/CNC_Surface/wiki',
    },
)
