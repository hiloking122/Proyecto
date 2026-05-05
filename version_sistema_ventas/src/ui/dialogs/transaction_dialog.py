import sys
import sqlite3
import shutil
import pandas as pd  # type: ignore
from datetime import datetime
import logging
import re

# Importaciones de PySide6 (Qt)
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,  # type: ignore
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, 
                             QMessageBox, QFileDialog, QFrame,
                             QScrollArea, QInputDialog, QStackedWidget,
                             QDateEdit, QDialog, QFormLayout, QComboBox, 
                             QAbstractItemView, QListWidget, QButtonGroup, 
                             QGroupBox, QGridLayout, QCheckBox, QDoubleSpinBox, QSpinBox,
                             QDateTimeEdit, QListWidgetItem, QCompleter, QTabWidget)
from PySide6.QtCore import Qt, QDate, Signal, QStringListModel  # type: ignore
from PySide6.QtGui import QColor, QFont, QIcon, QPalette, QTextDocument, QPageLayout, QPageSize, QShortcut, QKeySequence, QIntValidator, QDoubleValidator  # type: ignore
from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog  # type: ignore

# Importaciones de Matplotlib (Gráficos)
# Recommended for PySide6
import matplotlib  # type: ignore
try:
    matplotlib.use('QtAgg')
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas  # type: ignore
except:
    matplotlib.use('Qt5Agg')
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas  # type: ignore
from matplotlib.figure import Figure  # type: ignore
import matplotlib.pyplot as plt  # type: ignore
import matplotlib.ticker as ticker  # type: ignore
import io
import os
import json
import threading
from src.exchange import ExchangeRates  # type: ignore
from src.search import GlobalSearch  # type: ignore
from src.notifications import ReminderManager  # type: ignore
from src.styles import get_stylesheet  # type: ignore
from src.icons import load_icon  # type: ignore
import qtawesome as qta  # type: ignore

# =============================================================================
# CONFIGURACIÓN DE ESTILOS (CSS)
# =============================================================================
STYLESHEET = get_stylesheet("light")



# =============================================================================
# CLASE: GESTOR DE BASE DE DATOS
# Maneja toda la lógica SQL, conexiones y transacciones.
# =============================================================================

class TransactionDialog(QDialog):
    def __init__(self, parent=None, db_manager=None, tx_id=None):
        super().__init__(parent)
        self.db = db_manager
        self.tx_id = tx_id
        self.setWindowTitle("Registrar Movimiento" if not tx_id else "Editar Movimiento")
        self.setMinimumSize(400, 380)
        self.resize(460, 460)
        self.tasa = self.db.get_tasa()
        self.setup_ui()
        if self.tx_id:
            self.load_transaction()

    def load_transaction(self):
        row = self.db.get_connection().cursor().execute("SELECT * FROM transacciones WHERE id=?", (self.tx_id,)).fetchone()
        if not row:
            return
        self.txt_desc.setText(row['descripcion'])
        self.txt_usdt.setText(f"{row['monto_usdt']:.2f}")
        self.txt_ves.setText(f"{row['monto_ves']:.2f}")
        # sincronizar tipo/categoría
        self.cmb_tipo.setCurrentText(row['tipo'])
        self.update_categories()
        idx = self.cmb_cat.findText(row['categoria'])
        if idx == -1:
            self.cmb_cat.addItem(row['categoria'])
            self.cmb_cat.setCurrentText(row['categoria'])
        else:
            self.cmb_cat.setCurrentIndex(idx)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Tasa Informativa
        lbl_tasa = QLabel(f"ℹ️ Tasa de conversión actual: <b>{self.tasa:.2f} VES/USDT</b>")
        lbl_tasa.setStyleSheet("color: #1e293b; background: #e0f2fe; padding: 5px; border-radius: 4px; border: 1px solid #7dd3fc;")
        layout.addWidget(lbl_tasa)

        # Formulario
        form = QFormLayout()
        
        self.cmb_tipo = QComboBox()
        self.cmb_tipo.addItems(["GASTO", "INGRESO"])
        self.cmb_tipo.currentTextChanged.connect(self.update_categories)
        
        # Campos de Monto (Calculadora Bidireccional)
        self.txt_ves = QLineEdit()
        self.txt_ves.setPlaceholderText("Monto en Bolívares")
        self.txt_usdt = QLineEdit()
        self.txt_usdt.setPlaceholderText("Monto en USD")
        
        # Conexiones de la calculadora
        self.txt_ves.textChanged.connect(self.calculate_usdt)
        self.txt_usdt.textChanged.connect(self.calculate_ves)

        self.txt_desc = QLineEdit()
        self.txt_desc.setPlaceholderText("Ej: Pago de nómina, Venta #123")
        
        self.cmb_cat = QComboBox()
        self.update_categories() # Llenar inicial

        form.addRow("Tipo:", self.cmb_tipo)
        form.addRow("Monto (VES):", self.txt_ves)
        form.addRow("Monto (USDT):", self.txt_usdt)
        form.addRow("Descripción:", self.txt_desc)
        form.addRow("Categoría:", self.cmb_cat)
        
        layout.addLayout(form)
        
        # Botones
        btn_box = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        
        btn_save = QPushButton("Guardar Operación")
        btn_save.setObjectName("btn_success")
        btn_save.clicked.connect(self.save_transaction)
        
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

    def calculate_usdt(self):
        if self.txt_ves.hasFocus():
            try:
                val = float(self.txt_ves.text())
                self.txt_usdt.setText(f"{val / self.tasa:.2f}")
            except ValueError:
                self.txt_usdt.clear()

    def calculate_ves(self):
        if self.txt_usdt.hasFocus():
            try:
                val = float(self.txt_usdt.text())
                self.txt_ves.setText(f"{val * self.tasa:.2f}")
            except ValueError:
                self.txt_ves.clear()

    def update_categories(self):
        self.cmb_cat.clear()
        if self.cmb_tipo.currentText() == "INGRESO":
            self.cmb_cat.addItems(["Ventas", "Servicios", "Salario", "Otros Ingresos"])
        else:
            # categorías genéricas (prescindimos de las etiquetas 50/30/20)
            self.cmb_cat.addItems(["General", "Emergencias", "Otros"])

    def save_transaction(self):
        try:
            usdt = float(self.txt_usdt.text())
            ves = float(self.txt_ves.text())
            if usdt <= 0: raise ValueError
            desc = self.txt_desc.text()
            cat = self.cmb_cat.currentText()
            tipo = self.cmb_tipo.currentText()
            if self.tx_id:
                # Actualizar
                self.db.update_transaction(self.tx_id, desc, usdt, ves, cat, tipo)
            else:
                self.db.add_transaction(desc, usdt, ves, cat, tipo)
            self.accept()
        except ValueError:
            QMessageBox.warning(self, "Error", "Por favor ingrese montos numéricos válidos.")

# Login eliminado: no hay autenticación de usuario.

# =============================================================================
# DIALOG: HISTORIAL DE PAGOS PARCIALES
# =============================================================================
