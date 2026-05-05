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

class SaleDetailsDialog(QDialog):
    def __init__(self, venta_id, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.venta_id = venta_id
        self.sale_info = self.db.get_venta_header(venta_id)
        self.setWindowTitle(f"Detalle de Venta #{venta_id}")
        self.setMinimumSize(580, 420)
        self.resize(680, 520)
        self.setup_ui()
        self.load_details()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        title_ly = QHBoxLayout()
        header = QLabel(f"📦 <b>Venta #{self.venta_id}</b>")
        header.setObjectName("h2")
        title_ly.addWidget(header)
        title_ly.addStretch()
        
        # Mostrar Cliente
        cliente_txt = self.sale_info.get('cliente_nombre') if self.sale_info else "N/A"
        if not cliente_txt or cliente_txt == 'None':
            cliente_txt = "👤 <font color='orange'><i>Público General (Sin Cliente)</i></font>"
        else:
            cliente_txt = f"👤 <b>{cliente_txt}</b>"
            
        lbl_cliente = QLabel(cliente_txt)
        lbl_cliente.setStyleSheet("font-size: 14px;")
        layout.addLayout(title_ly)
        layout.addWidget(lbl_cliente)
        
        if self.sale_info:
            lbl_fecha = QLabel(f"📅 Fecha: {self.sale_info.get('fecha', 'N/A')}")
            lbl_fecha.setStyleSheet("color: #64748b;")
            layout.addWidget(lbl_fecha)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Tipo", "Descripción", "Cant", "P. Unit ($)", "Subtotal ($)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        self.lbl_total = QLabel("Total: 0.00 $")
        self.lbl_total.setStyleSheet("font-size: 18px; font-weight: bold; color: #10b981;")
        layout.addWidget(self.lbl_total, alignment=Qt.AlignRight)
        
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def load_details(self):
        details = self.db.get_venta_detalle(self.venta_id)
        self.table.setRowCount(len(details))
        total = 0
        for i, d in enumerate(details):
            subtotal = d['cantidad'] * d['precio_unitario']
            total += subtotal
            self.table.setItem(i, 0, QTableWidgetItem(d['tipo']))
            self.table.setItem(i, 1, QTableWidgetItem(d['nombre']))
            self.table.setItem(i, 2, QTableWidgetItem(str(d['cantidad'])))
            self.table.setItem(i, 3, QTableWidgetItem(f"{d['precio_unitario']:.2f}"))
            self.table.setItem(i, 4, QTableWidgetItem(f"{subtotal:.2f}"))
        
        self.lbl_total.setText(f"Total Venta: {total:,.2f} $")

# =============================================================================
# DIALOG: CLIENTE
# =============================================================================
