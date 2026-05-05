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

class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Guía de Usuario y Atajos")
        self.setMinimumSize(520, 440)
        self.resize(640, 540)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        tabs = QTabWidget()
        
        # Tab 1: Atajos de Teclado
        tab_keys = QWidget()
        keys_layout = QVBoxLayout(tab_keys)
        keys_text = """
        <h3>⌨️ Atajos de Teclado Globales</h3>
        <ul>
            <li><b>F1 - F4 / F7:</b> Navegar entre secciones (POS, Movimientos, Inventario, Reportes).</li>
            <li><b>Ctrl + K:</b> Búsqueda Global en todo el sistema.</li>
            <li><b>Ctrl + T:</b> Cambiar entre Modo Claro y Oscuro.</li>
            <li><b>F10:</b> Abrir Calculadora Interna.</li>
            <li><b>F12:</b> Abrir esta Guía de Ayuda.</li>
        </ul>
        <hr>
        <h3>🛒 Atajos en Punto de Venta (POS)</h3>
        <ul>
            <li><b>Ctrl + F:</b> Poner el foco en la búsqueda de productos.</li>
            <li><b>F5:</b> Procesar Venta / Cobrar.</li>
            <li><b>Ctrl + L:</b> Limpiar Carrito de Compras.</li>
            <li><b>F1 / F2 (Dentro de POS):</b> Alternar entre Productos y Servicios.</li>
        </ul>
        """
        lbl_keys = QLabel(keys_text)
        lbl_keys.setWordWrap(True)
        keys_layout.addWidget(lbl_keys)
        keys_layout.addStretch()
        tabs.addTab(tab_keys, "⌨️ Atajos")
        
        # Tab 2: Tutorial Rápido
        tab_tutorial = QWidget()
        tut_layout = QVBoxLayout(tab_tutorial)
        tut_text = """
        <h3>🚀 Guía Rápida de Uso</h3>
        <ol>
            <li><b>Realizar una Venta:</b> Ve al Punto de Venta, busca un producto, haz clic en "Añadir". Registra al cliente o deja como "Consumidor Final" y presiona <b>F5</b> para terminar.</li>
            <li><b>Gestionar Stock:</b> En "Inventario" puedes editar productos. Los items marcados con ⭐ (Destacados) aparecerán resaltados en el POS para un acceso rápido.</li>
            <li><b>Reportes:</b> Consulta tus ventas diarias, mensuales o anuales con gráficos dinámicos en la sección de Reportes.</li>
            <li><b>Configuración:</b> Asegúrate de tener la <b>Tasa BCV o USDT</b> actualizada para que los precios en Bolívares sean correctos.</li>
        </ol>
        """
        lbl_tut = QLabel(tut_text)
        lbl_tut.setWordWrap(True)
        tut_layout.addWidget(lbl_tut)
        tut_layout.addStretch()
        tabs.addTab(tab_tutorial, "🚀 Tutorial")
        
        layout.addWidget(tabs)
        
        btn_close = QPushButton("Entendido")
        btn_close.setObjectName("btn_primary")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

# =============================================================================
# VENTANA PRINCIPAL (MAIN WINDOW)
# =============================================================================
