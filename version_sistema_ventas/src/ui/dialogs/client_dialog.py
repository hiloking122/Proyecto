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

class ClientDialog(QDialog):
    def __init__(self, parent=None, db_manager=None, cid=None):
        super().__init__(parent)
        self.db = db_manager
        self.cid = cid
        self.setWindowTitle("Nuevo Cliente" if not cid else "Editar Cliente")
        self.setMinimumSize(360, 300)
        self.resize(440, 380)
        self.setup_ui()
        if self.cid:
            self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.txt_nombre = QLineEdit()
        self.txt_cedula = QLineEdit()
        self.txt_cedula.setValidator(QIntValidator()) # Solo números en cédula
        self.txt_cedula.setPlaceholderText("Solo números...")
        self.txt_telefono = QLineEdit()
        self.txt_direccion = QLineEdit()
        
        form.addRow("Nombre Completo:", self.txt_nombre)
        form.addRow("Cédula/RIF:", self.txt_cedula)
        form.addRow("Teléfono:", self.txt_telefono)
        form.addRow("Dirección:", self.txt_direccion)
        
        layout.addLayout(form)
        
        btns = QHBoxLayout()
        btn_save = QPushButton("Guardar"); btn_save.setObjectName("btn_success"); btn_save.clicked.connect(self.save)
        btn_cancel = QPushButton("Cancelar"); btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel); btns.addWidget(btn_save)
        layout.addLayout(btns)

    def load_data(self):
        row = self.db.get_connection().cursor().execute("SELECT * FROM clientes WHERE id=?", (self.cid,)).fetchone()
        if row:
            self.txt_nombre.setText(row['nombre'])
            self.txt_cedula.setText(row['cedula'])
            self.txt_telefono.setText(row['telefono'])
            self.txt_direccion.setText(row['direccion'])

    def save(self):
        nombre = self.txt_nombre.text()
        cedula = self.txt_cedula.text()
        if not nombre or not cedula:
            QMessageBox.warning(self, "Error", "Nombre y Cédula son obligatorios")
            return
        
        try:
            with self.db.get_connection() as conn:
                if self.cid:
                    conn.cursor().execute(
                        "UPDATE clientes SET nombre=?, cedula=?, telefono=?, direccion=? WHERE id=?",
                        (nombre, cedula, self.txt_telefono.text(), self.txt_direccion.text(), self.cid)
                    )
                else:
                    conn.cursor().execute(
                        "INSERT INTO clientes (nombre, cedula, telefono, direccion) VALUES (?,?,?,?)",
                        (nombre, cedula, self.txt_telefono.text(), self.txt_direccion.text())
                    )
                conn.commit()
            self.accept()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Error", "La cédula ya existe.")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

# =============================================================================
# DIALOG: SERVICIO
# =============================================================================
