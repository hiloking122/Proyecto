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

class ServiceDialog(QDialog):
    def __init__(self, parent=None, db_manager=None, sid=None):
        super().__init__(parent)
        self.db = db_manager
        self.sid = sid
        self.setWindowTitle("Servicio" if not sid else "Editar Servicio")
        self.setMinimumSize(380, 400)
        self.resize(440, 470)
        self.setup_ui()
        if self.sid:
            self.load_data()

    def apply_math(self, line_edit):
        """Evalúa expresiones matemáticas simples en el campo de texto."""
        text = line_edit.text().replace(',', '.')
        if not text: return
        try:
            clean = re.sub(r'[^0-9\+\-\*\/\.\(\)]', '', text)
            if any(op in clean for op in '+-*/'):
                res = eval(clean, {"__builtins__": None}, {})
                line_edit.setText(f"{float(res):.2f}")
        except:
            pass

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.txt_codigo = QLineEdit()
        self.txt_codigo.setPlaceholderText("Ej: SERV-001")
        
        ly_codigo = QHBoxLayout()
        ly_codigo.setSpacing(6)
        ly_codigo.addWidget(self.txt_codigo)
        btn_gen_cod_srv = QPushButton("⚡ Generar")
        btn_gen_cod_srv.setToolTip("Generar código automático")
        btn_gen_cod_srv.clicked.connect(lambda: self.txt_codigo.setText(f"SERV-{datetime.now().strftime('%Y%m%d%H%M%S')}"))
        ly_codigo.addWidget(btn_gen_cod_srv)

        self.txt_nombre = QLineEdit()
        self.txt_desc = QLineEdit()
        
        # Precio con mini-calculadora
        self.txt_precio = QLineEdit()
        self.txt_precio.setPlaceholderText("Ej: 10*1.50 para bultos")
        self.txt_precio.setToolTip("Puede escribir operaciones matemáticas como 100/12 y se calcularán automáticamente")
        self.txt_precio.editingFinished.connect(lambda: self.apply_math(self.txt_precio))
        
        ly_precio = QHBoxLayout()
        ly_precio.addWidget(self.txt_precio)
        btn_calc = QPushButton("🧮")
        btn_calc.setToolTip("Calcular expresión")
        btn_calc.setFixedWidth(40)
        btn_calc.clicked.connect(lambda: self.apply_math(self.txt_precio))
        ly_precio.addWidget(btn_calc)
        
        self.cmb_cat = QComboBox()
        self.cmb_cat.addItems(["General", "Servicios Digitales", "Mantenimiento", "Asesoría"])
        # Intentar cargar categorías existentes de la base de datos
        try:
            cats = [r['categoria'] for r in self.db.get_connection().cursor().execute("SELECT DISTINCT categoria FROM servicios").fetchall()]
            for c in cats:
                if self.cmb_cat.findText(c) == -1:
                    self.cmb_cat.addItem(c)
        except: pass
        self.cmb_cat.setEditable(True)
        
        self.chk_destacado = QCheckBox("Marcar como destacado (aparece primero)")
        
        form.addRow("Código:", ly_codigo)
        form.addRow("Nombre:", self.txt_nombre)
        form.addRow("Descripción:", self.txt_desc)
        form.addRow("Precio ($):", ly_precio)
        form.addRow("Categoría:", self.cmb_cat)
        form.addRow("", self.chk_destacado)
        
        layout.addLayout(form)
        
        lbl_hint = QLabel("<small style='color: #64748b;'>💡 <b>Tip:</b> Escriba una operación (ej: 120/12) y presione Enter o el botón 🧮 para calcular el precio unitario.</small>")
        lbl_hint.setWordWrap(True)
        layout.addWidget(lbl_hint)
        
        btns = QHBoxLayout()
        btn_save = QPushButton("Guardar"); btn_save.setObjectName("btn_success"); btn_save.clicked.connect(self.save)
        btn_cancel = QPushButton("Cancelar"); btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel); btns.addWidget(btn_save)
        layout.addLayout(btns)

    def load_data(self):
        row = self.db.get_connection().cursor().execute("SELECT * FROM servicios WHERE id=?", (self.sid,)).fetchone()
        if row:
            self.txt_codigo.setText(row['codigo'])
            self.txt_nombre.setText(row['nombre'])
            self.txt_desc.setText(row['descripcion'] or "")
            self.txt_precio.setText(str(row['precio']))
            self.cmb_cat.setCurrentText(row['categoria'])
            self.chk_destacado.setChecked(bool(row['destacado']))

    def save(self):
        try:
            codigo = self.txt_codigo.text()
            nombre = self.txt_nombre.text()
            precio = float(self.txt_precio.text() or 0)
            if not nombre: raise ValueError("Nombre es obligatorio")
            
            destacado = 1 if self.chk_destacado.isChecked() else 0
            
            if self.sid:
                self.db.update_service(self.sid, codigo, nombre, self.txt_desc.text(), precio, self.cmb_cat.currentText(), destacado)
            else:
                self.db.add_service(codigo, nombre, self.txt_desc.text(), precio, self.cmb_cat.currentText(), destacado)
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

# =============================================================================
# DIALOG: PRODUCTO (INVENTARIO)
# =============================================================================
