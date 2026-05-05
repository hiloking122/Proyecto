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

class PaymentHistoryDialog(QDialog):
    def __init__(self, payments, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Historial de Pagos")
        self.setMinimumSize(420, 280)
        self.resize(500, 360)
        layout = QVBoxLayout(self)
        lbl = QLabel("<b>Historial de pagos parciales</b>")
        layout.addWidget(lbl)
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(4)
        self.tbl.setHorizontalHeaderLabels(["Fecha", "Monto ($)", "Método", "Nota"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setRowCount(len(payments))
        for i, p in enumerate(payments):
            self.tbl.setItem(i, 0, QTableWidgetItem(p['fecha']))
            self.tbl.setItem(i, 1, QTableWidgetItem(f"{p['monto_usdt']:,.2f} $"))
            self.tbl.setItem(i, 2, QTableWidgetItem(p['metodo']))
            self.tbl.setItem(i, 3, QTableWidgetItem(p['nota']))
        layout.addWidget(self.tbl)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

# =============================================================================
# DIALOG: DETALLE DE VENTA
# =============================================================================
