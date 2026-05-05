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

class ProductDialog(QDialog):
    """Diálogo mejorado para productos con calculadora de precios en tiempo real."""
    def __init__(self, parent=None, db_manager=None, pid=None):
        super().__init__(parent)
        self.db = db_manager
        self.pid = pid
        self._updating = False
        self.tasa_ref = self.db.get_tasa_bcv()
        self.setWindowTitle("📦 Nuevo Producto" if not pid else "✏️ Editar Producto")
        self.setMinimumSize(480, 560)
        self.resize(520, 600)
        self.setup_ui()
        if self.pid:
            self.load_data()

    def apply_math(self, line_edit):
        """Evalúa expresiones matemáticas simples en el campo de texto."""
        text = line_edit.text().replace(',', '.')
        if not text: return
        try:
            clean = re.sub(r'[^0-9\+\-\*\/\.\(\)\s]', '', text)
            if any(op in clean for op in '+-*/'):
                res = eval(clean, {"__builtins__": None}, {})
                line_edit.setText(f"{float(res):.4f}".rstrip('0').rstrip('.'))
                if '.' not in line_edit.text():
                    line_edit.setText(f"{float(res):.2f}")
        except:
            pass

    def _suggest_price_from_margin(self, margin_pct=30.0):
        """Sugiere un precio dado un % de margen sobre costo."""
        try:
            costo = float(self.txt_costo.text().replace(',', '.') or 0)
            if costo > 0:
                precio_sug = costo * (1 + margin_pct / 100)
                self.txt_precio.setText(f"{precio_sug:.2f}")
                self.update_margin_preview()
        except: pass

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(14)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # ----- Sección 1: Identificación del Producto -----
        gb_id = QGroupBox("📋 Identificación")
        form_id = QFormLayout(gb_id)
        form_id.setSpacing(10)

        self.txt_codigo = QLineEdit()
        self.txt_codigo.setPlaceholderText("Ej: PROD-001")
        
        ly_codigo = QHBoxLayout()
        ly_codigo.setSpacing(6)
        ly_codigo.addWidget(self.txt_codigo)
        btn_gen_cod_inv = QPushButton("⚡ Generar")
        btn_gen_cod_inv.setToolTip("Generar código automático")
        btn_gen_cod_inv.clicked.connect(lambda: self.txt_codigo.setText(f"PROD-{datetime.now().strftime('%Y%m%d%H%M%S')}"))
        ly_codigo.addWidget(btn_gen_cod_inv)
        
        self.txt_nombre = QLineEdit()
        self.txt_nombre.setPlaceholderText("Nombre completo del producto")
        self.txt_desc = QLineEdit()
        self.txt_desc.setPlaceholderText("Descripción opcional")

        self.cmb_cat = QComboBox()
        self.cmb_cat.addItems(["General", "Electrónica", "Accesorios", "Papelería", "Alimentos", "Repuestos"])
        try:
            cats = [r['categoria'] for r in self.db.get_connection().cursor().execute(
                "SELECT DISTINCT categoria FROM inventario WHERE categoria IS NOT NULL").fetchall()]
            for c in cats:
                if c and self.cmb_cat.findText(c) == -1:
                    self.cmb_cat.addItem(c)
        except: pass
        self.cmb_cat.setEditable(True)

        form_id.addRow("Código:", ly_codigo)
        form_id.addRow("Nombre:*", self.txt_nombre)
        form_id.addRow("Descripción:", self.txt_desc)
        form_id.addRow("Categoría:", self.cmb_cat)
        main_layout.addWidget(gb_id)

        # ----- Sección 2: Precios y Calculadora -----
        gb_prices = QGroupBox("💰 Precios y Calculadora de Margen")
        prices_layout = QVBoxLayout(gb_prices)
        prices_layout.setSpacing(10)

        form_prices = QFormLayout()
        form_prices.setSpacing(10)

        # COSTO con calculadora
        self.txt_costo = QLineEdit()
        self.txt_costo.setPlaceholderText("Ej: 50.00 | bulto: 600/12 = 50")
        self.txt_costo.setToolTip("💡 Puede escribir: 600/12 (bulto de 12), 3.5*4 (4 unidades de 3.50)")
        self.txt_costo.editingFinished.connect(lambda: (self.apply_math(self.txt_costo), self.update_margin_preview()))
        self.txt_costo.textChanged.connect(self.update_margin_preview)

        ly_costo = QHBoxLayout()
        ly_costo.setSpacing(6)
        ly_costo.addWidget(self.txt_costo)
        btn_ccalc = QPushButton("=")
        btn_ccalc.setObjectName("btn_calc")
        btn_ccalc.setToolTip("Calcular expresión")
        btn_ccalc.setFixedWidth(36)
        btn_ccalc.setFixedHeight(36)
        btn_ccalc.clicked.connect(lambda: (self.apply_math(self.txt_costo), self.update_margin_preview()))
        ly_costo.addWidget(btn_ccalc)

        # PRECIO con calculadora
        self.txt_precio = QLineEdit()
        self.txt_precio.setPlaceholderText("Ej: 65.00 | con margen: costo*1.30")
        self.txt_precio.setToolTip("💡 Puede escribir: 50*1.30 (30% sobre costo), o un precio directo")
        self.txt_precio.editingFinished.connect(lambda: (self.apply_math(self.txt_precio), self.update_margin_preview()))
        self.txt_precio.textChanged.connect(self.update_margin_preview)

        ly_precio = QHBoxLayout()
        ly_precio.setSpacing(6)
        ly_precio.addWidget(self.txt_precio)
        btn_pcalc = QPushButton("=")
        btn_pcalc.setObjectName("btn_calc")
        btn_pcalc.setToolTip("Calcular expresión de precio")
        btn_pcalc.setFixedWidth(36)
        btn_pcalc.setFixedHeight(36)
        btn_pcalc.clicked.connect(lambda: (self.apply_math(self.txt_precio), self.update_margin_preview()))
        ly_precio.addWidget(btn_pcalc)

        form_prices.addRow("Costo ($):", ly_costo)
        form_prices.addRow("Precio Venta ($):", ly_precio)
        prices_layout.addLayout(form_prices)

        # Botones de margen rápido
        lbl_margin_hint = QLabel("⚡ Sugerir precio con margen:")
        lbl_margin_hint.setObjectName("subtitle")
        prices_layout.addWidget(lbl_margin_hint)

        margin_btns = QHBoxLayout()
        margin_btns.setSpacing(6)
        for pct in [10, 20, 25, 30, 35, 50]:
            btn_m = QPushButton(f"+{pct}%")
            btn_m.setFixedHeight(30)
            btn_m.setStyleSheet(
                "QPushButton { background-color: #f0f9ff; border: 1px solid #bae6fd; "
                "color: #0369a1; border-radius: 6px; font-weight: 700; font-size: 12px; padding: 2px 8px; }"
                "QPushButton:hover { background-color: #e0f2fe; }"
            )
            btn_m.clicked.connect(lambda _, p=pct: self._suggest_price_from_margin(p))
            margin_btns.addWidget(btn_m)
        prices_layout.addLayout(margin_btns)

        # Preview de margen en tiempo real
        self.lbl_margin_preview = QLabel("Ingrese costo y precio para ver el análisis")
        self.lbl_margin_preview.setObjectName("calc_preview")
        self.lbl_margin_preview.setWordWrap(True)
        self.lbl_margin_preview.setMinimumHeight(60)
        prices_layout.addWidget(self.lbl_margin_preview)

        main_layout.addWidget(gb_prices)

        # ----- Sección 3: Stock y Destacado -----
        gb_stock = QGroupBox("📊 Stock e Inventario")
        form_stock = QFormLayout(gb_stock)
        form_stock.setSpacing(10)

        self.txt_stock = QLineEdit()
        self.txt_stock.setPlaceholderText("Cantidad en stock")
        self.txt_stock.setValidator(QIntValidator(0, 999999))
        self.chk_destacado = QCheckBox("⭐ Marcar como destacado — aparece primero en POS")

        form_stock.addRow("Stock Disponible:", self.txt_stock)
        form_stock.addRow("", self.chk_destacado)
        main_layout.addWidget(gb_stock)

        # Hint operaciones matemáticas
        lbl_hint = QLabel(
            "💡 <b>Calculadora de expresiones:</b>  "
            "<code>600/12</code> = costo por unidad de bulto de 12  |  "
            "<code>costo×1.30</code> = precio con 30% de margen"
        )
        lbl_hint.setWordWrap(True)
        lbl_hint.setStyleSheet("color: #64748b; font-size: 11px; padding: 4px 8px; "
                               "background: #f8fafc; border-radius: 6px; border: 1px solid #e2e8f0;")
        main_layout.addWidget(lbl_hint)

        # Botones de acción
        btns = QHBoxLayout()
        btns.setSpacing(10)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setFixedHeight(40)
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("💾 Guardar Producto")
        btn_save.setObjectName("btn_success")
        btn_save.setFixedHeight(40)
        btn_save.clicked.connect(self.save)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save, 2)
        main_layout.addLayout(btns)

    def update_margin_preview(self):
        """Actualiza el panel preview con el análisis de margen en tiempo real."""
        if self._updating:
            return
        self._updating = True
        try:
            costo_txt = self.txt_costo.text().replace(',', '.')
            precio_txt = self.txt_precio.text().replace(',', '.')

            # Intentar evaluar expresiones si contienen operadores
            def eval_expr(txt):
                clean = re.sub(r'[^0-9\+\-\*\/\.\(\)\s]', '', txt)
                try:
                    return float(eval(clean, {"__builtins__": None}, {})) if clean else 0.0
                except:
                    try: return float(clean)
                    except: return 0.0

            costo = eval_expr(costo_txt)
            precio = eval_expr(precio_txt)
            tasa = self.tasa_ref

            if costo > 0 and precio > 0:
                ganancia = precio - costo
                margen = (ganancia / costo) * 100
                precio_ves = precio * tasa
                costo_ves = costo * tasa

                if margen >= 20:
                    obj = "calc_preview"
                    icono = "✅"
                else:
                    obj = "calc_preview_warn"
                    icono = "⚠️"

                self.lbl_margin_preview.setObjectName(obj)
                self.lbl_margin_preview.setStyle(self.lbl_margin_preview.style())
                self.lbl_margin_preview.setText(
                    f"{icono}  Costo: <b>${costo:,.2f}</b>  →  Precio: <b>${precio:,.2f}</b>  "
                    f"│  Ganancia: <b>${ganancia:,.2f}</b>  │  Margen: <b>{margen:.1f}%</b><br>"
                    f"🇻🇪  Costo Bs: <b>{costo_ves:,.2f}</b>  │  Precio Bs: <b>{precio_ves:,.2f}</b>  (Tasa: {tasa:.2f})"
                )
            elif costo > 0:
                tasa = self.tasa_ref
                self.lbl_margin_preview.setObjectName("calc_preview")
                self.lbl_margin_preview.setStyle(self.lbl_margin_preview.style())
                self.lbl_margin_preview.setText(
                    f"💵  Costo: <b>${costo:,.2f}</b>  │  Bs: <b>{costo * tasa:,.2f}</b>  "
                    f"→ Ingrese el precio de venta para ver el margen"
                )
            else:
                self.lbl_margin_preview.setObjectName("calc_preview")
                self.lbl_margin_preview.setStyle(self.lbl_margin_preview.style())
                self.lbl_margin_preview.setText("Ingrese costo y precio para ver el análisis de rentabilidad")
        except:
            pass
        finally:
            self._updating = False

    def load_data(self):
        row = self.db.get_connection().cursor().execute("SELECT * FROM inventario WHERE id=?", (self.pid,)).fetchone()
        if row:
            self.txt_codigo.setText(str(row['codigo'] or ''))
            self.txt_nombre.setText(str(row['nombre'] or ''))
            self.txt_desc.setText(str(row['descripcion'] or ''))
            self.txt_costo.setText(str(row['costo']))
            self.txt_precio.setText(str(row['precio']))
            self.txt_stock.setText(str(row['stock']))
            self.cmb_cat.setCurrentText(str(row['categoria'] or 'General'))
            self.chk_destacado.setChecked(bool(row['destacado']))
            self.update_margin_preview()

    def save(self):
        try:
            codigo = self.txt_codigo.text().strip()
            nombre = self.txt_nombre.text().strip()
            desc = self.txt_desc.text().strip()

            # Evaluar expresiones matemáticas antes de guardar
            def parse_val(txt):
                txt = txt.replace(',', '.')
                clean = re.sub(r'[^0-9\+\-\*\/\.\(\)\s]', '', txt)
                try:
                    return float(eval(clean, {"__builtins__": None}, {})) if clean else 0.0
                except:
                    try: return float(clean)
                    except: return 0.0

            costo = parse_val(self.txt_costo.text())
            precio = parse_val(self.txt_precio.text())
            stock = int(self.txt_stock.text() or 0)
            cat = self.cmb_cat.currentText().strip()
            destacado = 1 if self.chk_destacado.isChecked() else 0

            if not codigo or not nombre:
                QMessageBox.warning(self, "Error", "⚠️ Código y Nombre son obligatorios.")
                return

            if precio < costo:
                reply = QMessageBox.question(self, "Precio bajo",
                    f"⚠️ El precio de venta (${precio:.2f}) es menor al costo (${costo:.2f}).\n"
                    f"Esto significaría vender a pérdida. ¿Confirmar de todas formas?",
                    QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.No:
                    return

            if self.pid:
                self.db.update_product(self.pid, codigo, nombre, desc, costo, precio, stock, cat, destacado)
            else:
                self.db.add_product(codigo, nombre, desc, costo, precio, stock, cat, destacado)

            if stock <= 0:
                QMessageBox.warning(self, "Sin Stock",
                    f"⚠️ El producto '{nombre}' fue guardado con stock 0.\nRecuerde hacer re-stock.")

            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al guardar: {e}")

# =============================================================================
# DIALOG: TUTORIAL / AYUDA
# =============================================================================
