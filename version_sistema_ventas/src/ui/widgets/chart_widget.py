import sys
import sqlite3
import shutil
import pandas as pd
from datetime import datetime
import logging
import re

# Importaciones de PySide6 (Qt)
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, 
                             QMessageBox, QFileDialog, QFrame,
                             QScrollArea, QInputDialog, QStackedWidget,
                             QDateEdit, QDialog, QFormLayout, QComboBox, 
                             QAbstractItemView, QListWidget, QButtonGroup, 
                             QGroupBox, QGridLayout, QCheckBox, QDoubleSpinBox, QSpinBox,
                             QDateTimeEdit, QListWidgetItem, QCompleter, QTabWidget)
from PySide6.QtCore import Qt, QDate, Signal, QStringListModel
from PySide6.QtGui import QColor, QFont, QIcon, QPalette, QTextDocument, QPageLayout, QPageSize, QShortcut, QKeySequence, QIntValidator, QDoubleValidator
from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog

# Importaciones de Matplotlib (Gráficos)
# Recommended for PySide6
import matplotlib
try:
    matplotlib.use('QtAgg')
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
except:
    matplotlib.use('Qt5Agg')
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import io
import os
import json
import threading
from src.exchange import ExchangeRates
from src.search import GlobalSearch
from src.notifications import ReminderManager
from src.styles import get_stylesheet
from src.icons import load_icon
import qtawesome as qta

# =============================================================================
# CONFIGURACIÓN DE ESTILOS (CSS)
# =============================================================================
STYLESHEET = get_stylesheet("light")



# =============================================================================
# CLASE: GESTOR DE BASE DE DATOS
# Maneja toda la lógica SQL, conexiones y transacciones.
# =============================================================================

class ChartWidget(QWidget):
    def __init__(self, theme='dark'):
        super().__init__()
        self.theme_mode = theme
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        self.bg_color = '#1e293b' if theme == 'dark' else '#ffffff'
        self.text_color = '#f8fafc' if theme == 'dark' else '#0f172a'
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.figure.patch.set_facecolor(self.bg_color)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
    
    def set_theme(self, theme):
        self.theme_mode = theme
        self.bg_color = '#1e293b' if theme == 'dark' else '#ffffff'
        self.text_color = '#f8fafc' if theme == 'dark' else '#0f172a'
        self.figure.patch.set_facecolor(self.bg_color)
        self.canvas.draw()
        
    def plot_donut(self, data, title="Distribución"):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(self.bg_color)
        if not data or sum(data.values()) == 0:
            ax.text(0.5, 0.5, "Sin Datos", ha='center', va='center', color=self.text_color)
            ax.axis('off')
        else:
            labels = list(data.keys())
            sizes = list(data.values())
            colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']
            wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%', 
                                              startangle=90, colors=colors, pctdistance=0.85,
                                              wedgeprops=dict(width=0.3, edgecolor=self.bg_color))
            plt.setp(autotexts, size=8, weight="bold", color="white")
            plt.setp(texts, size=8, color=self.text_color)
            if title: ax.set_title(title, color=self.text_color, pad=10)
        self.canvas.draw()

    def plot_line(self, x_labels, y_values, title="Historial"):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(self.bg_color)
        if not y_values:
            ax.text(0.5, 0.5, "Sin Datos", ha='center', va='center', color=self.text_color)
            ax.axis('off')
        else:
            # Dibujar línea y área sombreada
            ax.plot(x_labels, y_values, color='#3b82f6', marker='o', linewidth=2, markersize=4)
            ax.fill_between(x_labels, y_values, color='#3b82f6', alpha=0.1)
            ax.set_title(title, color=self.text_color, pad=15)
            ax.tick_params(colors=self.text_color, labelsize=7)
            for spine in ax.spines.values():
                spine.set_color(self.border_color())
            # Rotar etiquetas de X a 45° con alineación correcta usando FixedLocator
            try:
                ax.xaxis.set_major_locator(ticker.FixedLocator(range(len(x_labels))))
                ax.set_xticklabels(x_labels, rotation=45, ha='right', color=self.text_color, fontsize=7)
                self.figure.subplots_adjust(left=0.12, right=0.97, top=0.88, bottom=0.28)
            except Exception:
                pass
        self.canvas.draw()

    def plot_horizontal_bar(self, y_labels, x_values, title="Top"):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(self.bg_color)
        if not x_values:
            ax.text(0.5, 0.5, "Sin Datos", ha='center', va='center', color=self.text_color)
            ax.axis('off')
        else:
            colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']
            plot_colors = [colors[i % len(colors)] for i in range(len(y_labels))]
            ax.barh(y_labels, x_values, color=plot_colors)
            ax.set_title(title, color=self.text_color, pad=15)
            ax.tick_params(colors=self.text_color, labelsize=8)
            for spine in ax.spines.values():
                spine.set_color(self.border_color())
            try:
                self.figure.subplots_adjust(left=0.22, right=0.97, top=0.88, bottom=0.08)
            except Exception:
                pass
        self.canvas.draw()

    def plot_bar(self, x_labels, y_values, title="Tendencia"):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(self.bg_color)
        if not y_values or sum(y_values) == 0:
            ax.text(0.5, 0.5, "Sin Datos", ha='center', va='center', color=self.text_color)
            ax.axis('off')
        else:
            colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']
            plot_colors = [colors[i % len(colors)] for i in range(len(x_labels))]
            ax.bar(x_labels, y_values, color=plot_colors)
            ax.set_title(title, color=self.text_color, pad=15)
            ax.tick_params(colors=self.text_color, labelsize=7)
            for spine in ax.spines.values():
                spine.set_color(self.border_color())
            # Rotar etiquetas de X a 45° usando el Axes directamente con FixedLocator
            try:
                ax.xaxis.set_major_locator(ticker.FixedLocator(range(len(x_labels))))
                ax.set_xticklabels(x_labels, rotation=45, ha='right', color=self.text_color, fontsize=7)
                self.figure.subplots_adjust(left=0.12, right=0.97, top=0.88, bottom=0.30)
            except Exception:
                pass
        self.canvas.draw()

    def border_color(self):
        return '#334155' if self.theme_mode == 'dark' else '#e2e8f0'

# =============================================================================
# DIÁLOGO: TRANSACCIÓN CON CALCULADORA INTELIGENTE
# =============================================================================
