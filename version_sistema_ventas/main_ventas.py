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
                             QGroupBox, QGridLayout, QCheckBox, QDoubleSpinBox,
                             QDateTimeEdit, QListWidgetItem, QCompleter)
from PySide6.QtCore import Qt, QDate, Signal, QStringListModel
from PySide6.QtGui import QColor, QFont, QIcon, QPalette, QTextDocument, QPageLayout, QPageSize, QShortcut, QKeySequence
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
class DatabaseManager:
    def __init__(self, db_name="finanzas_pro.db"):
        self.db_name = db_name
        self.init_tables()

    def get_connection(self):
        """Retorna una conexión configurada."""
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row  # Permite acceder a columnas por nombre
        return conn

    def init_tables(self):
        """Inicializa las tablas si no existen."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Transacciones (Ingresos/Gastos)
            cursor.execute('''CREATE TABLE IF NOT EXISTS transacciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT, descripcion TEXT, monto_usdt REAL, 
                monto_ves REAL, categoria TEXT, tipo TEXT)''')
            
            # 2. (REMOVIDO) Metas de Ahorro - tabla ya no se utiliza
            # originalmente el sistema gestionaba objetivos de ahorro
            # con reglas 50/30/20; ese módulo fue eliminado según requisitos.
            
            # 3. Configuración (Tasa de cambio persistente)
            cursor.execute('''CREATE TABLE IF NOT EXISTS config (
                clave TEXT PRIMARY KEY, valor TEXT)''')
            
            # 4. Pagos Pendientes (Cuentas por Cobrar)
            cursor.execute('''CREATE TABLE IF NOT EXISTS pendientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER, monto_usdt REAL, monto_pagado REAL DEFAULT 0, fecha TEXT, 
                descripcion TEXT, estado TEXT DEFAULT 'PENDIENTE')''')

            # Tabla para historial de pagos parciales
            cursor.execute('''CREATE TABLE IF NOT EXISTS pagos_parciales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pendiente_id INTEGER, monto_usdt REAL, fecha TEXT, metodo TEXT, nota TEXT,
                FOREIGN KEY(pendiente_id) REFERENCES pendientes(id))''')

            # 5. Recordatorios y notificaciones
            cursor.execute('''CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT, message TEXT, run_at TEXT,
                repeat TEXT DEFAULT 'once', enabled INTEGER DEFAULT 1, created_at TEXT)''')
            
            # 6. Inventario
            cursor.execute('''CREATE TABLE IF NOT EXISTS inventario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE, nombre TEXT, descripcion TEXT,
                costo REAL DEFAULT 0, precio REAL DEFAULT 0,
                stock INTEGER DEFAULT 0, categoria TEXT)''')

            # 7. Clientes (NUEVO)
            cursor.execute('''CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                cedula TEXT UNIQUE,
                telefono TEXT,
                direccion TEXT,
                puntos INTEGER DEFAULT 0)''')

            # 8. Ventas (NUEVO)
            cursor.execute('''CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT,
                cliente_id INTEGER,
                total_usd REAL,
                total_ves REAL,
                metodo_pago TEXT,
                tasa_momento REAL,
                FOREIGN KEY(cliente_id) REFERENCES clientes(id))''')

            # 9. Detalle de Ventas (NUEVO)
            cursor.execute('''CREATE TABLE IF NOT EXISTS detalle_ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                venta_id INTEGER,
                producto_id INTEGER,
                cantidad INTEGER,
                precio_unitario REAL,
                FOREIGN KEY(venta_id) REFERENCES ventas(id),
                FOREIGN KEY(producto_id) REFERENCES inventario(id))''')

            # 10. Gastos (NUEVO)
            cursor.execute('''CREATE TABLE IF NOT EXISTS gastos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT,
                descripcion TEXT,
                monto REAL,
                categoria TEXT)''')

            # 11. Servicios (NUEVO)
            cursor.execute('''CREATE TABLE IF NOT EXISTS servicios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE,
                nombre TEXT NOT NULL,
                descripcion TEXT,
                precio REAL DEFAULT 0,
                categoria TEXT DEFAULT 'Servicios')''')

            # Actualizar Detalle Ventas para soportar servicios
            try:
                cursor.execute("ALTER TABLE detalle_ventas ADD COLUMN servicio_id INTEGER")
            except: pass

            # Actualizar Tabla Pendientes para la columna de compatibilidad cliente
            try:
                cursor.execute("ALTER TABLE pendientes ADD COLUMN cliente TEXT")
            except: pass
            
            # Insertar tasas por defecto
            cursor.execute("INSERT OR IGNORE INTO config (clave, valor) VALUES ('tasa_ves', '60.0')")
            cursor.execute("INSERT OR IGNORE INTO config (clave, valor) VALUES ('tasa_bcv', '60.0')")
            cursor.execute("INSERT OR IGNORE INTO config (clave, valor) VALUES ('tasa_usdt', '60.0')")
            cursor.execute("INSERT OR IGNORE INTO config (clave, valor) VALUES ('tasa_mode', 'api')")
            
            try:
                cursor.execute("CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(name, description, type, ref UNINDEXED);")
            except Exception: pass
            
            # Nuevas configuraciones por defecto
            cursor.execute("INSERT OR IGNORE INTO config (clave, valor) VALUES ('pos_show_ves', '0')")
            cursor.execute("INSERT OR IGNORE INTO config (clave, valor) VALUES ('pos_enable_discount', '0')")
            cursor.execute("INSERT OR IGNORE INTO config (clave, valor) VALUES ('hk_pos', 'F1')")
            cursor.execute("INSERT OR IGNORE INTO config (clave, valor) VALUES ('hk_movimientos', 'F2')")
            cursor.execute("INSERT OR IGNORE INTO config (clave, valor) VALUES ('hk_reportes', 'F3')")
            cursor.execute("INSERT OR IGNORE INTO config (clave, valor) VALUES ('hk_inventory', 'F4')")
            cursor.execute("INSERT OR IGNORE INTO config (clave, valor) VALUES ('hk_checkout', 'F5')")
            
            conn.commit()

    # --- GETTERS Y SETTERS ---
    # --- TASAS (BCV y USDT) ---
    def get_tasa(self):
        """Legacy: retorna la tasa principal usada por las operaciones históricas (USDT).
        Para nueva funcionalidad use get_tasa_usdt()/get_tasa_bcv() explícitamente."""
        return self.get_tasa_usdt()

    def set_tasa(self, nueva_tasa):
        """Legacy: alias para setear la tasa USDT (compatibilidad)."""
        return self.set_tasa_usdt(nueva_tasa)

    def get_tasa_bcv(self):
        with self.get_connection() as conn:
            val = conn.cursor().execute("SELECT valor FROM config WHERE clave='tasa_bcv'").fetchone()
            return float(val['valor']) if val else 60.0

    def set_tasa_bcv(self, nueva_tasa):
        with self.get_connection() as conn:
            conn.cursor().execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('tasa_bcv', ?)", (str(nueva_tasa),))
            conn.commit()

    def get_tasa_usdt(self):
        with self.get_connection() as conn:
            val = conn.cursor().execute("SELECT valor FROM config WHERE clave='tasa_usdt'").fetchone()
            return float(val['valor']) if val else 60.0

    def set_tasa_usdt(self, nueva_tasa):
        with self.get_connection() as conn:
            conn.cursor().execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('tasa_usdt', ?)", (str(nueva_tasa),))
            conn.commit()

    def get_tasa_mode(self):
        """Devuelve 'api' o 'manual' (fuente de la tasa USDT)."""
        with self.get_connection() as conn:
            val = conn.cursor().execute("SELECT valor FROM config WHERE clave='tasa_mode'").fetchone()
            return (val['valor'] if val else 'api')

    def set_tasa_mode(self, mode: str):
        with self.get_connection() as conn:
            conn.cursor().execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('tasa_mode', ?)", (mode,))
            conn.commit()

    def get_config(self, clave, default=""):
        with self.get_connection() as conn:
            val = conn.cursor().execute("SELECT valor FROM config WHERE clave=?", (clave,)).fetchone()
            return val['valor'] if val else default

    def set_config(self, clave, valor):
        with self.get_connection() as conn:
            conn.cursor().execute("INSERT OR REPLACE INTO config (clave, valor) VALUES (?, ?)", (clave, str(valor)))
            conn.commit()
    def update_tasa_bcv_from_api(self):
        """Actualiza la tasa BCV desde la API de cambio (USD->VES)."""
        try:
            er = ExchangeRates()
            rate = er.get_rate('USD', 'VES')
            self.set_tasa_bcv(rate)
            return rate
        except Exception as e:
            logging.warning("Failed to update BCV rate: %s", e)
            return self.get_tasa_bcv()

    def update_tasa_usdt_from_api(self):
        """Actualiza la tasa USDT (intenta usar USDT->VES, cae a USD->VES si no disponible)."""
        try:
            er = ExchangeRates()
            try:
                rate = er.get_rate('USDT', 'VES')
            except Exception:
                rate = er.get_rate('USD', 'VES')
            self.set_tasa_usdt(rate)
            return rate
        except Exception as e:
            logging.warning("Failed to update USDT rate: %s", e)
            return self.get_tasa_usdt()

    def update_tasa_from_api(self, base='USD', target='VES'):
        """Compatibilidad: por defecto actualiza la tasa USDT (legacy)."""
        return self.update_tasa_usdt_from_api()

    # --- OPERACIONES DE NEGOCIO ---
    def add_transaction(self, desc, usdt, ves, cat, tipo):
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self.get_connection() as conn:
            conn.cursor().execute(
                "INSERT INTO transacciones (fecha, descripcion, monto_usdt, monto_ves, categoria, tipo) VALUES (?,?,?,?,?,?)",
                (fecha, desc, usdt, ves, cat, tipo)
            )

    def add_pendiente(self, cliente, monto, desc):
        fecha = datetime.now().strftime("%Y-%m-%d")
        with self.get_connection() as conn:
            conn.cursor().execute(
                "INSERT INTO pendientes (cliente, monto_usdt, fecha, descripcion) VALUES (?,?,?,?)",
                (cliente, monto, fecha, desc)
            )

    def marcar_pendiente_pagado(self, p_id):
        """Marca una deuda como pagada en la DB."""
        with self.get_connection() as conn:
            conn.cursor().execute("UPDATE pendientes SET estado='PAGADO' WHERE id=?", (p_id,))

    def add_partial_payment(self, pendiente_id, monto, metodo=None, nota=None):
        """Registra un pago parcial: inserta en pagos_parciales, actualiza monto_pagado y marca PAGADO si corresponde.
        Retorna el monto aplicado (por si hay validaciones externas)."""
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self.get_connection() as conn:
            cur = conn.cursor()
            # Obtener deuda actual
            row = cur.execute("SELECT monto_usdt, monto_pagado, estado FROM pendientes WHERE id=?", (pendiente_id,)).fetchone()
            if not row:
                raise ValueError("Pendiente no encontrado")
            monto_total = float(row['monto_usdt'])
            pagado = float(row['monto_pagado']) if row['monto_pagado'] is not None else 0.0
            restante = monto_total - pagado
            monto = float(monto)
            if monto <= 0 or monto > restante:
                raise ValueError("Monto inválido para pago parcial")
            # Insert pago parcial
            cur.execute("INSERT INTO pagos_parciales (pendiente_id, monto_usdt, fecha, metodo, nota) VALUES (?,?,?,?,?)",
                        (pendiente_id, monto, fecha, metodo or '', nota or ''))
            # Actualizar monto_pagado
            cur.execute("UPDATE pendientes SET monto_pagado = monto_pagado + ? WHERE id=?", (monto, pendiente_id))
            # Si se pagó por completo marcar PAGADO
            if pagado + monto >= monto_total:
                cur.execute("UPDATE pendientes SET estado='PAGADO' WHERE id=?", (pendiente_id,))
            conn.commit()
            return monto

    def get_payments_for_pendiente(self, pendiente_id):
        with self.get_connection() as conn:
            rows = conn.cursor().execute("SELECT * FROM pagos_parciales WHERE pendiente_id=? ORDER BY id DESC", (pendiente_id,)).fetchall()
            return rows

    def get_ventas(self):
        """Retorna todas las ventas junto con el nombre del cliente (si existe)."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            rows = cur.execute(
                "SELECT v.id, v.fecha, c.nombre AS cliente, v.total_usd, v.total_ves, v.metodo_pago "
                "FROM ventas v LEFT JOIN clientes c ON v.cliente_id = c.id "
                "ORDER BY v.id DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    # --- RECORDATORIOS / NOTIFICACIONES ---
    def add_reminder(self, title, message, run_at_iso, repeat='once', enabled=1):
        created = datetime.now().isoformat()
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO reminders (title, message, run_at, repeat, enabled, created_at) VALUES (?,?,?,?,?,?)",
                        (title, message, run_at_iso, repeat, enabled, created))
            conn.commit()
            return cur.lastrowid

    def get_upcoming_reminders(self):
        with self.get_connection() as conn:
            rows = conn.cursor().execute("SELECT * FROM reminders WHERE enabled=1 ORDER BY run_at").fetchall()
            return rows

    def delete_reminder(self, reminder_id):
        with self.get_connection() as conn:
            conn.cursor().execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
            conn.commit()

    def update_tasa_from_api(self, base='USD', target='VES'):
        """Consulta API y actualiza la tasa almacenada en config."""
        try:
            er = ExchangeRates()
            rate = er.get_rate(base, target)
            self.set_tasa(rate)
            return rate
        except Exception as e:
            logging.warning("Exchange sync failed: %s", e)
            return self.get_tasa()

    # --- TELEGRAM CONFIG ---
    def get_telegram_config(self):
        with self.get_connection() as conn:
            cur = conn.cursor()
            token = cur.execute("SELECT valor FROM config WHERE clave='telegram_token'").fetchone()
            chat = cur.execute("SELECT valor FROM config WHERE clave='telegram_chat_id'").fetchone()
            return (token['valor'] if token else '', chat['valor'] if chat else '')

    def set_telegram_config(self, token, chat_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('telegram_token', ?)", (token,))
            cur.execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('telegram_chat_id', ?)", (chat_id,))
            conn.commit()

    # --- INVENTARIO ---
    def add_product(self, codigo, nombre, descripcion, costo, precio, stock, categoria):
        with self.get_connection() as conn:
            conn.cursor().execute("INSERT INTO inventario (codigo, nombre, descripcion, costo, precio, stock, categoria) VALUES (?,?,?,?,?,?,?)",
                                  (codigo, nombre, descripcion, costo, precio, stock, categoria))
            conn.commit()

    def update_product(self, pid, codigo, nombre, descripcion, costo, precio, stock, categoria):
        with self.get_connection() as conn:
            conn.cursor().execute("UPDATE inventario SET codigo=?, nombre=?, descripcion=?, costo=?, precio=?, stock=?, categoria=? WHERE id=?",
                                  (codigo, nombre, descripcion, costo, precio, stock, categoria, pid))
            conn.commit()

    def delete_product(self, pid):
         with self.get_connection() as conn:
            conn.cursor().execute("DELETE FROM inventario WHERE id=?", (pid,))
            conn.commit()

    def get_inventory(self):
        with self.get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM inventario", conn)

    # --- SERVICIOS ---
    def add_service(self, codigo, nombre, descripcion, precio, categoria="Servicios"):
        with self.get_connection() as conn:
            conn.cursor().execute("INSERT INTO servicios (codigo, nombre, descripcion, precio, categoria) VALUES (?,?,?,?,?)",
                                  (codigo, nombre, descripcion, precio, categoria))
            conn.commit()

    def update_service(self, sid, codigo, nombre, descripcion, precio, categoria):
        with self.get_connection() as conn:
            conn.cursor().execute("UPDATE servicios SET codigo=?, nombre=?, descripcion=?, precio=?, categoria=? WHERE id=?",
                                  (codigo, nombre, descripcion, precio, categoria, sid))
            conn.commit()

    def delete_service(self, sid):
        with self.get_connection() as conn:
            conn.cursor().execute("DELETE FROM servicios WHERE id=?", (sid,))
            conn.commit()

    def get_services(self):
        with self.get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM servicios", conn)

    # --- CLIENTES ---
    def add_cliente(self, nombre, cedula, telefono, direccion):
        with self.get_connection() as conn:
            conn.cursor().execute(
                "INSERT INTO clientes (nombre, cedula, telefono, direccion) VALUES (?,?,?,?)",
                (nombre, cedula, telefono, direccion)
            )
            conn.commit()

    def get_clientes(self):
        with self.get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM clientes", conn)

    # --- VENTAS / POS ---
    def add_venta(self, cliente_id, total_usd, total_ves, metodo_pago, items):
        """
        Registra una venta completa.
        items: lista de diccionarios [{'id': producto_id, 'cantidad': q, 'precio': p}]
        """
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
        tasa = self.get_tasa()
        with self.get_connection() as conn:
            cur = conn.cursor()
            try:
                # 1. Insertar Cabecera de Venta
                cur.execute(
                    "INSERT INTO ventas (fecha, cliente_id, total_usd, total_ves, metodo_pago, tasa_momento) VALUES (?,?,?,?,?,?)",
                    (fecha, cliente_id, total_usd, total_ves, metodo_pago, tasa)
                )
                venta_id = cur.lastrowid

                # 2. Insertar Detalles y Actualizar Stock
                for item in items:
                    precio_final = item['precio'] * (1 - item.get('descuento', 0) / 100)
                    if item.get('is_service'):
                        cur.execute(
                            "INSERT INTO detalle_ventas (venta_id, servicio_id, cantidad, precio_unitario) VALUES (?,?,?,?)",
                            (venta_id, item['id'], item['cantidad'], precio_final)
                        )
                    else:
                        cur.execute(
                            "INSERT INTO detalle_ventas (venta_id, producto_id, cantidad, precio_unitario) VALUES (?,?,?,?)",
                            (venta_id, item['id'], item['cantidad'], precio_final)
                        )
                        # Descontar stock
                        cur.execute("UPDATE inventario SET stock = stock - ? WHERE id = ?", (item['cantidad'], item['id']))
                
                # 3. Registrar como transacción de ingreso
                desc_venta = f"Venta #{venta_id}"
                cur.execute(
                    "INSERT INTO transacciones (fecha, descripcion, monto_usdt, monto_ves, categoria, tipo) VALUES (?,?,?,?,?,?)",
                    (fecha, desc_venta, total_usd, total_ves, "Ventas", "INGRESO")
                )
                
                conn.commit()
                return venta_id
            except Exception as e:
                conn.rollback()
                raise e

    # --- FTS / Índice de búsqueda persistente ---
    def rebuild_search_index(self):
        """Reconstruye la tabla FTS con datos actuales de transacciones, pendientes y metas."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            try:
                # Vaciar tabla FTS si existe
                cur.execute("DELETE FROM search_fts")
            except Exception:
                # Podría no existir FTS (SQLite sin fts5)
                return 0

            # Insertar transacciones
            rows = cur.execute("SELECT id, descripcion FROM transacciones").fetchall()
            for r in rows:
                cur.execute("INSERT INTO search_fts (name, description, type, ref) VALUES (?,?,?,?)",
                            (str(r['id']), r['descripcion'], 'transaction', f"tx_{r['id']}"))
            # Insertar pendientes
            rows = cur.execute("SELECT id, cliente, descripcion FROM pendientes").fetchall()
            for r in rows:
                cur.execute("INSERT INTO search_fts (name, description, type, ref) VALUES (?,?,?,?)",
                            (r['cliente'], r['descripcion'], 'pendiente', f"pend_{r['id']}"))
            # (ANTES) Insertar metas en índice FTS - bloque eliminado ya que
            # la funcionalidad de metas/ahorro fue removida.
            conn.commit()
            return 1

    def autocomplete_suggestions(self, prefix: str, limit: int = 10):
        """Devuelve sugerencias rápidas (strings) para autocompletar usando FTS (si disponible)."""
        if not prefix:
            return []
        with self.get_connection() as conn:
            cur = conn.cursor()
            try:
                q = f"{prefix}*"
                rows = cur.execute("SELECT name FROM search_fts WHERE name MATCH ? LIMIT ?", (q, limit)).fetchall()
                return [r['name'] for r in rows]
            except Exception:
                return []

    def search_fts(self, query: str, limit: int = 100):
        """Busca en el índice FTS y devuelve filas con ref, name y type."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            try:
                q = f"{query}*"
                rows = cur.execute("SELECT ref, name, type FROM search_fts WHERE search_fts MATCH ? LIMIT ?", (q, limit)).fetchall()
                return [dict(r) for r in rows]
            except Exception:
                return []

    def get_balance_summary(self):
        """Calcula ingresos, gastos y balance general.

        La regla 50/30/20 y categorías de ahorro ya no se usan en el
        dashboard; este método sólo devuelve montos globales.
        """
        df = pd.read_sql_query("SELECT * FROM transacciones", self.get_connection())
        
        if df.empty:
            return {"ingreso": 0, "gasto": 0, "balance": 0}

        ingreso_total = df[df['tipo'] == 'INGRESO']['monto_usdt'].sum()
        gastos = df[df['tipo'] == 'GASTO']
        gasto_total = gastos['monto_usdt'].sum()

        return {
            "ingreso": ingreso_total,
            "gasto": gasto_total,
            "balance": ingreso_total - gasto_total
        }

    def get_recent_actions(self, limit=5):
        """Devuelve las últimas `limit` transacciones ordenadas por id descendente.

        Cada fila es un dict con campos fecha, descripcion, monto_usdt, categoria y tipo.
        """
        with self.get_connection() as conn:
            rows = conn.cursor().execute(
                "SELECT fecha, descripcion, monto_usdt, categoria, tipo FROM transacciones "
                "ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_dataframe(self, query="SELECT * FROM transacciones ORDER BY id DESC"):
        return pd.read_sql_query(query, self.get_connection())

    # Autenticación de usuarios eliminada.

    # --- TRANSACCIONES: actualizar / eliminar / importar ---
    def update_transaction(self, tx_id, desc, usdt, ves, cat, tipo):
        with self.get_connection() as conn:
            conn.cursor().execute("UPDATE transacciones SET descripcion=?, monto_usdt=?, monto_ves=?, categoria=?, tipo=? WHERE id=?",
                                  (desc, usdt, ves, cat, tipo, tx_id))
            conn.commit()

    def delete_transaction(self, tx_id):
        with self.get_connection() as conn:
            conn.cursor().execute("DELETE FROM transacciones WHERE id=?", (tx_id,))
            conn.commit()

    def import_transactions_from_df(self, df):
        """Importa filas desde un DataFrame. Columnas esperadas: descripcion, monto_usdt, monto_ves (opcional), categoria (opcional), tipo (opcional), fecha (opcional)."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            for _, row in df.iterrows():
                try:
                    fecha = row.get('fecha') if 'fecha' in row.index else datetime.now().strftime("%Y-%m-%d %H:%M")
                    desc = row['descripcion']
                    usdt = float(row['monto_usdt'])
                    ves = float(row['monto_ves']) if 'monto_ves' in row.index and not pd.isna(row['monto_ves']) else usdt * self.get_tasa()
                    cat = row['categoria'] if 'categoria' in row.index and not pd.isna(row['categoria']) else 'Otros'
                    tipo = row['tipo'] if 'tipo' in row.index and not pd.isna(row['tipo']) else ('INGRESO' if usdt >= 0 else 'GASTO')
                    cur.execute("INSERT INTO transacciones (fecha, descripcion, monto_usdt, monto_ves, categoria, tipo) VALUES (?,?,?,?,?,?)",
                                (fecha, desc, usdt, ves, cat, tipo))
                except Exception:
                    # Ignorar filas inválidas
                    continue
            conn.commit()

    # --- EXPORT / IMPORT DE BASE DE DATOS (JSON / SQLite) ---
    def export_db_to_dict(self):
        result = {'meta': {'db_name': self.db_name, 'exported_at': datetime.now().isoformat()}, 'tables': {}}
        with self.get_connection() as conn:
            cur = conn.cursor()
            tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
            for t in tables:
                rows = cur.execute(f"SELECT * FROM {t}").fetchall()
                result['tables'][t] = [dict(r) for r in rows]
        return result

    def export_db_to_json(self, path):
        """Exporta todas las tablas a un archivo JSON. """
        d = self.export_db_to_dict()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=2, default=str)

    def import_db_from_json(self, path):
        """Importa un dump JSON: usará INSERT OR REPLACE para no duplicar ids.
        Retorna un dict con recuentos por tabla."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        counts = {}
        with self.get_connection() as conn:
            cur = conn.cursor()
            for table, rows in data.get('tables', {}).items():
                # Verificar columnas existentes
                existing_cols = [c[1] for c in cur.execute(f"PRAGMA table_info({table})").fetchall()]
                if not existing_cols:
                    # Tabla no existe; saltar
                    continue
                inserted = 0
                for r in rows:
                    vals = {k: r.get(k) for k in existing_cols if k in r}
                    if not vals:
                        continue
                    cols = ",".join(vals.keys())
                    placeholders = ",".join(["?" for _ in vals])
                    cur.execute(f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})", tuple(vals.values()))
                    inserted += 1
                counts[table] = inserted
            conn.commit()
        return counts

    def import_from_sqlite_file(self, other_db_path):
        """Importa datos desde otro archivo SQLite: copia filas de tablas existentes usando INSERT OR REPLACE.
        Retorna un dict con recuentos por tabla."""
        if not os.path.exists(other_db_path):
            raise ValueError("Archivo no encontrado")
        counts = {}
        with sqlite3.connect(other_db_path) as other_conn:
            ocur = other_conn.cursor()
            tables = [r[0] for r in ocur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
            with self.get_connection() as conn:
                cur = conn.cursor()
                for t in tables:
                    # Obtener filas del DB antiguo
                    try:
                        rows = ocur.execute(f"SELECT * FROM {t}").fetchall()
                    except Exception:
                        continue
                    if not rows:
                        continue
                    cols_other = [d[0] for d in ocur.description]
                    existing_cols = [c[1] for c in cur.execute(f"PRAGMA table_info({t})").fetchall()]
                    if not existing_cols:
                        continue
                    inserted = 0
                    for row in rows:
                        rowdict = dict(zip(cols_other, row))
                        vals = {k: rowdict.get(k) for k in existing_cols if k in rowdict}
                        if not vals:
                            continue
                        cols = ",".join(vals.keys())
                        placeholders = ",".join(["?" for _ in vals])
                        cur.execute(f"INSERT OR REPLACE INTO {t} ({cols}) VALUES ({placeholders})", tuple(vals.values()))
                        inserted += 1
                    counts[t] = inserted
                conn.commit()
        return counts

    def get_top_selling_products(self, limit=5):
        query = """
        SELECT nombre, SUM(cantidad) as total_vendido FROM (
            SELECT i.nombre, d.cantidad 
            FROM detalle_ventas d
            JOIN inventario i ON d.producto_id = i.id
            UNION ALL
            SELECT s.nombre, d.cantidad
            FROM detalle_ventas d
            JOIN servicios s ON d.servicio_id = s.id
        )
        GROUP BY nombre
        ORDER BY total_vendido DESC
        LIMIT ?
        """
        with self.get_connection() as conn:
            return pd.read_sql_query(query, conn, params=(limit,))

    def get_weekly_sales(self):
        """Retorna las ventas de los últimos 7 días agrupadas por fecha."""
        query = """
        SELECT date(fecha) as dia, SUM(total_usd) as total
        FROM ventas
        WHERE fecha >= date('now', '-7 days')
        GROUP BY dia
        ORDER BY dia ASC
        """
        with self.get_connection() as conn:
            return pd.read_sql_query(query, conn)

    def get_category_sales(self):
        """Retorna la distribución de ventas por categoría de producto/servicio."""
        query = """
        SELECT cat, SUM(subtotal) as total FROM (
            SELECT i.categoria as cat, (d.cantidad * d.precio_unitario) as subtotal
            FROM detalle_ventas d JOIN inventario i ON d.producto_id = i.id
            UNION ALL
            SELECT s.categoria as cat, (d.cantidad * d.precio_unitario) as subtotal
            FROM detalle_ventas d JOIN servicios s ON d.servicio_id = s.id
        ) GROUP BY cat
        """
        with self.get_connection() as conn:
            return pd.read_sql_query(query, conn)

    def get_venta_detalle(self, venta_id):
        """Retorna el detalle de productos/servicios de una venta."""
        query = """
        SELECT d.cantidad, d.precio_unitario, 
               COALESCE(i.nombre, s.nombre) as nombre,
               CASE WHEN i.id IS NOT NULL THEN 'Producto' ELSE 'Servicio' END as tipo
        FROM detalle_ventas d
        LEFT JOIN inventario i ON d.producto_id = i.id
        LEFT JOIN servicios s ON d.servicio_id = s.id
        WHERE d.venta_id = ?
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            rows = cur.execute(query, (venta_id,)).fetchall()
            return [dict(r) for r in rows]

# =============================================================================
# WIDGET: GRÁFICO DONUT (Matplotlib embebido)
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
            ax.tick_params(colors=self.text_color, labelsize=8)
            for spine in ax.spines.values():
                spine.set_color(self.border_color())
            
            # Formatear etiquetas de X para que no se amontonen
            self.figure.autofmt_xdate(rotation=45)
            self.figure.tight_layout()
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
            self.figure.tight_layout()
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
            ax.tick_params(colors=self.text_color, labelsize=8)
            for spine in ax.spines.values():
                spine.set_color(self.border_color())
            plt.xticks(rotation=45, ha='right', color=self.text_color)
            self.figure.tight_layout()
        self.canvas.draw()

    def border_color(self):
        return '#334155' if self.theme_mode == 'dark' else '#e2e8f0'

# =============================================================================
# DIÁLOGO: TRANSACCIÓN CON CALCULADORA INTELIGENTE
# =============================================================================
class TransactionDialog(QDialog):
    def __init__(self, parent=None, db_manager=None, tx_id=None):
        super().__init__(parent)
        self.db = db_manager
        self.tx_id = tx_id
        self.setWindowTitle("Registrar Movimiento" if not tx_id else "Editar Movimiento")
        self.setFixedSize(450, 450)
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
        lbl_tasa.setStyleSheet("color: #f8f8f2; background: #44475a; padding: 5px; border-radius: 4px; border: 1px solid #6272a4;")
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
class PaymentHistoryDialog(QDialog):
    def __init__(self, payments, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Historial de Pagos")
        self.setFixedSize(480, 320)
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
class SaleDetailsDialog(QDialog):
    def __init__(self, venta_id, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.venta_id = venta_id
        self.setWindowTitle(f"Detalle de Venta #{venta_id}")
        self.setFixedSize(600, 450)
        self.setup_ui()
        self.load_details()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        header = QLabel(f"📦 <b>Productos y Servicios - Venta #{self.venta_id}</b>")
        header.setObjectName("h2")
        layout.addWidget(header)
        
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
class ClientDialog(QDialog):
    def __init__(self, parent=None, db_manager=None, cid=None):
        super().__init__(parent)
        self.db = db_manager
        self.cid = cid
        self.setWindowTitle("Nuevo Cliente" if not cid else "Editar Cliente")
        self.setFixedSize(400, 350)
        self.setup_ui()
        if self.cid:
            self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.txt_nombre = QLineEdit()
        self.txt_cedula = QLineEdit()
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
class ServiceDialog(QDialog):
    def __init__(self, parent=None, db_manager=None, sid=None):
        super().__init__(parent)
        self.db = db_manager
        self.sid = sid
        self.setWindowTitle("Servicio" if not sid else "Editar Servicio")
        self.setFixedSize(400, 400)
        self.setup_ui()
        if self.sid:
            self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.txt_codigo = QLineEdit()
        self.txt_nombre = QLineEdit()
        self.txt_desc = QLineEdit()
        self.txt_precio = QLineEdit()
        self.cmb_cat = QComboBox()
        self.cmb_cat.addItems(["General", "Servicios Digitales", "Mantenimiento", "Asesoría"])
        self.cmb_cat.setEditable(True)
        
        form.addRow("Código:", self.txt_codigo)
        form.addRow("Nombre:", self.txt_nombre)
        form.addRow("Descripción:", self.txt_desc)
        form.addRow("Precio ($):", self.txt_precio)
        form.addRow("Categoría:", self.cmb_cat)
        
        layout.addLayout(form)
        
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

    def save(self):
        try:
            codigo = self.txt_codigo.text()
            nombre = self.txt_nombre.text()
            precio = float(self.txt_precio.text() or 0)
            if not nombre: raise ValueError("Nombre es obligatorio")
            
            if self.sid:
                self.db.update_service(self.sid, codigo, nombre, self.txt_desc.text(), precio, self.cmb_cat.currentText())
            else:
                self.db.add_service(codigo, nombre, self.txt_desc.text(), precio, self.cmb_cat.currentText())
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

# =============================================================================
# DIALOG: PRODUCTO (INVENTARIO)
# =============================================================================
class ProductDialog(QDialog):
    def __init__(self, parent=None, db_manager=None, pid=None):
        super().__init__(parent)
        self.db = db_manager
        self.pid = pid
        self.setWindowTitle("Producto" if not pid else "Editar Producto")
        self.setFixedSize(400, 500)
        self.setup_ui()
        if self.pid:
            self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.txt_codigo = QLineEdit()
        self.txt_nombre = QLineEdit()
        self.txt_desc = QLineEdit()
        self.txt_costo = QLineEdit()
        self.txt_precio = QLineEdit()
        self.txt_stock = QLineEdit()
        self.cmb_cat = QComboBox()
        self.cmb_cat.addItems(["General", "Electrónica", "Accesorios", "Servicios"])
        self.cmb_cat.setEditable(True)
        
        form.addRow("Código:", self.txt_codigo)
        form.addRow("Nombre:", self.txt_nombre)
        form.addRow("Descripción:", self.txt_desc)
        form.addRow("Costo ($):", self.txt_costo)
        form.addRow("Precio ($):", self.txt_precio)
        form.addRow("Stock:", self.txt_stock)
        form.addRow("Categoría:", self.cmb_cat)
        
        layout.addLayout(form)
        
        btns = QHBoxLayout()
        btn_save = QPushButton("Guardar"); btn_save.setObjectName("btn_success"); btn_save.clicked.connect(self.save)
        btn_cancel = QPushButton("Cancelar"); btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel); btns.addWidget(btn_save)
        layout.addLayout(btns)

    def load_data(self):
        row = self.db.get_connection().cursor().execute("SELECT * FROM inventario WHERE id=?", (self.pid,)).fetchone()
        if row:
            self.txt_codigo.setText(row['codigo'])
            self.txt_nombre.setText(row['nombre'])
            self.txt_desc.setText(row['descripcion'])
            self.txt_costo.setText(str(row['costo']))
            self.txt_precio.setText(str(row['precio']))
            self.txt_stock.setText(str(row['stock']))
            self.cmb_cat.setCurrentText(row['categoria'])

    def save(self):
        try:
            codigo = self.txt_codigo.text()
            nombre = self.txt_nombre.text()
            desc = self.txt_desc.text()
            costo = float(self.txt_costo.text() or 0)
            precio = float(self.txt_precio.text() or 0)
            stock = int(self.txt_stock.text() or 0)
            cat = self.cmb_cat.currentText()
            
            if not codigo or not nombre:
                QMessageBox.warning(self, "Error", "Código y Nombre son obligatorios")
                return

            if self.pid:
                self.db.update_product(self.pid, codigo, nombre, desc, costo, precio, stock, cat)
            else:
                self.db.add_product(codigo, nombre, desc, costo, precio, stock, cat)
            
            # Alerta inmediata si se guardó con stock 0
            if stock <= 0:
                QMessageBox.warning(self, "Agotado", f"El producto '{nombre}' se ha guardado con stock 0.\nRecuerde realizar un re-stock.")
                
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al guardar: {e}")

# =============================================================================
# VENTANA PRINCIPAL (MAIN WINDOW)
# =============================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        # Login eliminado (no se solicita usuario)
        self.setWindowTitle("Sistema de Ventas y Gestión Empresarial")
        self.resize(1280, 800)
        self.setStyleSheet(STYLESHEET)
        
        # Widget Central y Layout Principal
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)
        
        # 0. Contenedor de la derecha (Navbar + Contenido)
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0,0,0,0)
        right_layout.setSpacing(0)
        
        # NAVBAR (Top Bar)
        navbar = QFrame()
        navbar.setFixedHeight(60)
        navbar.setObjectName("Navbar")
        navbar.setContentsMargins(15, 8, 15, 8)
        nav_layout = QHBoxLayout(navbar)
        
        lbl_brand = QLabel("💼 <b>Sistema de Ventas y Gestión Empresarial</b>")
        lbl_brand.setObjectName("h3")
        
        self.nav_search = QLineEdit()
        self.nav_search.setObjectName("NavSearch")
        self.nav_search.setPlaceholderText("🔍 Buscar en todo el sistema... (Ctrl+K)")
        self.nav_search.setMinimumWidth(350)
        self.nav_search.setMaximumWidth(500)
        self.nav_search.setFixedHeight(38)
        
        lbl_status = QLabel("🟢 Conectado")
        lbl_status.setStyleSheet("color: #10b981; font-weight: bold; margin-right: 20px;")

        # Botón para alternar tema (día / noche).
        self.btn_theme = QPushButton()
        self.btn_theme.setIcon(qta.icon('fa5s.sun', color='#f59e0b'))
        self.btn_theme.setObjectName("btn_theme")
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.setToolTip("Alternar modo día / noche")
        self.btn_theme.clicked.connect(self.toggle_theme)

        nav_layout.addWidget(lbl_brand)
        nav_layout.addStretch()
        nav_layout.addWidget(self.nav_search)
        nav_layout.addStretch()
        nav_layout.addWidget(self.btn_theme)
        nav_layout.addWidget(lbl_status)

        
        right_layout.addWidget(navbar)

        
        # 1. ÁREA DE CONTENIDO (Stacked Widget) - Create first
        self.pages = QStackedWidget()
        self.page_dashboard = self.setup_dashboard_page()
        self.page_pos = self.setup_pos_page() # NUEVA
        self.page_movimientos = self.setup_movimientos_page()
        self.page_pendientes = self.setup_pendientes_page()
        self.page_inventory = self.setup_inventory_page()
        self.page_services = self.setup_services_page()
        self.page_clients = self.setup_clients_page() # NUEVA
        self.page_reports = self.setup_reports_page()
        self.page_calculadora = self.setup_calculator_page()
        # Metas/Ahorro removido
        self.page_reminders = self.setup_reminders_page()
        self.page_config = self.setup_config_page()
        
        self.pages.addWidget(self.page_dashboard)
        self.pages.addWidget(self.page_pos)
        self.pages.addWidget(self.page_movimientos)
        self.pages.addWidget(self.page_pendientes)
        self.pages.addWidget(self.page_inventory)
        self.pages.addWidget(self.page_services)
        self.pages.addWidget(self.page_clients)
        self.pages.addWidget(self.page_reports)
        self.pages.addWidget(self.page_calculadora)
        # no se añade page_metas
        self.pages.addWidget(self.page_reminders)
        self.pages.addWidget(self.page_config)
        
        # 2. SIDEBAR (Navegación Izquierda) - Create after pages
        self.sidebar = self.create_sidebar()
        self.sidebar.setFixedWidth(240)
        
        # Agregar contenido al right_layout
        right_layout.addWidget(self.pages)
        
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(right_container)

        # Configurar Hotkeys Globales
        self.setup_hotkeys()

        
        # Background services: exchange sync, reminders, global search
        self.setup_background_tasks()
        
        # Conectar Buscador Navbar
        self.nav_search.returnPressed.connect(self.open_global_search_from_nav)
        
        self.refresh_ui()

    # -----------------------------
    # Tema e icon helper
    # -----------------------------
    def load_icon(self, name: str) -> QIcon:
        """Busca el icono en assets/icons/{name}.png y devuelve QIcon, o vacío si no existe."""
        base_dir = os.path.dirname(__file__)
        icon_path = os.path.join(base_dir, 'assets', 'icons', f"{name}.png")
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        return QIcon()

    def toggle_theme(self):
        """Alterna entre 'dark' y 'light' aplicando el stylesheet y actualizando la paleta."""
        app = QApplication.instance()
        current = getattr(self, 'theme_mode', 'light')
        new_mode = 'dark' if current == 'light' else 'light'
        self.theme_mode = new_mode
        try: app.setStyleSheet(get_stylesheet(new_mode))
        except Exception: pass
        
        palette = app.palette()
        if new_mode == 'dark':
            palette.setColor(QPalette.Window, QColor("#1e293b"))
            palette.setColor(QPalette.Base, QColor("#0f172a"))
            palette.setColor(QPalette.Text, QColor("#f8fafc"))
            palette.setColor(QPalette.WindowText, QColor("#f8fafc"))
            palette.setColor(QPalette.Button, QColor("#334155"))
            palette.setColor(QPalette.ButtonText, QColor("#f8fafc"))
            palette.setColor(QPalette.Highlight, QColor("#2563eb"))
            palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        else:
            palette.setColor(QPalette.Window, QColor("#f8fafc"))
            palette.setColor(QPalette.Base, QColor("#ffffff"))
            palette.setColor(QPalette.Text, QColor("#1e293b"))
            palette.setColor(QPalette.WindowText, QColor("#1e293b"))
            palette.setColor(QPalette.Button, QColor("#ffffff"))
            palette.setColor(QPalette.ButtonText, QColor("#1e293b"))
            palette.setColor(QPalette.Highlight, QColor("#2563eb"))
            palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        try: app.setPalette(palette)
        except Exception: pass
            
        if new_mode == "light":
            self.btn_theme.setIcon(qta.icon('fa5s.sun', color='#f59e0b'))
        else:
            self.btn_theme.setIcon(qta.icon('fa5s.moon', color='#cbd5e1'))

        
        # Actualizar temas de todos los gráficos del dashboard
        for c in ['chart_cat', 'chart_weekly', 'chart_top', 'chart_expenses']:
            if hasattr(self, c): getattr(self, c).set_theme(new_mode)
            
        if hasattr(self, 'rep_chart_donut'): self.rep_chart_donut.set_theme(new_mode)
        if hasattr(self, 'rep_chart_bar'): self.rep_chart_bar.set_theme(new_mode)
        self.refresh_ui()

    def setup_hotkeys(self):
        """Configura los atajos de teclado según la configuración en BD."""
        # Limpiar atajos anteriores si existieran
        if hasattr(self, 'shortcuts'):
            for s in self.shortcuts: s.setEnabled(False)
        
        self.shortcuts = []
        
        mapping = {
            'hk_pos': lambda: self.switch_page(1),
            'hk_movimientos': lambda: self.switch_page(2),
            'hk_reportes': lambda: self.switch_page(7),
            'hk_inventory': lambda: self.switch_page(4)
        }
        
        for key, action in mapping.items():
            hk = self.db.get_config(key)
            if hk:
                s = QShortcut(QKeySequence(hk), self)
                s.activated.connect(action)
                self.shortcuts.append(s)
        
        # Atajo especial para checkout en POS
        hk_checkout = self.db.get_config('hk_checkout', 'F5')
        s_checkout = QShortcut(QKeySequence(hk_checkout), self)
        s_checkout.activated.connect(self.process_pos_sale)
        self.shortcuts.append(s_checkout)

    def create_sidebar(self):
        list_widget = QListWidget()
        list_widget.setObjectName("Sidebar")
        # Eliminar scroll bar para vista más limpia si caben los items
        list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        list_widget.addItems([
            "📊 Dashboard", 
            "🛒 Punto de Venta",
            "💸 Movimientos", 
            "⌛ Cuentas Pendientes",
            "📦 Inventario",
            "🛠️ Servicios",
            "👥 Clientes",
            "📈 Reportes", 
            "🧮 Calculadora",
            # "🎯 Metas Ahorro", eliminado
            "🔔 Notificaciones",
            "⚙️ Configuración"
        ])
        list_widget.currentRowChanged.connect(self.switch_page)
        list_widget.setCurrentRow(0)
        return list_widget

    def switch_page(self, index):
        """Cambia el QStackedWidget según la selección del Sidebar o Quick Actions."""
        if isinstance(index, int):
            self.pages.setCurrentIndex(index)
            if hasattr(self, 'sidebar'):
                self.sidebar.setCurrentRow(index)
        self.refresh_ui()




    # --- PÁGINAS ---

    def setup_dashboard_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(25)
        
        # 1. HEADER
        header = QHBoxLayout()
        header.addWidget(QLabel("<h1 id='h1'>Panel de Control</h1>"))
        header.addStretch()
        self.lbl_last_update = QLabel("Actualizado: --:--")
        self.lbl_last_update.setObjectName("subtitle")
        header.addWidget(self.lbl_last_update)
        layout.addLayout(header)

        # 2. KPI ROW (4 Cards)
        kpi_row = QHBoxLayout()
        self.kpi_ingresos = self.create_kpi_card("Ingresos Hoy", "#10b981", "value_success")
        self.kpi_gastos = self.create_kpi_card("Gastos Hoy", "#ef4444", "value_danger")
        self.kpi_ventas = self.create_kpi_card("Ventas Totales", "#3b82f6", "value_primary")
        self.kpi_debt = self.create_kpi_card("Cuentas x Cobrar", "#f59e0b", "value_warning")
        
        kpi_row.addWidget(self.kpi_ingresos)
        kpi_row.addWidget(self.kpi_gastos)
        kpi_row.addWidget(self.kpi_ventas)
        kpi_row.addWidget(self.kpi_debt)
        layout.addLayout(kpi_row)

        # 3. CHART GRID (2x2)
        grid_charts = QGridLayout()
        grid_charts.setSpacing(20)

        # Chart 1: Donut (Distribution)
        c1_frame = QFrame(); c1_frame.setObjectName("ContentPanel")
        c1_layout = QVBoxLayout(c1_frame)
        c1_layout.addWidget(QLabel("<h2 id='h2'>📊 Ventas por Categoría</h2>"))
        self.chart_cat = ChartWidget()
        c1_layout.addWidget(self.chart_cat)
        grid_charts.addWidget(c1_frame, 0, 0)

        # Chart 2: Line (Weekly Sales)
        c2_frame = QFrame(); c2_frame.setObjectName("ContentPanel")
        c2_layout = QVBoxLayout(c2_frame)
        c2_layout.addWidget(QLabel("<h2 id='h2'>📈 Ventas (Últimos 7 días)</h2>"))
        self.chart_weekly = ChartWidget()
        c2_layout.addWidget(self.chart_weekly)
        grid_charts.addWidget(c2_frame, 1, 0)

        # Chart 3: Horizontal Bar (Top Products)
        c3_frame = QFrame(); c3_frame.setObjectName("ContentPanel")
        c3_layout = QVBoxLayout(c3_frame)
        c3_layout.addWidget(QLabel("<h2 id='h2'>🏆 Top 5 Productos/Servicios</h2>"))
        self.chart_top = ChartWidget()
        c3_layout.addWidget(self.chart_top)
        grid_charts.addWidget(c3_frame, 0, 1)

        # Chart 4: Expenses Distribution
        c4_frame = QFrame(); c4_frame.setObjectName("ContentPanel")
        c4_layout = QVBoxLayout(c4_frame)
        c4_layout.addWidget(QLabel("<h2 id='h2'>💸 Distribución de Gastos</h2>"))
        self.chart_expenses = ChartWidget()
        c4_layout.addWidget(self.chart_expenses)
        grid_charts.addWidget(c4_frame, 1, 1)

        layout.addLayout(grid_charts, 3)

        # 4. BOTTOM SECTION: Recent Actions + Quick Actions
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(25)

        # Listado de acciones recientes
        recent_frame = QFrame(); recent_frame.setObjectName("ContentPanel")
        rl = QVBoxLayout(recent_frame)
        rl.addWidget(QLabel("<h2 id='h2'>🕒 Últimas Acciones</h2>"))
        self.recent_list = QListWidget()
        self.recent_list.setObjectName("RecentActionsList")
        self.recent_list.setFixedHeight(120)
        rl.addWidget(self.recent_list)
        bottom_layout.addWidget(recent_frame, 3)

        # Acciones rápidas (footer)
        qa_frame = QFrame(); qa_frame.setObjectName("ContentPanel")
        ql = QVBoxLayout(qa_frame)
        ql.addWidget(QLabel("<h2 id='h2'>⚡ Accesos Directos</h2>"))
        grid_qa = QGridLayout()
        grid_qa.setSpacing(8)
        
        qa_pos = QPushButton(" Nueva Venta")
        qa_pos.setIcon(qta.icon('fa5s.shopping-cart', color='#ffffff'))
        qa_pos.setObjectName("btn_success")
        qa_pos.setFixedHeight(40)
        qa_pos.clicked.connect(lambda: self.switch_page(1))
        
        qa_mov = QPushButton(" Movimiento")
        qa_mov.setIcon(qta.icon('fa5s.exchange-alt', color='#ffffff'))
        qa_mov.setObjectName("btn_primary")
        qa_mov.setFixedHeight(40)
        qa_mov.clicked.connect(self.open_transaction_dialog)
        
        grid_qa.addWidget(qa_pos, 0, 0)
        grid_qa.addWidget(qa_mov, 0, 1)
        
        ql.addLayout(grid_qa)
        bottom_layout.addWidget(qa_frame, 2)
        
        layout.addLayout(bottom_layout, 1)
        
        return page

    def create_kpi_card(self, title, color, val_obj_name="value"):
        card = QFrame(); card.setObjectName("StatCard")
        vbox = QVBoxLayout(card)
        lbl_t = QLabel(title.upper()); lbl_t.setObjectName("subtitle")
        lbl_v = QLabel("0.00 $"); lbl_v.setObjectName(val_obj_name)
        vbox.addWidget(lbl_t)
        vbox.addWidget(lbl_v)
        return card

    def setup_movimientos_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30,30,30,30)
        
        # Header y Controles
        top_bar = QHBoxLayout()
        btn_add = QPushButton("+ Registrar Movimiento")
        btn_add.setObjectName("btn_success")
        btn_add.clicked.connect(self.open_transaction_dialog)
        
        btn_import = QPushButton("Importar CSV")
        btn_import.clicked.connect(self.import_transactions_csv)
        btn_export_csv = QPushButton("Exportar CSV")
        btn_export_csv.clicked.connect(self.export_transactions_csv)
        btn_export_xlsx = QPushButton("Exportar Excel")
        btn_export_xlsx.clicked.connect(self.export_transactions_excel)
        btn_edit = QPushButton("Editar Seleccionado")
        btn_edit.clicked.connect(self.edit_selected_transaction)
        btn_delete = QPushButton("Eliminar Seleccionado")
        btn_delete.setObjectName("btn_danger")
        btn_delete.clicked.connect(self.delete_selected_transaction)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Buscar por descripción... (Ctrl+K para búsqueda global)")
        # Completer para autocompletar usando FTS
        self.search_model = QStringListModel()
        self.search_completer = QCompleter()
        self.search_completer.setModel(self.search_model)
        self.search_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.search_bar.setCompleter(self.search_completer)
        self.search_bar.textChanged.connect(self.update_search_suggestions)
        self.search_bar.returnPressed.connect(self.load_transactions_table)
        
        top_bar.addWidget(btn_add)
        top_bar.addWidget(btn_import)
        top_bar.addWidget(btn_export_csv)
        top_bar.addWidget(btn_export_xlsx)
        top_bar.addWidget(btn_edit)
        top_bar.addWidget(btn_delete)
        top_bar.addStretch()
        top_bar.addWidget(self.search_bar)
        
        layout.addLayout(top_bar)
        
        # Tabla
        self.table_mov = QTableWidget()
        self.table_mov.setColumnCount(7)
        self.table_mov.setHorizontalHeaderLabels(["ID", "Fecha", "Descripción", "Monto ($)", "Monto (Bs)", "Categoría", "Tipo"])
        self.table_mov.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_mov.setEditTriggers(QAbstractItemView.NoEditTriggers) # Solo lectura
        
        layout.addWidget(self.table_mov)
        return page

    def setup_pendientes_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30,30,30,30)
        
        layout.addWidget(QLabel("<h2>📋 Gestión de Pagos Pendientes y Ventas a Crédito</h2>"))
        
        # Formulario rápido de deuda
        # Usamos un QVBoxLayout para organizar mejor los campos ahora que hay más
        form_frame = QFrame(); form_frame.setObjectName("ContentPanel")
        form_vlayout = QVBoxLayout(form_frame)
        
        # Fila 1: Cliente y Descripción
        row1 = QHBoxLayout()
        self.p_cliente = QLineEdit(); self.p_cliente.setPlaceholderText("Nombre del Cliente / Deudor")
        self.p_desc = QLineEdit(); self.p_desc.setPlaceholderText("Detalle (ej: Venta a crédito / Bulto de Chupetas)")
        row1.addWidget(self.p_cliente, 2)
        row1.addWidget(self.p_desc, 3)
        
        # Fila 2: Montos y Conversión
        row2 = QHBoxLayout()
        self.p_monto_ves = QLineEdit(); self.p_monto_ves.setPlaceholderText("Monto en Bolívares (Bs)")
        self.p_monto = QLineEdit(); self.p_monto.setPlaceholderText("Monto en Dólares ($)")
        
        # Conexión para conversión automática
        self.p_monto_ves.textChanged.connect(self.calc_p_ves_to_usdt)
        self.p_monto.textChanged.connect(self.calc_p_usdt_to_ves)
        
        btn_save_p = QPushButton("➕ Registrar Deuda")
        btn_save_p.setObjectName("btn_success")
        btn_save_p.clicked.connect(self.add_pendiente)
        
        row2.addWidget(QLabel("Monto Bs:"))
        row2.addWidget(self.p_monto_ves, 2)
        row2.addWidget(QLabel("Monto $:"))
        row2.addWidget(self.p_monto, 2)
        row2.addStretch(1)
        row2.addWidget(btn_save_p, 2)
        
        form_vlayout.addLayout(row1)
        form_vlayout.addLayout(row2)
        
        layout.addWidget(form_frame)
        
        # Tabla de Deudores
        self.table_pend = QTableWidget()
        # Columnas: ID, Cliente, Monto ($), Pagado ($), Saldo ($), Saldo (Bs), Fecha, Acción
        self.table_pend.setColumnCount(8)
        self.table_pend.setHorizontalHeaderLabels(["ID", "Cliente", "Monto ($)", "Pagado ($)", "Saldo ($)", "Saldo (Bs)", "Fecha", "Acción"])
        self.table_pend.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(QLabel("<b>Listado de Cobros Pendientes:</b>"))
        layout.addWidget(self.table_pend)
        return page

    def setup_metas_page(self):
        """Página de metas deshabilitada.

        Esta sección solía permitir crear y visualizar metas de ahorro, pero
        fue retirada cuando se decidió eliminar la gestión de ahorros.
        Se conserva un panel vacío con mensaje informativo para evitar errores
        de índices en el QStackedWidget.
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.addWidget(QLabel("<i>La gestión de metas/ahorro ha sido eliminada.</i>"))
        layout.addStretch()
        return page

    def setup_calculator_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30,30,30,30)
        
        layout.addWidget(QLabel("<h2>🧮 Calculadora y Utilidades</h2>"))
        
        # Grid Principal
        grid = QHBoxLayout()
        
        # --- 1. CONVERSOR DE DIVISAS ---
        conv_frame = QFrame(); conv_frame.setObjectName("ContentPanel")
        cv_layout = QVBoxLayout(conv_frame)
        cv_layout.addWidget(QLabel("<b>🔄 Conversor Real: USDT ↔ VES</b>"))
        
        f_cv = QFormLayout()
        # Converter usa la tasa USDT
        self.cv_tasa = QLineEdit(str(self.db.get_tasa_usdt()))
        self.cv_usdt = QLineEdit(); self.cv_usdt.setPlaceholderText("0.00")
        self.cv_ves = QLineEdit(); self.cv_ves.setPlaceholderText("0.00")
        
        # Conexiones
        self.cv_usdt.textChanged.connect(self.calc_conv_to_ves)
        self.cv_ves.textChanged.connect(self.calc_conv_to_usdt)
        self.cv_tasa.textChanged.connect(self.recalc_conv)
        
        f_cv.addRow("Tasa (VES/USD):", self.cv_tasa)
        f_cv.addRow("Monto USD:", self.cv_usdt)
        f_cv.addRow("Monto VES:", self.cv_ves)
        
        cv_layout.addLayout(f_cv)
        cv_layout.addWidget(QLabel("<small style='color:gray'>*Calculadora instantánea</small>"))
        cv_layout.addStretch()
        
        # --- 2. CALCULADORA DE GANANCIAS ---
        profit_frame = QFrame(); profit_frame.setObjectName("ContentPanel")
        pf_layout = QVBoxLayout(profit_frame)
        pf_layout.addWidget(QLabel("<b>📈 Calculadora de Precios y Ganancias</b>"))
        
        f_pf = QFormLayout()
        # Precio y margen usan la tasa BCV (precios oficiales)
        self.pf_tasa = QLineEdit(str(self.db.get_tasa_bcv()))
        self.pf_costo = QLineEdit(); self.pf_costo.setPlaceholderText("Costo del producto ($)")
        self.pf_margen = QLineEdit("30"); self.pf_margen.setPlaceholderText("Margen deseado %")
        
        self.pf_btn_calc = QPushButton("Calcular Proyección")
        self.pf_btn_calc.setObjectName("btn_success")
        self.pf_btn_calc.clicked.connect(self.calc_profit)
        
        # Etiquetas de resultados con mejor estilo
        self.pf_res_pv_usd = QLabel("---")
        self.pf_res_pv_ves = QLabel("---")
        self.pf_res_gan_usd = QLabel("---")
        self.pf_res_gan_ves = QLabel("---")
        
        for lbl in [self.pf_res_pv_usd, self.pf_res_pv_ves, self.pf_res_gan_usd, self.pf_res_gan_ves]:
            lbl.setStyleSheet("font-weight: bold; font-size: 15px; color: #f8f8f2; padding: 2px;")

        self.pf_res_gan_usd.setStyleSheet("font-weight: bold; font-size: 16px; color: #10b981;")
        self.pf_res_gan_ves.setStyleSheet("font-weight: bold; font-size: 16px; color: #10b981;")
        
        f_pf.addRow("Tasa Ref. (VES/$):", self.pf_tasa)
        f_pf.addRow("Costo Producto ($):", self.pf_costo)
        f_pf.addRow("Margen Ganancia (%):", self.pf_margen)
        f_pf.addRow("", self.pf_btn_calc)
        f_pf.addRow(QLabel("<hr>"))
        f_pf.addRow("Precio Venta ($):", self.pf_res_pv_usd)
        f_pf.addRow("Precio Venta (Bs):", self.pf_res_pv_ves)
        f_pf.addRow("Ganancia Neta ($):", self.pf_res_gan_usd)
        f_pf.addRow("Ganancia Neta (Bs):", self.pf_res_gan_ves)
        
        pf_layout.addLayout(f_pf)
        pf_layout.addStretch()
        
        grid.addWidget(conv_frame)
        grid.addWidget(profit_frame)
        
        # --- 3. CALCULADORA DE COSTO UNITARIO Y MAYOREO ---
        bulk_frame = QFrame(); bulk_frame.setObjectName("ContentPanel")
        bk_layout = QVBoxLayout(bulk_frame)
        bk_layout.addWidget(QLabel("<b>📦 Desglose por Bulto / Empaque</b>"))
        
        f_bk = QFormLayout()
        self.bk_tasa = QLineEdit(str(self.db.get_tasa_bcv()))
        self.bk_costo_total = QLineEdit(); self.bk_costo_total.setPlaceholderText("Costo total del bulto ($)")
        self.bk_unidades = QLineEdit("12"); self.bk_unidades.setPlaceholderText("Unidades (ej. 12, 24...)")
        self.bk_margen = QLineEdit("30")
        
        self.bk_btn_calc = QPushButton("Calcular Desglose")
        self.bk_btn_calc.setObjectName("btn_success")
        self.bk_btn_calc.clicked.connect(self.calc_bulk_breakdown)
        
        self.bk_res_unit_cost = QLabel("---")
        self.bk_res_unit_pv = QLabel("---")
        self.bk_res_total_profit = QLabel("---")
        
        for lbl in [self.bk_res_unit_cost, self.bk_res_unit_pv, self.bk_res_total_profit]:
            lbl.setStyleSheet("font-weight: bold; font-size: 14px; color: #f8f8f2;")
            
        self.bk_res_total_profit.setStyleSheet("font-weight: bold; font-size: 15px; color: #6366f1;")
        
        f_bk.addRow("Tasa Ref. (VES/$):", self.bk_tasa)
        f_bk.addRow("Costo Bulto ($):", self.bk_costo_total)
        f_bk.addRow("Cant. Unidades:", self.bk_unidades)
        f_bk.addRow("Margen %:", self.bk_margen)
        f_bk.addRow("", self.bk_btn_calc)
        f_bk.addRow(QLabel("<hr>"))
        f_bk.addRow("Costo Unitario:", self.bk_res_unit_cost)
        f_bk.addRow("P. Venta Unitario:", self.bk_res_unit_pv)
        f_bk.addRow("Ganancia Total:", self.bk_res_total_profit)
        
        bk_layout.addLayout(f_bk)
        bk_layout.addStretch()
        
        grid.addWidget(bulk_frame)
        layout.addLayout(grid)
        
        # --- 4. ARQUEO DE CAJA (USD) ---
        cash_frame = QFrame(); cash_frame.setObjectName("ContentPanel")
        cc_layout = QHBoxLayout(cash_frame)
        
        # Columna Izquierda: Billetes
        f_cc = QFormLayout()
        # Arqueo de caja usa tasa USDT (billetes en $)
        self.cc_tasa = QLineEdit(str(self.db.get_tasa_usdt()))
        self.cc_100 = QLineEdit(); self.cc_100.setPlaceholderText("Cant.")
        self.cc_50 = QLineEdit(); self.cc_50.setPlaceholderText("Cant.")
        self.cc_20 = QLineEdit(); self.cc_20.setPlaceholderText("Cant.")
        self.cc_10 = QLineEdit(); self.cc_10.setPlaceholderText("Cant.")
        self.cc_5 = QLineEdit(); self.cc_5.setPlaceholderText("Cant.")
        self.cc_1 = QLineEdit(); self.cc_1.setPlaceholderText("Cant.")
        
        # Conexiones auto-calculo
        for le in [self.cc_tasa, self.cc_100, self.cc_50, self.cc_20, self.cc_10, self.cc_5, self.cc_1]:
            le.textChanged.connect(self.calc_cash_count)
            
        f_cc.addRow("Tasa Ref:", self.cc_tasa)
        f_cc.addRow("💵 $100 x", self.cc_100)
        f_cc.addRow("💵 $50 x", self.cc_50)
        f_cc.addRow("💵 $20 x", self.cc_20)
        f_cc.addRow("💵 $10 x", self.cc_10)
        f_cc.addRow("💵 $5 x", self.cc_5)
        f_cc.addRow("💵 $1 x", self.cc_1)
        
        # Columna Derecha: Totales
        cc_right = QVBoxLayout()
        cc_right.addWidget(QLabel("<b>Total Efectivo (USD)</b>"))
        self.cc_total_usd = QLabel("0.00 $")
        self.cc_total_usd.setStyleSheet("font-size: 24px; font-weight: bold; color: #10b981;")
        cc_right.addWidget(self.cc_total_usd)
        
        cc_right.addSpacing(20)
        cc_right.addWidget(QLabel("<b>Equivalente en VES</b>"))
        self.cc_info_ves = QLabel("Calculado a la tasa indicada")
        self.cc_total_ves = QLabel("0.00 Bs")
        self.cc_total_ves.setStyleSheet("font-size: 24px; font-weight: bold; color: #3b82f6;")
        cc_right.addWidget(self.cc_info_ves)
        cc_right.addWidget(self.cc_total_ves)
        cc_right.addStretch()
        
        cc_layout.addLayout(f_cc, 1)
        cc_layout.addLayout(cc_right, 2)
        
        layout.addWidget(QLabel("<h3>💵 Arqueo de Caja (USD)</h3>"))
        layout.addWidget(cash_frame)
        
        return page

    # --- LÓGICA CALCULADORA ---
    def calc_cash_count(self):
        try:
            tasa = float(self.cc_tasa.text() or 0)
            total = 0
            total += float(self.cc_100.text() or 0) * 100
            total += float(self.cc_50.text() or 0) * 50
            total += float(self.cc_20.text() or 0) * 20
            total += float(self.cc_10.text() or 0) * 10
            total += float(self.cc_5.text() or 0) * 5
            total += float(self.cc_1.text() or 0) * 1
            
            self.cc_total_usd.setText(f"{total:,.2f} $")
            self.cc_total_ves.setText(f"{total*tasa:,.2f} Bs")
            self.cc_info_ves.setText(f"A tasa: {tasa:.2f}")
        except:
            pass
    def calc_conv_to_ves(self):
        if self.cv_usdt.hasFocus():
            try:
                t = float(self.cv_tasa.text())
                u = float(self.cv_usdt.text())
                self.cv_ves.setText(f"{u*t:.2f}")
            except: self.cv_ves.clear()

    def calc_conv_to_usdt(self):
        if self.cv_ves.hasFocus():
            try:
                t = float(self.cv_tasa.text())
                v = float(self.cv_ves.text())
                self.cv_usdt.setText(f"{v/t:.2f}")
            except: self.cv_usdt.clear()
            
    def recalc_conv(self):
        if self.cv_usdt.text(): self.calc_conv_to_ves()
        
    def calc_profit(self):
        try:
            costo = float(self.pf_costo.text())
            margen = float(self.pf_margen.text())
            tasa = float(self.pf_tasa.text())
            
            # Cálculo de Precio de Venta (markup base)
            # Precio = Costo / (1 - Margen/100)  <-- Esta es la fórmula real de margen sobre precio
            # Pero usaremos la más común: Costo * (1 + Margen/100)
            precio_usd = costo * (1 + (margen/100))
            precio_ves = precio_usd * tasa
            
            ganancia_usd = precio_usd - costo
            ganancia_ves = ganancia_usd * tasa
            
            self.pf_res_pv_usd.setText(f"{precio_usd:,.2f} $")
            self.pf_res_pv_ves.setText(f"{precio_ves:,.2f} Bs")
            self.pf_res_gan_usd.setText(f"{ganancia_usd:,.2f} $")
            self.pf_res_gan_ves.setText(f"{ganancia_ves:,.2f} Bs")
            
        except ValueError:
            QMessageBox.warning(self, "Error", "Por favor, ingrese valores numéricos válidos en todos los campos.")

    def calc_bulk_breakdown(self):
        try:
            costo_bulto = float(self.bk_costo_total.text())
            unidades = float(self.bk_unidades.text())
            margen = float(self.bk_margen.text())
            tasa = float(self.bk_tasa.text())
            
            if unidades <= 0: 
                QMessageBox.warning(self, "Error", "La cantidad de unidades debe ser mayor a 0.")
                return
            
            # Costo por cada unidad individual
            costo_unitario = costo_bulto / unidades
            
            # Precio de venta sugerido por unidad
            pv_unitario_usd = costo_unitario * (1 + (margen/100))
            pv_unitario_ves = pv_unitario_usd * tasa
            
            # Ganancia total al vender todo el bulto
            ganancia_total_usd = (pv_unitario_usd * unidades) - costo_bulto
            ganancia_total_ves = ganancia_total_usd * tasa
            
            self.bk_res_unit_cost.setText(f"{costo_unitario:,.2f} $")
            self.bk_res_unit_pv.setText(f"{pv_unitario_usd:,.2f} $ / {pv_unitario_ves:,.2f} Bs")
            self.bk_res_total_profit.setText(f"{ganancia_total_usd:,.2f} $ / {ganancia_total_ves:,.2f} Bs")
            
        except ValueError:
            QMessageBox.warning(self, "Error", "Por favor, ingrese valores numéricos válidos.")

    def setup_pos_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # --- PARTE IZQUIERDA: BUSQUEDA Y PRODUCTOS ---
        left_panel = QFrame(); left_panel.setObjectName("POSPanel")
        left_layout = QVBoxLayout(left_panel)
        
        left_header = QHBoxLayout()
        left_header.addWidget(QLabel("<h2>🛒 Terminal de Punto de Venta</h2>"))
        left_header.addStretch()
        left_layout.addLayout(left_header)
        
        search_box = QHBoxLayout()
        self.pos_search = QLineEdit()
        self.pos_search.setFixedHeight(40)
        self.pos_search.setPlaceholderText("🔍 Buscar por nombre, código... (Remix Icon sim)")
        self.pos_search.textChanged.connect(self.filter_pos_products)
        search_box.addWidget(self.pos_search)
        left_layout.addLayout(search_box)

        # Selector de tipo (Productos vs Servicios)
        toggle_box = QHBoxLayout()
        self.btn_pos_prod = QPushButton("📦 Productos (F1)")
        self.btn_pos_prod.setCheckable(True)
        self.btn_pos_prod.setChecked(True)
        self.btn_pos_prod.setObjectName("btn_outline")
        self.btn_pos_prod.setFixedHeight(45)
        self.btn_pos_svc = QPushButton("🛠️ Servicios (F2)")
        self.btn_pos_svc.setCheckable(True)
        self.btn_pos_svc.setObjectName("btn_outline")
        self.btn_pos_svc.setFixedHeight(45)
        
        # Atajos de teclado para POS
        QShortcut(QKeySequence("F1"), self).activated.connect(self.btn_pos_prod.click)
        QShortcut(QKeySequence("F2"), self).activated.connect(self.btn_pos_svc.click)
        
        # Grupo exclusivo
        self.pos_mode_group = QButtonGroup(self)
        self.pos_mode_group.addButton(self.btn_pos_prod)
        self.pos_mode_group.addButton(self.btn_pos_svc)
        self.pos_mode_group.setExclusive(True)
        self.pos_mode_group.buttonClicked.connect(self.filter_pos_products)

        toggle_box.addWidget(self.btn_pos_prod)
        toggle_box.addWidget(self.btn_pos_svc)
        left_layout.addLayout(toggle_box)
        
        self.pos_table = QTableWidget()
        self.pos_table.setColumnCount(6)
        self.pos_table.setHorizontalHeaderLabels(["ID", "Código", "🏷️ Nombre", "💵 USD", "💴 VES", "Acción"])
        self.pos_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.pos_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.pos_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.pos_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.pos_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        
        self.pos_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.pos_table.setAlternatingRowColors(True)
        self.pos_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.pos_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.pos_table.verticalHeader().setVisible(False)
        self.pos_table.verticalHeader().setDefaultSectionSize(45)
        self.pos_table.setSortingEnabled(True)
        self.pos_table.setShowGrid(False)
        left_layout.addWidget(self.pos_table)
        
        # --- PARTE DERECHA: CARRITO ---
        right_panel = QFrame(); right_panel.setObjectName("CartPanel")
        right_panel.setFixedWidth(450)
        right_layout = QVBoxLayout(right_panel)
        
        right_layout.addWidget(QLabel("<h2>🧾 Order / Detalle de Pedido</h2>"))
        
        # Cliente
        client_box = QHBoxLayout()
        self.pos_client_sel = QComboBox()
        self.pos_client_sel.setFixedHeight(35)
        self.refresh_pos_clients()
        btn_add_cli = QPushButton("➕ Cliente")
        btn_add_cli.setFixedHeight(35)
        btn_add_cli.clicked.connect(self.add_client_pos)
        client_box.addWidget(QLabel("👤 Cliente:"))
        client_box.addWidget(self.pos_client_sel, 1)
        client_box.addWidget(btn_add_cli)
        right_layout.addLayout(client_box)
        
        # Tabla Carrito
        self.pos_cart_table = QTableWidget()
        self.pos_cart_table.setColumnCount(5)
        self.pos_cart_table.setHorizontalHeaderLabels(["🛍️ Item", "Cant", "Desc %", "Total", "Borrar"])
        self.pos_cart_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.pos_cart_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.pos_cart_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.pos_cart_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        # ocultar columna de descuento si la opción está deshabilitada
        if not self.is_discount_enabled():
            self.pos_cart_table.setColumnHidden(2, True)
        
        self.pos_cart_table.setAlternatingRowColors(True)
        self.pos_cart_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.pos_cart_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.pos_cart_table.verticalHeader().setVisible(False)
        self.pos_cart_table.setShowGrid(False)
        # Añadir algo de altura al row para que se vea más touch-friendly
        self.pos_cart_table.verticalHeader().setDefaultSectionSize(45)
        right_layout.addWidget(self.pos_cart_table)
        
        # Totales Frame (Cono Monetario Style)
        totals_frame = QFrame(); totals_frame.setObjectName("ContentPanel")
        totals_v = QVBoxLayout(totals_frame)
        
        t1 = QHBoxLayout()
        t1.addWidget(QLabel("<b>TOTAL USD:</b>")); t1.addStretch()
        self.lbl_pos_total_usd = QLabel("<b>0.00 $</b>")
        self.lbl_pos_total_usd.setObjectName("value_success")
        t1.addWidget(self.lbl_pos_total_usd)
        
        t2 = QHBoxLayout()
        lbl_v = QLabel("TOTAL VES:"); lbl_v.setObjectName("h3")
        t2.addWidget(lbl_v); t2.addStretch()
        self.lbl_pos_total_ves = QLabel("0.00 Bs")
        self.lbl_pos_total_ves.setObjectName("h3")
        t2.addWidget(self.lbl_pos_total_ves)
        
        totals_v.addLayout(t1); totals_v.addLayout(t2)
        right_layout.addWidget(totals_frame)
        
        # Métodos de Pago
        h_met = QHBoxLayout()
        self.pos_payment_method = QComboBox()
        self.pos_payment_method.setFixedHeight(40)
        self.pos_payment_method.addItems(["💵 Efectivo USD", "💴 Efectivo Bs", "📱 Pago Móvil", "🏦 Transferencia", "🇺🇸 Zelle", "💳 Punto de Venta"])
        h_met.addWidget(QLabel("<b>Método de Pago:</b>"))
        h_met.addWidget(self.pos_payment_method, 1)
        right_layout.addLayout(h_met)
        
        btn_checkout = QPushButton("💰 PROCESAR VENTA (F5)")
        QShortcut(QKeySequence("F5"), self).activated.connect(btn_checkout.click)
        btn_checkout.setObjectName("btn_pos_large")
        btn_checkout.clicked.connect(self.process_pos_sale)
        right_layout.addWidget(btn_checkout)
        
        layout.addWidget(left_panel, 5)
        layout.addWidget(right_panel, 3)
        
        self.pos_cart = [] # List of {'id', 'nombre', 'precio', 'cantidad'}
        return page

    def setup_clients_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30,30,30,30)
        
        top = QHBoxLayout()
        btn_add = QPushButton("Registrar Cliente")
        btn_add.setObjectName("btn_success")
        # Intenta usar icono si está disponible
        ic = load_icon('user-plus')
        if not ic.isNull():
            btn_add.setIcon(ic)
        btn_add.clicked.connect(self.add_client_dialog)
        top.addWidget(btn_add); top.addStretch()
        layout.addLayout(top)
        
        self.tbl_clients = QTableWidget()
        self.tbl_clients.setColumnCount(5)
        self.tbl_clients.setHorizontalHeaderLabels(["ID", "Nombre", "Cédula", "Teléfono", "Dirección"])
        self.tbl_clients.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl_clients.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_clients.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tbl_clients.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tbl_clients.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.tbl_clients.setAlternatingRowColors(True)
        self.tbl_clients.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_clients.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tbl_clients.verticalHeader().setVisible(False)
        self.tbl_clients.setShowGrid(False)
        layout.addWidget(self.tbl_clients)
        
        return page

    # --- LÓGICA POS ---
    def filter_pos_products(self):
        txt = self.pos_search.text().lower()
        is_service_mode = self.btn_pos_svc.isChecked()
        
        if is_service_mode:
            df = self.db.get_services()
        else:
            df = self.db.get_inventory()
            
        if txt:
            df = df[df['nombre'].str.lower().str.contains(txt) | df['codigo'].str.lower().str.contains(txt)]
        
        show_ves = self.db.get_config('pos_show_ves', '0') == '1'
        self.pos_table.setColumnHidden(4, not show_ves)
        
        self.pos_table.setRowCount(len(df))
        tasa = self.db.get_tasa()
        for i, row in df.iterrows():
            self.pos_table.setItem(i, 0, QTableWidgetItem(str(row['id'])))
            self.pos_table.setItem(i, 1, QTableWidgetItem(row['codigo']))
            self.pos_table.setItem(i, 2, QTableWidgetItem(row['nombre']))
            self.pos_table.setItem(i, 3, QTableWidgetItem(f"{row['precio']:.2f} $"))
            self.pos_table.setItem(i, 4, QTableWidgetItem(f"{row['precio'] * tasa:.2f} Bs"))
            
            btn = QPushButton("➕ Añadir")
            btn.setObjectName("btn_primary")
            btn.setCursor(Qt.PointingHandCursor)
            
            self.pos_table.setColumnWidth(5, 110)
            
            btn.clicked.connect(lambda _, r=row, svc=is_service_mode: self.add_to_cart(r, svc))
            self.pos_table.setCellWidget(i, 5, btn)

    def add_to_cart(self, product, is_service=False):
        # Buscar si ya está
        for item in self.pos_cart:
            if item['id'] == product['id'] and item.get('is_service', False) == is_service:
                item['cantidad'] += 1
                self.refresh_cart_table()
                return
        
        self.pos_cart.append({
            'id': product['id'],
            'nombre': product['nombre'],
            'precio': product['precio'],
            'cantidad': 1,
            'descuento': 0.0,
            'is_service': is_service
        })
        self.refresh_cart_table()

    def is_discount_enabled(self):
        """Return True when POS item discounts are allowed by configuration."""
        return self.db.get_config('pos_enable_discount') == '1'

    def update_pos_discount_ui(self):
        """Called when the discount checkbox is toggled or settings are saved.
        Adjusts the cart table column visibility and forces a refresh.
        """
        enabled = self.is_discount_enabled()
        # hide/show header column, refresh any existing rows
        if hasattr(self, 'pos_cart_table'):
            self.pos_cart_table.setColumnHidden(2, not enabled)
        self.refresh_cart_table()

    def refresh_cart_table(self):
        enabled = self.is_discount_enabled()
        # esconder/mostrar columna de descuento según configuración
        self.pos_cart_table.setColumnHidden(2, not enabled)
        self.pos_cart_table.setRowCount(len(self.pos_cart))
        total_usd = 0
        for i, item in enumerate(self.pos_cart):
            base = item['precio'] * item['cantidad']
            if enabled:
                # Aplicar descuento por item
                desc_val = base * (item['descuento'] / 100)
                sub = base - desc_val
            else:
                sub = base
                # asegurar que no haya descuentos acumulados cuando está deshabilitado
                item['descuento'] = 0.0
            total_usd += sub
            
            self.pos_cart_table.setItem(i, 0, QTableWidgetItem(item['nombre']))
            self.pos_cart_table.setItem(i, 1, QTableWidgetItem(str(item['cantidad'])))
            
            if enabled:
                # Spinbox para el descuento
                spin_desc = QDoubleSpinBox()
                spin_desc.setRange(0, 100)
                spin_desc.setSuffix(" %")
                spin_desc.setValue(item['descuento'])
                spin_desc.setButtonSymbols(QDoubleSpinBox.NoButtons)
                spin_desc.setAlignment(Qt.AlignCenter)
                spin_desc.setFixedWidth(80)
                # Forzar visibilidad con estilo local si el global falla
                theme = getattr(self, 'theme_mode', 'light')
                bg = "#ffffff" if theme == 'light' else "#1e293b"
                fg = "#1e293b" if theme == 'light' else "#f8fafc"
                spin_desc.setStyleSheet(f"background-color: {bg}; color: {fg}; border: 1px solid #cbd5e1; border-radius: 4px;")
                
                spin_desc.valueChanged.connect(lambda val, idx=i: self.update_item_discount(idx, val))
                self.pos_cart_table.setCellWidget(i, 2, spin_desc)
            else:
                self.pos_cart_table.setItem(i, 2, QTableWidgetItem("0 %"))
            
            self.pos_cart_table.setItem(i, 3, QTableWidgetItem(f"{sub:.2f}"))
            
            btn_del = QPushButton("🗑️")
            btn_del.setObjectName("btn_danger")
            btn_del.setCursor(Qt.PointingHandCursor)
            
            self.pos_cart_table.setColumnWidth(4, 80)
            
            btn_del.clicked.connect(lambda _, idx=i: self.remove_from_cart(idx))
            self.pos_cart_table.setCellWidget(i, 4, btn_del)
            
        tasa = self.db.get_tasa()
        self.lbl_pos_total_usd.setText(f"{total_usd:,.2f} $")
        self.lbl_pos_total_ves.setText(f"{total_usd * tasa:,.2f} Bs")

    def update_item_discount(self, index, value):
        if not self.is_discount_enabled():
            return
        if 0 <= index < len(self.pos_cart):
            self.pos_cart[index]['descuento'] = value
            # Solo actualizamos el total sin reconstruir la tabla entera para evitar loops/foco
            total_usd = 0
            for item in self.pos_cart:
                base = item['precio'] * item['cantidad']
                total_usd += base * (1 - item['descuento'] / 100)
            
            tasa = self.db.get_tasa()
            self.lbl_pos_total_usd.setText(f"{total_usd:,.2f} $")
            self.lbl_pos_total_ves.setText(f"{total_usd * tasa:,.2f} Bs")
            # Actualizar también la celda de subtotal de la fila
            row_sub = (self.pos_cart[index]['precio'] * self.pos_cart[index]['cantidad']) * (1 - value / 100)
            self.pos_cart_table.setItem(index, 3, QTableWidgetItem(f"{row_sub:.2f}"))

    def remove_from_cart(self, index):
        self.pos_cart.pop(index)
        self.refresh_cart_table()

    def refresh_pos_clients(self):
        self.pos_client_sel.clear()
        df = self.db.get_clientes()
        self.pos_client_sel.addItem("Consumidor Final", 0)
        for _, row in df.iterrows():
            self.pos_client_sel.addItem(f"{row['nombre']} ({row['cedula']})", row['id'])

    def add_client_pos(self):
        if ClientDialog(self, self.db).exec():
            self.refresh_pos_clients()
            self.refresh_clients_table()

    def process_pos_sale(self):
        if not self.pos_cart:
            QMessageBox.warning(self, "Error", "El carrito está vacío")
            return
        
        if not self.is_discount_enabled():
            total_usd = sum(item['precio'] * item['cantidad'] for item in self.pos_cart)
        else:
            total_usd = sum((item['precio'] * (1 - item.get('descuento', 0) / 100)) * item['cantidad'] for item in self.pos_cart)
        total_ves = total_usd * self.db.get_tasa()
        cliente_id = self.pos_client_sel.currentData()
        metodo = self.pos_payment_method.currentText()
        
        try:
            venta_id = self.db.add_venta(cliente_id, total_usd, total_ves, metodo, self.pos_cart)
            
            # Verificar stock de productos vendidos para alertas
            out_of_stock = []
            current_inv = self.db.get_inventory()
            for item in self.pos_cart:
                if not item.get('is_service'):
                    # Buscar stock actual en el dataframe
                    match = current_inv[current_inv['id'] == item['id']]
                    if not match.empty and match.iloc[0]['stock'] <= 0:
                        out_of_stock.append(match.iloc[0]['nombre'])

            QMessageBox.information(self, "Venta Exitosa", f"Venta #{venta_id} procesada.")
            
            # Mostrar alerta de stock si es necesario
            if out_of_stock:
                msg = "⚠️ <b>ALERTA DE RE-STOCK</b><br><br>"
                msg += "Los siguientes productos se han agotado:<br>"
                for prod in out_of_stock:
                    msg += f"• {prod}<br>"
                msg += "<br>Se recomienda realizar un re-stock lo antes posible."
                
                alert = QMessageBox(self)
                alert.setIcon(QMessageBox.Warning)
                alert.setWindowTitle("Agotado - Re-stock Necesario")
                alert.setText(msg)
                alert.setTextFormat(Qt.RichText)
                alert.exec_()

            self.pos_cart = []
            self.refresh_cart_table()
            self.refresh_ui()
            
            # Generación de facturas deshabilitada en esta versión
            # anteriormente se preguntaba al usuario e imprimía factura
            # si estaba activada, ahora no se realiza ninguna acción.
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo completar la venta: {e}")

    def print_invoice(self, venta_id):
        """Función de factura deshabilitada.

        Anteriormente generaba un PDF/impresión de la factura, pero la
        generación de facturas ha sido removida según los requisitos actuales.
        """
        # No se realiza ninguna acción; la facturación fue eliminada.
        pass

    # --- CLIENTES LOGIC ---
    def add_client_dialog(self):
        if ClientDialog(self, self.db).exec():
            self.refresh_clients_table()
            self.refresh_pos_clients()

    def refresh_clients_table(self):
        df = self.db.get_clientes()
        self.tbl_clients.setRowCount(len(df))
        for i, row in df.iterrows():
            self.tbl_clients.setItem(i, 0, QTableWidgetItem(str(row['id'])))
            self.tbl_clients.setItem(i, 1, QTableWidgetItem(row['nombre']))
            self.tbl_clients.setItem(i, 2, QTableWidgetItem(row['cedula']))
            self.tbl_clients.setItem(i, 3, QTableWidgetItem(row['telefono']))
            self.tbl_clients.setItem(i, 4, QTableWidgetItem(row['direccion']))

    def setup_inventory_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30,30,30,30)
        
        top = QHBoxLayout()
        btn_add = QPushButton("Nuevo Producto"); btn_add.setObjectName("btn_success"); btn_add.clicked.connect(self.add_product_dialog)
        btn_edit = QPushButton("Editar"); btn_edit.clicked.connect(self.edit_product_dialog)
        btn_del = QPushButton("Eliminar"); btn_del.setObjectName("btn_danger"); btn_del.clicked.connect(self.delete_product)
        btn_export_inv = QPushButton("📤 Exportar Excel"); btn_export_inv.clicked.connect(self.export_inventory_excel)
        top.addWidget(btn_add); top.addWidget(btn_edit); top.addWidget(btn_del); top.addWidget(btn_export_inv); top.addStretch()
        layout.addLayout(top)
        
        # Alerta de stock (oculta por defecto)
        self.lbl_inv_warning = QLabel("")
        self.lbl_inv_warning.setStyleSheet("background-color: #fee2e2; color: #ef4444; border: 1px solid #fecaca; padding: 10px; border-radius: 8px; font-weight: bold;")
        self.lbl_inv_warning.setVisible(False)
        layout.addWidget(self.lbl_inv_warning)
        
        self.tbl_inv = QTableWidget()
        self.tbl_inv.setColumnCount(7)
        self.tbl_inv.setHorizontalHeaderLabels(["ID", "Código", "Nombre", "Costo", "Precio", "Stock", "Categoría"])
        self.tbl_inv.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tbl_inv)
        return page

    def setup_services_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30,30,30,30)
        
        top = QHBoxLayout()
        btn_add = QPushButton("Nuevo Servicio"); btn_add.setObjectName("btn_success"); btn_add.clicked.connect(self.add_service_dialog)
        btn_edit = QPushButton("Editar"); btn_edit.clicked.connect(self.edit_service_dialog)
        btn_del = QPushButton("Eliminar"); btn_del.setObjectName("btn_danger"); btn_del.clicked.connect(self.delete_service)
        btn_import_svc = QPushButton("📥 Importar Servicios Excel"); btn_import_svc.clicked.connect(self.import_services_excel)
        top.addWidget(btn_add); top.addWidget(btn_edit); top.addWidget(btn_del); top.addWidget(btn_import_svc); top.addStretch()
        layout.addLayout(top)
        
        self.tbl_services = QTableWidget()
        self.tbl_services.setColumnCount(5)
        self.tbl_services.setHorizontalHeaderLabels(["ID", "Código", "Nombre", "Precio", "Categoría"])
        self.tbl_services.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tbl_services)
        return page

    def setup_reports_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30,30,30,30)
        
        header = QHBoxLayout()
        header.addWidget(QLabel("<h2>📊 Reportes Dinámicos y Analíticas (Cono Monetario)</h2>"))
        header.addStretch()
        self.rep_period = QComboBox()
        self.rep_period.setFixedWidth(200)
        self.rep_period.addItems(["📅 Hoy", "📆 Esta Semana", "📅 Este Mes", "🗓️ Este Año", "♾️ Todo el Tiempo"])
        self.rep_period.currentIndexChanged.connect(self.refresh_reports)
        
        self.rep_search = QLineEdit()
        self.rep_search.setPlaceholderText("🔍 Buscar venta por cliente o ID...")
        self.rep_search.setFixedWidth(300)
        self.rep_search.textChanged.connect(self.refresh_reports)
        
        header.addWidget(self.rep_search)
        header.addWidget(self.rep_period)
        layout.addLayout(header)
        
        # Grid para gráficos
        grid = QHBoxLayout()
        
        # Donut distribucion
        f1 = QFrame(); f1.setObjectName("ContentPanel")
        v1 = QVBoxLayout(f1)
        v1.addWidget(QLabel("<b>🍩 Distribución por Categorías</b>"))
        self.rep_chart_donut = ChartWidget(getattr(self, 'theme_mode', 'dark'))
        v1.addWidget(self.rep_chart_donut)
        grid.addWidget(f1)
        
        # Bar tendencia
        f2 = QFrame(); f2.setObjectName("ContentPanel")
        v2 = QVBoxLayout(f2)
        v2.addWidget(QLabel("<b>📈 Tendencia de Transacciones</b>"))
        self.rep_chart_bar = ChartWidget(getattr(self, 'theme_mode', 'dark'))
        v2.addWidget(self.rep_chart_bar)
        grid.addWidget(f2)
        
        layout.addLayout(grid)
        
        # Panel inferior de resumen (Cono monetario summary)
        bot_frame = QFrame(); bot_frame.setObjectName("ContentPanel")
        bot_layout = QHBoxLayout(bot_frame)
        self.rep_lbl_ingresos = QLabel("Ingresos: 0.00 $")
        self.rep_lbl_ingresos.setStyleSheet("color: #10b981; font-weight: bold; font-size: 16px;")
        self.rep_lbl_gastos = QLabel("Gastos: 0.00 $")
        self.rep_lbl_gastos.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 16px;")
        self.rep_lbl_balance = QLabel("Balance Neta: 0.00 $")
        self.rep_lbl_balance.setStyleSheet("color: #3b82f6; font-weight: bold; font-size: 16px;")
        
        bot_layout.addWidget(QLabel("<b>💵 Análisis USD:</b>"))
        bot_layout.addWidget(self.rep_lbl_ingresos)
        bot_layout.addWidget(self.rep_lbl_gastos)
        bot_layout.addWidget(self.rep_lbl_balance)
        layout.addWidget(bot_frame)
        
        btn_refresh = QPushButton("🔄 Actualizar Reportes")
        btn_refresh.setFixedWidth(250)
        btn_refresh.clicked.connect(self.refresh_reports)
        
        btn_sales_chart = QPushButton("📊 Ventas por Producto")
        btn_sales_chart.setFixedWidth(250)
        btn_sales_chart.setObjectName("btn_primary")
        btn_sales_chart.clicked.connect(self.show_product_sales_chart)
        
        btns_rep = QHBoxLayout()
        btns_rep.addStretch()
        btns_rep.addWidget(btn_refresh)
        btns_rep.addWidget(btn_sales_chart)
        btns_rep.addStretch()
        layout.addLayout(btns_rep)

        # Tabla de ventas (nueva): mostrará registros de la tabla ventas
        self.tbl_sales = QTableWidget()
        self.tbl_sales.setColumnCount(6)
        self.tbl_sales.setHorizontalHeaderLabels(["ID", "Fecha", "Cliente", "Total USD", "Método", "Detalles"])
        self.tbl_sales.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_sales.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(QLabel("<b>📋 Historial de Ventas</b>"))
        layout.addWidget(self.tbl_sales)

        return page

    def add_product_dialog(self):
        ProductDialog(self, self.db).exec()
        self.load_inventory_table()

    def edit_product_dialog(self):
        rows = self.tbl_inv.selectedItems()
        if not rows: return
        pid = int(self.tbl_inv.item(rows[0].row(), 0).text())
        ProductDialog(self, self.db, pid).exec()
        self.load_inventory_table()
        
    def delete_product(self):
        rows = self.tbl_inv.selectedItems()
        if not rows: return
        pid = int(self.tbl_inv.item(rows[0].row(), 0).text())
        if QMessageBox.question(self, "Eliminar", "¿Borrar producto?") == QMessageBox.Yes:
            self.db.delete_product(pid)
            self.load_inventory_table()

    def export_inventory_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar Inventario", f"inventario_{datetime.now().strftime('%Y%m%d')}.xlsx", "Excel Files (*.xlsx)")
        if path:
            try:
                df = self.db.get_inventory()
                df.to_excel(path, index=False)
                QMessageBox.information(self, "Éxito", f"Inventario exportado a {path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Fallo al exportar: {e}")

    def import_services_excel(self):
        """Importa servicios desde Excel usando el modelo de porcentajes."""
        path, _ = QFileDialog.getOpenFileName(self, "Importar Servicios (Excel)", "", "Excel Files (*.xlsx)")
        if not path: return
        
        try:
            df = pd.read_excel(path, header=None)
            with self.db.get_connection() as conn:
                conn.cursor().execute("DELETE FROM servicios") # Re-importación limpia
            
            count = 0
            for _, row in df.iterrows():
                try:
                    name = str(row[0]).strip()
                    pct_val = str(row[1]).strip()
                    precio = float(row[2])
                    
                    if name == "nan" or name == "": continue
                    
                    full_name = f"{name} ({pct_val}%)" if pct_val.replace('.0','').isdigit() else f"{name} {pct_val}"
                    if pct_val == "nan": full_name = name
                    
                    self.db.add_service(f"SVC-{count:04d}", full_name, "Importado de Excel", precio)
                    count += 1
                except: continue
                
            QMessageBox.information(self, "Excel", f"Se importaron {count} servicios correctamente.")
            self.refresh_ui()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Fallo al importar Excel: {e}")

    def add_service_dialog(self):
        if ServiceDialog(self, self.db).exec():
            self.load_services_table()

    def edit_service_dialog(self):
        rows = self.tbl_services.selectedItems()
        if not rows: return
        sid = int(self.tbl_services.item(rows[0].row(), 0).text())
        if ServiceDialog(self, self.db, sid).exec():
            self.load_services_table()

    def delete_service(self):
        rows = self.tbl_services.selectedItems()
        if not rows: return
        sid = int(self.tbl_services.item(rows[0].row(), 0).text())
        if QMessageBox.question(self, "Eliminar", "¿Eliminar servicio?") == QMessageBox.Yes:
            self.db.delete_service(sid)
            self.load_services_table()

    def load_services_table(self):
        df = self.db.get_services()
        self.tbl_services.setRowCount(len(df))
        for i, row in df.iterrows():
            self.tbl_services.setItem(i, 0, QTableWidgetItem(str(row['id'])))
            self.tbl_services.setItem(i, 1, QTableWidgetItem(row['codigo']))
            self.tbl_services.setItem(i, 2, QTableWidgetItem(row['nombre']))
            self.tbl_services.setItem(i, 3, QTableWidgetItem(f"{row['precio']:.2f} $"))
            self.tbl_services.setItem(i, 4, QTableWidgetItem(row['categoria']))


    def load_inventory_table(self):
        df = self.db.get_inventory()
        self.tbl_inv.setRowCount(len(df))
        
        low_stock_count = 0
        for i, row in df.iterrows():
            stk = int(row['stock'])
            if stk <= 0: low_stock_count += 1
            
            self.tbl_inv.setItem(i, 0, QTableWidgetItem(str(row['id'])))
            self.tbl_inv.setItem(i, 1, QTableWidgetItem(row['codigo']))
            self.tbl_inv.setItem(i, 2, QTableWidgetItem(row['nombre']))
            self.tbl_inv.setItem(i, 3, QTableWidgetItem(f"{row['costo']:.2f}"))
            self.tbl_inv.setItem(i, 4, QTableWidgetItem(f"{row['precio']:.2f}"))
            
            # Stock con alerta visual
            stock_item = QTableWidgetItem(str(stk))
            if stk <= 0:
                stock_item.setBackground(QColor("#fee2e2")) # Rojo muy claro
                stock_item.setForeground(QColor("#ef4444")) # Rojo fuerte
                font = stock_item.font()
                font.setBold(True)
                stock_item.setFont(font)
            self.tbl_inv.setItem(i, 5, stock_item)
            
            self.tbl_inv.setItem(i, 6, QTableWidgetItem(row['categoria']))
            
        # Actualizar banner de advertencia si existe el objeto
        if hasattr(self, 'lbl_inv_warning'):
            if low_stock_count > 0:
                self.lbl_inv_warning.setText(f"⚠️ ATENCIÓN: Hay {low_stock_count} producto(s) sin stock. Se recomienda realizar un re-stock.")
                self.lbl_inv_warning.setVisible(True)
            else:
                self.lbl_inv_warning.setVisible(False)

    def refresh_reports(self):
        df = self.db.get_dataframe()
        if df.empty:
            self.rep_chart_donut.plot_donut({})
            self.rep_chart_bar.plot_bar([], [])
            # limpiar tabla de ventas también
            self.tbl_sales.setRowCount(0)
            return
            
        # Filtro de fecha para reportes dimámicos
        try:
            df['fecha_datetime'] = pd.to_datetime(df['fecha'])
        except:
            pass # Si hay falla parseando
            
        now = datetime.now()
        periodo = self.rep_period.currentText()
        if hasattr(df, 'fecha_datetime'):
            if "Hoy" in periodo:
                df = df[df['fecha_datetime'].dt.date == now.date()]
            elif "Esta Semana" in periodo:
                start = now - pd.Timedelta(days=now.weekday())
                df = df[df['fecha_datetime'] >= start]
            elif "Este Mes" in periodo:
                df = df[(df['fecha_datetime'].dt.month == now.month) & (df['fecha_datetime'].dt.year == now.year)]
            elif "Este Año" in periodo:
                df = df[df['fecha_datetime'].dt.year == now.year]

        ing = df[df['tipo']=='INGRESO']['monto_usdt'].sum()
        gas = df[df['tipo']=='GASTO']['monto_usdt'].sum()
        
        # Donut (Categorías de ingresos o gastos combinados, ej. Todo)
        if not df.empty:
            df['cat_simple'] = df['categoria'].fillna('Otros').apply(lambda x: str(x).split(' ')[0])
            data_cat = df.groupby('cat_simple')['monto_usdt'].sum().to_dict()
            self.rep_chart_donut.plot_donut(data_cat, title="Distribución por Categorías ($)")
            
            # Gráfico de barras (Ingreso vs Gasto)
            self.rep_chart_bar.plot_bar(["Ingresos", "Gastos"], [ing, gas], title="Ingresos vs Gastos ($)")
        else:
            self.rep_chart_donut.plot_donut({})
            self.rep_chart_bar.plot_bar([], [])

        # Resumen Label
        self.rep_lbl_ingresos.setText(f"Ingresos: {ing:,.2f} $")
        self.rep_lbl_gastos.setText(f"Gastos: {gas:,.2f} $")
        self.rep_lbl_balance.setText(f"Balance Neto: {(ing - gas):,.2f} $")

        # Cargar tabla de ventas según periodo seleccionado
        sales_df = pd.DataFrame(self.db.get_ventas())
        if not sales_df.empty and 'fecha' in sales_df:
            try:
                sales_df['fecha_datetime'] = pd.to_datetime(sales_df['fecha'])
            except:
                pass
            if 'fecha_datetime' in sales_df:
                if "Hoy" in periodo:
                    sales_df = sales_df[sales_df['fecha_datetime'].dt.date == now.date()]
                elif "Esta Semana" in periodo:
                    start = now - pd.Timedelta(days=now.weekday())
                    sales_df = sales_df[sales_df['fecha_datetime'] >= start]
                elif "Este Mes" in periodo:
                    sales_df = sales_df[(sales_df['fecha_datetime'].dt.month == now.month) & (sales_df['fecha_datetime'].dt.year == now.year)]
                elif "Este Año" in periodo:
                    sales_df = sales_df[sales_df['fecha_datetime'].dt.year == now.year]
        # rellenar tabla
        # Aplicamos filtro de búsqueda de texto si rep_search tiene contenido
        search_q = self.rep_search.text().lower().strip()
        if search_q:
            sales_df = sales_df[
                sales_df['cliente'].str.lower().str.contains(search_q, na=False) |
                sales_df['id'].astype(str).str.contains(search_q)
            ]

        self.tbl_sales.setRowCount(len(sales_df))
        for i, row in sales_df.iterrows():
            v_id = row.get('id','')
            self.tbl_sales.setItem(i, 0, QTableWidgetItem(str(v_id)))
            self.tbl_sales.setItem(i, 1, QTableWidgetItem(str(row.get('fecha',''))))
            self.tbl_sales.setItem(i, 2, QTableWidgetItem(str(row.get('cliente',''))))
            self.tbl_sales.setItem(i, 3, QTableWidgetItem(f"{row.get('total_usd',0):.2f}"))
            self.tbl_sales.setItem(i, 4, QTableWidgetItem(str(row.get('metodo_pago',''))))
            
            # Botón de detalles
            btn_det = QPushButton("🔍 Ver Productos")
            btn_det.setObjectName("btn_primary")
            btn_det.setFixedHeight(30)
            btn_det.clicked.connect(lambda _, vid=v_id: self.show_venta_detalle(vid))
            self.tbl_sales.setCellWidget(i, 5, btn_det)

    def show_venta_detalle(self, venta_id):
        """Muestra el diálogo con los productos de una venta."""
        if not venta_id: return
        try:
            # Asegurarse de que el ID sea entero
            v_id = int(venta_id)
            dlg = SaleDetailsDialog(v_id, self.db, self)
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo cargar el detalle: {e}")

    def show_product_sales_chart(self):
        """Muestra una ventana con el gráfico de todos los productos vendidos."""
        df = self.db.get_top_selling_products(limit=100)
        if df.empty:
            QMessageBox.information(self, "Info", "No hay datos de ventas disponibles.")
            return
            
        dlg = QDialog(self)
        dlg.setWindowTitle("Gráfico de Ventas por Producto")
        dlg.setMinimumSize(800, 600)
        v = QVBoxLayout(dlg)
        
        chart = ChartWidget(getattr(self, 'theme_mode', 'dark'))
        chart.plot_bar(df['nombre'].tolist(), df['total_vendido'].tolist(), title="Total Unidades Vendidas por Producto")
        v.addWidget(chart)
        
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(dlg.accept)
        v.addWidget(btn_close)
        dlg.exec()

    def setup_config_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40,40,40,40)
        
        layout.addWidget(QLabel("<h2>⚙️ Avanzado y Configuración Global</h2>"))
        
        # Formulario principal de configuración
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        form_ly = QVBoxLayout(container)
        
        # --- 1. Distribuido en Cono Monetario y Tasas ---
        gb_cono = QGroupBox("💵 Distribución de Cono Monetario y Tasas de Cambio")
        form_cono = QFormLayout(gb_cono)
        
        self.cb_tasa_mode = QComboBox()
        self.cb_tasa_mode.addItems(["🌐 API (Al Cambio Automático)", "✍️ Manual"])
        self.cb_tasa_mode.currentIndexChanged.connect(self.tasa_mode_changed_ui)
        
        self.cfg_tasa_usdt = QLineEdit()
        self.cfg_tasa_usdt.setPlaceholderText("Tasa USD/VES ($)")
        btn_upd_tasa_usdt = QPushButton("Actualizar Tasa USDT (API)")
        btn_upd_tasa_usdt.clicked.connect(self.update_tasa_usdt_ui)
        self.btn_upd_tasa_usdt = btn_upd_tasa_usdt

        btn_save_tasa_usdt = QPushButton("Guardar Manual")
        btn_save_tasa_usdt.clicked.connect(self.save_tasa_usdt_ui)
        self.btn_save_tasa_usdt = btn_save_tasa_usdt

        self.cfg_tasa_bcv = QLineEdit()
        self.cfg_tasa_bcv.setPlaceholderText("Tasa BCV Oficial para Precios")
        btn_upd_tasa_bcv = QPushButton("Guardar Tasa BCV Oficial")
        btn_upd_tasa_bcv.clicked.connect(self.update_tasa_bcv_ui)

        self.cfg_tasa = QLineEdit() # Legacy visual
        btn_upd_tasa = QPushButton("Guardar Tasa Sistema")
        btn_upd_tasa.clicked.connect(self.update_tasa_global)
        
        h_usdt = QHBoxLayout()
        h_usdt.addWidget(btn_upd_tasa_usdt); h_usdt.addWidget(btn_save_tasa_usdt)
        
        form_cono.addRow("🚀 Tipo de Obtención:", self.cb_tasa_mode)
        form_cono.addRow(QLabel("<hr>"))
        form_cono.addRow("💲 Tasa Mercado Paralelo (USD -> VES):", self.cfg_tasa_usdt)
        form_cono.addRow("", h_usdt)
        form_cono.addRow(QLabel("<br>"))
        form_cono.addRow("🏛️ Tasa Emisión BCV (USD -> VES):", self.cfg_tasa_bcv)
        form_cono.addRow("", btn_upd_tasa_bcv)
        form_cono.addRow(QLabel("<br>"))
        form_cono.addRow("🔄 Tasa Principal Legacy:", self.cfg_tasa)
        form_cono.addRow("", btn_upd_tasa)
        form_ly.addWidget(gb_cono)
        
        # --- 2. Telegram Configurations ---
        gb_tg = QGroupBox("📱 Notificaciones Bots y Telegram")
        form_tg = QFormLayout(gb_tg)
        
        self.tg_token = QLineEdit(); self.tg_token.setEchoMode(QLineEdit.Password)
        self.tg_chat = QLineEdit()
        btn_tg_save = QPushButton("Guardar Config Telegram")
        btn_tg_save.clicked.connect(self.save_telegram_config)
        
        tg_token, tg_chat = self.db.get_telegram_config()
        self.tg_token.setText(tg_token)
        self.tg_chat.setText(tg_chat)
        
        form_tg.addRow("Telegram Bot Token:", self.tg_token)
        form_tg.addRow("Telegram Chat ID:", self.tg_chat)
        form_tg.addRow("", btn_tg_save)
        form_ly.addWidget(gb_tg)
        
        # --- 3. Sistema y Respaldo ---
        gb_sys = QGroupBox("🛡️ Seguridad y Respaldo de Datos")
        form_sys = QFormLayout(gb_sys)
        
        btn_backup = QPushButton("💾 Crear Respaldo (Backup .db)")
        btn_backup.clicked.connect(self.create_backup)
        btn_export = QPushButton("📤 Exportar DB Completa (JSON)")
        btn_export.clicked.connect(self.export_data_json)
        btn_import_json = QPushButton("📥 Importar DB desde (JSON)")
        btn_import_json.clicked.connect(self.import_data_json)
        btn_import_db = QPushButton("📥 Migrar desde DB anterior (.db)")
        btn_import_db.clicked.connect(self.import_from_old_db)
        btn_rebuild_index = QPushButton("🔍 Reconstruir Índice de Búsquedas Rápidas")
        btn_rebuild_index.setObjectName("btn_warning")
        btn_rebuild_index.clicked.connect(self.rebuild_search_index_ui)
        
        form_sys.addRow("", btn_backup)
        form_sys.addRow("", btn_export)
        form_sys.addRow("", btn_import_json)
        form_sys.addRow("", btn_import_db)
        form_sys.addRow("", btn_rebuild_index)
        form_ly.addWidget(gb_sys)
        
        # --- 4. Interfaz y POS ---
        gb_pos_ui = QGroupBox("🛒 Configuración de Interfaz POS")
        form_pos_ui = QFormLayout(gb_pos_ui)
        
        self.cfg_pos_ves = QCheckBox("Mostrar columna de Bolívares (VES) en POS")
        self.cfg_pos_ves.setChecked(self.db.get_config('pos_show_ves') == '1')
        
        self.cfg_pos_disc = QCheckBox("Habilitar opción de descuento del 25% en POS")
        self.cfg_pos_disc.setChecked(self.db.get_config('pos_enable_discount') == '1')
        # reacción inmediata cuando el usuario cambia la casilla
        self.cfg_pos_disc.stateChanged.connect(self.update_pos_discount_ui)
        
        form_pos_ui.addRow(self.cfg_pos_ves)
        form_pos_ui.addRow(self.cfg_pos_disc)
        form_ly.addWidget(gb_pos_ui)
        
        # --- 5. Hotkeys (Atajos de Teclado) ---
        gb_hk = QGroupBox("⌨️ Atajos de Teclado (Hotkeys)")
        form_hk = QFormLayout(gb_hk)
        
        self.hk_pos = QLineEdit(self.db.get_config('hk_pos', 'F1'))
        self.hk_mov = QLineEdit(self.db.get_config('hk_movimientos', 'F2'))
        self.hk_rep = QLineEdit(self.db.get_config('hk_reportes', 'F3'))
        self.hk_inv = QLineEdit(self.db.get_config('hk_inventory', 'F4'))
        self.hk_checkout = QLineEdit(self.db.get_config('hk_checkout', 'F5'))
        
        form_hk.addRow("Ir a Punto de Venta:", self.hk_pos)
        form_hk.addRow("Ir a Movimientos:", self.hk_mov)
        form_hk.addRow("Ir a Reportes:", self.hk_rep)
        form_hk.addRow("Ir a Inventario:", self.hk_inv)
        form_hk.addRow("Procesar Venta (Checkout):", self.hk_checkout)
        
        btn_save_config = QPushButton("💾 Guardar Todo")
        btn_save_config.setObjectName("btn_success")
        btn_save_config.clicked.connect(self.save_all_settings)
        form_ly.addWidget(btn_save_config)
        
        form_ly.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        return page

    def save_all_settings(self):
        """Guarda todas las configuraciones de la página de config."""
        # Verificar que los objetos existan antes de acceder
        if not hasattr(self, 'cfg_pos_ves') or not self.cfg_pos_ves: return
        
        self.db.set_config('pos_show_ves', '1' if self.cfg_pos_ves.isChecked() else '0')
        self.db.set_config('pos_enable_discount', '1' if self.cfg_pos_disc.isChecked() else '0')
        self.db.set_config('hk_pos', self.hk_pos.text())
        self.db.set_config('hk_movimientos', self.hk_mov.text())
        self.db.set_config('hk_reportes', self.hk_rep.text())
        self.db.set_config('hk_inventory', self.hk_inv.text())
        self.db.set_config('hk_checkout', self.hk_checkout.text())
        
        # Recargar Hotkeys
        self.setup_hotkeys()
        self.refresh_ui()
        # actualizar la UI de descuentos y el carrito si cambia
        self.update_pos_discount_ui()
        self.refresh_cart_table()
        QMessageBox.information(self, "Éxito", "Configuración guardada correctamente.")

    def save_telegram_config(self):
        self.db.set_telegram_config(self.tg_token.text(), self.tg_chat.text())
        self.reminder_manager.set_telegram_config(self.tg_token.text(), self.tg_chat.text())
        QMessageBox.information(self, "Info", "Configuración guardada.")

    # =========================================================================
    # LÓGICA DE NEGOCIO Y ACTUALIZACIÓN UI
    # =========================================================================

    def refresh_ui(self):
        """Actualiza todos los elementos de la interfaz."""
        # 1. Actualizar Dashboard Header y KPI Cards
        self.lbl_last_update.setText(f"Actualizado: {datetime.now().strftime('%H:%M:%S')}")

        kpis = self.db.get_balance_summary()
        self.kpi_ingresos.findChild(QLabel, "value_success").setText(f"{kpis['ingreso']:,.2f} $")
        self.kpi_gastos.findChild(QLabel, "value_danger").setText(f"{kpis['gasto']:,.2f} $")
        # Ventas Totales
        self.kpi_ventas.findChild(QLabel, "value_primary").setText(f"{kpis['balance'] + kpis['gasto']:,.2f} $")
        
        # Nueva KPI: Deuda pendiente
        try:
            with self.db.get_connection() as conn:
                res = conn.execute("SELECT SUM(monto_usdt - monto_pagado) as deuda FROM pendientes WHERE estado='PENDIENTE'").fetchone()
                deuda = res['deuda'] if res else 0
            self.kpi_debt.findChild(QLabel, "value_warning").setText(f"{deuda or 0:,.2f} $")
        except: pass

        # poblar lista de acciones recientes
        if hasattr(self, 'recent_list'):
            self.recent_list.clear()
            for act in self.db.get_recent_actions(limit=8):
                text = f"{act['fecha']} | {act['descripcion']} | {act['monto_usdt']:.2f} $"
                self.recent_list.addItem(text)
        # asegurar que la tabla POS refleje la configuración actual de descuentos
        self.update_pos_discount_ui()

        # 2. Actualizar Gráficos
        # Chart 1: Ventas por Categoría (Donut)
        try:
            df_cat = self.db.get_category_sales()
            if not df_cat.empty:
                data_cat = df_cat.set_index('cat')['total'].to_dict()
                self.chart_cat.plot_donut(data_cat, "Distribución de Ventas")
            else:
                self.chart_cat.plot_donut({}, "Ventas por Categoría")
        except: pass

        # Chart 2: Ventas Semanales (Line)
        try:
            df_week = self.db.get_weekly_sales()
            if not df_week.empty:
                labels = df_week['dia'].tolist()
                values = df_week['total'].tolist()
                self.chart_weekly.plot_line(labels, values, "Historial de Ventas")
            else:
                self.chart_weekly.plot_line([], [], "Sin Ventas Recientes")
        except: pass

        # Chart 3: Top Productos (Horizontal Bar)
        try:
            df_top = self.db.get_top_selling_products(limit=5)
            if not df_top.empty:
                df_top = df_top.iloc[::-1] # Invertir para mejor visualización hbar
                labels = df_top['nombre'].tolist()
                values = df_top['total_vendido'].tolist()
                self.chart_top.plot_horizontal_bar(labels, values, "Top Productos")
            else:
                self.chart_top.plot_horizontal_bar([], [], "Sin Datos")
        except: pass

        # Chart 4: Distribución de Gastos (Donut)
        try:
            df_tx = self.db.get_dataframe()
            if not df_tx.empty:
                gastos = df_tx[df_tx['tipo'] == 'GASTO']
                if not gastos.empty:
                    gastos['cat_simple'] = gastos['categoria'].apply(lambda x: x.split(' ')[0])
                    data_g = gastos.groupby('cat_simple')['monto_usdt'].sum().to_dict()
                    self.chart_expenses.plot_donut(data_g, "Gastos por Categoría")
                else:
                    self.chart_expenses.plot_donut({}, "Sin Gastos")
            else:
                self.chart_expenses.plot_donut({}, "Sin Movimientos")
        except: pass

        # 3. Actualizar Tablas y POS
        self.load_transactions_table()
        self.load_pendientes_table()
        self.load_inventory_table()
        self.load_services_table()
        self.refresh_clients_table()
        self.refresh_pos_clients()
        self.filter_pos_products()
        
        # 4. Config Sync
        try:
            self.cfg_tasa_usdt.setText(str(self.db.get_tasa_usdt()))
            self.cfg_tasa_bcv.setText(str(self.db.get_tasa_bcv()))
            self.cfg_tasa.setText(str(self.db.get_tasa()))
        except: pass

        # Modo de tasa
        mode = self.db.get_tasa_mode()
        self.cb_tasa_mode.setCurrentIndex(0 if mode == 'api' else 1)
        self._apply_tasa_mode_to_ui()

        # Rebuild global search index
        try:
            self.build_search_index()
            self.refresh_reminders_table()
        except: pass

    # Background tasks: exchange sync, reminders and search UI
    def setup_background_tasks(self):
        self.reminder_manager = ReminderManager()
        self.exchange = ExchangeRates(ttl=3600)
        self.global_search = GlobalSearch()
        threading.Thread(target=self.sync_exchange_rate, daemon=True).start()
        try:
            self.reminder_manager.scheduler.add_job(self.sync_exchange_rate, 'interval', hours=1, id='exchange_sync')
        except Exception:
            pass
        # Schedule periodic rebuild of search index
        try:
            if hasattr(self.reminder_manager.scheduler, 'add_job'):
                self.reminder_manager.scheduler.add_job(self.db.rebuild_search_index, 'interval', hours=6, id='rebuild_search_index')
        except Exception:
            pass
        self.sync_reminders_from_db()
        try:
            sc = QShortcut(QKeySequence("Ctrl+K"), self)
            sc.activated.connect(self.open_global_search_dialog)
        except Exception:
            pass

    def update_search_suggestions(self, text):
        try:
            suggestions = self.db.autocomplete_suggestions(text, limit=20)
            self.search_model.setStringList(suggestions)
        except Exception:
            self.search_model.setStringList([])

    def rebuild_search_index_ui(self):
        try:
            n = self.db.rebuild_search_index()
            if n:
                QMessageBox.information(self, "Éxito", "Índice de búsqueda reconstruido.")
                self.build_search_index()
            else:
                QMessageBox.warning(self, "Aviso", "FTS5 no disponible en esta instalación de SQLite.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo reconstruir el índice: {e}")

    def sync_exchange_rate(self):
        try:
            # Solo actualizamos la tasa USDT automáticamente (Al Cambio API) si el modo es 'api'.
            if self.db.get_tasa_mode() == 'api':
                rate_usdt = self.db.update_tasa_usdt_from_api()
                self.cfg_tasa_usdt.setText(str(rate_usdt))
                self.cfg_tasa.setText(str(rate_usdt))
            # NOTA: no actualizamos BCV ni legacy automáticamente; son campos de guardado manual
        except Exception as e:
            print("Exchange sync failed:", e)

    def sync_reminders_from_db(self):
        rows = self.db.get_upcoming_reminders()
        for r in rows:
            job_id = f"reminder_{r['id']}"
            if not self.reminder_manager.scheduler.get_job(job_id):
                run_at = datetime.fromisoformat(r['run_at'])
                title = r['title']
                message = r['message']
                repeat = r['repeat']
                if repeat == 'once':
                    self.reminder_manager.scheduler.add_job(self.reminder_manager._notify, 'date', run_date=run_at, args=[title, message], id=job_id)
                elif repeat == 'daily':
                    self.reminder_manager.scheduler.add_job(self.reminder_manager._notify, 'interval', days=1, start_date=run_at, args=[title, message], id=job_id)
                elif repeat == 'weekly':
                    self.reminder_manager.scheduler.add_job(self.reminder_manager._notify, 'interval', weeks=1, start_date=run_at, args=[title, message], id=job_id)
                elif repeat == 'hourly':
                    self.reminder_manager.scheduler.add_job(self.reminder_manager._notify, 'interval', hours=1, start_date=run_at, args=[title, message], id=job_id)

    def setup_reminders_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30,30,30,30)
        layout.addWidget(QLabel("<h2>🔔 Recordatorios & Notificaciones</h2>"))

        btn_add = QPushButton("Nuevo Recordatorio")
        btn_add.setObjectName("btn_success")
        btn_add.clicked.connect(self.add_reminder_dialog)
        btn_del = QPushButton("Eliminar Seleccionado")
        btn_del.setObjectName("btn_danger")
        btn_del.clicked.connect(self.delete_selected_reminder)
        btn_toggle = QPushButton("Activar / Desactivar")
        btn_toggle.clicked.connect(self.toggle_reminder_enabled)
        h = QHBoxLayout()
        h.addWidget(btn_add); h.addWidget(btn_del); h.addWidget(btn_toggle); h.addStretch()
        layout.addLayout(h)
        self.tbl_reminders = QTableWidget()
        self.tbl_reminders.setColumnCount(6)
        self.tbl_reminders.setHorizontalHeaderLabels(["ID","Título","Mensaje","Run At","Repetir","Enabled"])
        self.tbl_reminders.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tbl_reminders)
        self.refresh_reminders_table()
        return page

    def refresh_reminders_table(self):
        rows = self.db.get_upcoming_reminders()
        self.tbl_reminders.setRowCount(len(rows))
        for i,r in enumerate(rows):
            self.tbl_reminders.setItem(i,0,QTableWidgetItem(str(r['id'])))
            self.tbl_reminders.setItem(i,1,QTableWidgetItem(r['title']))
            self.tbl_reminders.setItem(i,2,QTableWidgetItem(r['message']))
            self.tbl_reminders.setItem(i,3,QTableWidgetItem(r['run_at']))
            self.tbl_reminders.setItem(i,4,QTableWidgetItem(r['repeat']))
            self.tbl_reminders.setItem(i,5,QTableWidgetItem(str(bool(r['enabled']))))

    def add_reminder_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Nuevo Recordatorio")
        dlg.setFixedSize(420,240)
        layout = QVBoxLayout(dlg)
        form = QFormLayout()
        title = QLineEdit()
        message = QLineEdit()
        dt = QDateTimeEdit()
        dt.setCalendarPopup(True)
        dt.setDateTime(datetime.now())
        repeat = QComboBox()
        repeat.addItems(["once","daily","weekly","hourly"])
        form.addRow("Título:", title)
        form.addRow("Mensaje:", message)
        form.addRow("Fecha y hora:", dt)
        form.addRow("Repetir:", repeat)
        layout.addLayout(form)
        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar"); btn_cancel.clicked.connect(dlg.reject)
        btn_ok = QPushButton("Guardar"); btn_ok.setObjectName("btn_success")
        def on_save():
            run_at = dt.dateTime().toString(Qt.ISODate)
            rid = self.db.add_reminder(title.text(), message.text(), run_at, repeat.currentText())
            self.sync_reminders_from_db()
            self.refresh_reminders_table()
            dlg.accept()
        btn_ok.clicked.connect(on_save)
        btns.addWidget(btn_cancel); btns.addWidget(btn_ok)
        layout.addLayout(btns)
        dlg.exec()

    def delete_selected_reminder(self):
        items = self.tbl_reminders.selectedItems()
        if not items: QMessageBox.warning(self, "Error", "Seleccione un recordatorio."); return
        row = items[0].row()
        rid = int(self.tbl_reminders.item(row,0).text())
        if QMessageBox.question(self, "Eliminar", "¿Eliminar este recordatorio?") == QMessageBox.Yes:
            self.db.delete_reminder(rid)
            job_id = f"reminder_{rid}"
            try:
                self.reminder_manager.scheduler.remove_job(job_id)
            except Exception:
                pass
            self.refresh_reminders_table()

    def toggle_reminder_enabled(self):
        items = self.tbl_reminders.selectedItems()
        if not items: QMessageBox.warning(self, "Error", "Seleccione un recordatorio."); return
        row = items[0].row()
        rid = int(self.tbl_reminders.item(row,0).text())
        cur = self.db.get_connection().cursor().execute("SELECT enabled FROM reminders WHERE id=?", (rid,)).fetchone()
        if cur:
            new = 0 if cur['enabled'] else 1
            with self.db.get_connection() as conn:
                conn.cursor().execute("UPDATE reminders SET enabled=? WHERE id=?", (new, rid))
            if new:
                self.sync_reminders_from_db()
            else:
                try:
                    self.reminder_manager.scheduler.remove_job(f"reminder_{rid}")
                except Exception:
                    pass
            self.refresh_reminders_table()

    def open_global_search_from_nav(self):
        text = self.nav_search.text().strip()
        if text:
            # Reutilizar el diálogo de búsqueda pero pre-rellenado o llamar directamente a la función
            self.open_global_search_dialog(prefill=text)
            self.nav_search.clear()

    def open_global_search_dialog(self, prefill=""):
        dlg = QDialog(self)
        dlg.setWindowTitle("Búsqueda Global (Ctrl+K)")
        dlg.setFixedSize(600,400)
        v = QVBoxLayout(dlg)
        le = QLineEdit(); le.setPlaceholderText("Buscar (productos, clientes, transacciones)"); le.setClearButtonEnabled(True)
        if prefill:
            le.setText(prefill)
        listw = QListWidget()
        v.addWidget(le); v.addWidget(listw)
        
        def do_search():
            q = le.text().strip()
            if not q: return
            self.build_search_index()
            res = self.global_search.search(q, limit=50)
            listw.clear()
            for r in res:
                item = QListWidgetItem(f"[{r['type']}] {r['meta'].get('name', r['meta'].get('descripcion', ''))}  ({r['score']:.0f})")
                item.setData(Qt.UserRole, r)
                listw.addItem(item)
        
        le.textChanged.connect(do_search) # Buscar mientras escribe
        if prefill: do_search()

        def on_activate(item):
            r = item.data(Qt.UserRole)
            if r['type'] == 'transaction':
                txid = int(r['id'].split('_',1)[1])
                dlg2 = TransactionDialog(self, self.db, tx_id=txid); dlg2.exec(); self.refresh_ui()
            elif r['type'] == 'pendiente':
                # Navigate to pendientes page and select row
                self.pages.setCurrentWidget(self.page_pendientes)
                self.refresh_ui()
            dlg.accept()
        listw.itemActivated.connect(on_activate)
        dlg.exec()

    def build_search_index(self):
        items = []
        # transacciones
        rows = self.db.get_connection().cursor().execute("SELECT id, descripcion FROM transacciones").fetchall()
        for r in rows:
            items.append({'id': f"tx_{r['id']}", 'type': 'transaction', 'name': str(r['id']), 'description': r['descripcion'], 'meta': {'descripcion': r['descripcion']}})
        rows = self.db.get_connection().cursor().execute("SELECT id, cliente, descripcion FROM pendientes").fetchall()
        for r in rows:
            items.append({'id': f"pend_{r['id']}", 'type': 'pendiente', 'name': r['cliente'], 'description': r['descripcion'], 'meta': {'cliente': r['cliente'], 'descripcion': r['descripcion']}})
        # La tabla "metas" ya no existe/usa, por lo que no la indexamos.
        self.global_search.index_items(items)
    # --- MOVIMIENTOS ---
    def open_transaction_dialog(self):
        dlg = TransactionDialog(self, self.db)
        if dlg.exec():
            self.refresh_ui()

    def load_transactions_table(self):
        # Asegurarse de que la tabla tenga 8 columnas para incluir el botón de detalle si es necesario
        if self.table_mov.columnCount() < 8:
            self.table_mov.setColumnCount(8)
            self.table_mov.setHorizontalHeaderLabels(["ID", "Fecha", "Descripción", "Monto ($)", "Monto (Bs)", "Categoría", "Tipo", "Detalle"])

        filter_txt = self.search_bar.text().lower()
        df = self.db.get_dataframe()
        
        if filter_txt:
            # Intentar búsqueda rápida usando FTS index
            try:
                refs = self.db.search_fts(filter_txt, limit=200)
                tx_ids = [int(r['ref'].split('_',1)[1]) for r in refs if r['ref'].startswith('tx_')]
                if tx_ids:
                    df = df[df['id'].isin(tx_ids)]
                else:
                    df = df[df['descripcion'].str.lower().str.contains(filter_txt, na=False)]
            except Exception:
                df = df[df['descripcion'].str.lower().str.contains(filter_txt, na=False)]
            
        self.table_mov.setRowCount(len(df))
        for i, row in df.iterrows():
            desc = str(row['descripcion'])
            self.table_mov.setItem(i, 0, QTableWidgetItem(str(row['id'])))
            self.table_mov.setItem(i, 1, QTableWidgetItem(row['fecha']))
            self.table_mov.setItem(i, 2, QTableWidgetItem(desc))
            self.table_mov.setItem(i, 3, QTableWidgetItem(f"{row['monto_usdt']:,.2f}"))
            self.table_mov.setItem(i, 4, QTableWidgetItem(f"{row['monto_ves']:,.2f}"))
            self.table_mov.setItem(i, 5, QTableWidgetItem(row['categoria']))
            
            # Colorear Tipo
            tipo_item = QTableWidgetItem(row['tipo'])
            if row['tipo'] == 'INGRESO': tipo_item.setForeground(QColor("#10b981"))
            else: tipo_item.setForeground(QColor("#ef4444"))
            self.table_mov.setItem(i, 6, tipo_item)

            # Detectar si es una venta para mostrar botón de detalle
            if "Venta #" in desc:
                match = re.search(r'Venta #(\d+)', desc)
                if match:
                    v_id = match.group(1)
                    btn_det = QPushButton("🛒 Ver Venta")
                    btn_det.setObjectName("btn_outline")
                    btn_det.setFixedHeight(30)
                    btn_det.clicked.connect(lambda _, vid=v_id: self.show_venta_detalle(vid))
                    self.table_mov.setCellWidget(i, 7, btn_det)
                else:
                    self.table_mov.setCellWidget(i, 7, QWidget()) # Celda vacía
            else:
                self.table_mov.setCellWidget(i, 7, QWidget()) # Celda vacía

    def export_transactions_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar CSV", f"transacciones_{datetime.now().strftime('%Y%m%d')}.csv", "CSV Files (*.csv)")
        if path:
            try:
                df = self.db.get_dataframe()
                df.to_csv(path, index=False)
                QMessageBox.information(self, "Éxito", f"Exportadas {len(df)} filas a {path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudo exportar: {e}")

    def export_transactions_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar Excel", f"transacciones_{datetime.now().strftime('%Y%m%d')}.xlsx", "Excel Files (*.xlsx)")
        if path:
            try:
                df = self.db.get_dataframe()
                df.to_excel(path, index=False)
                QMessageBox.information(self, "Éxito", f"Exportadas {len(df)} filas a {path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudo exportar a Excel: {e}")

    def import_transactions_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importar CSV", "", "CSV Files (*.csv)")
        if path:
            try:
                df = pd.read_csv(path)
                if not {'descripcion','monto_usdt'}.issubset(set(df.columns)):
                    QMessageBox.warning(self, "Error", "CSV debe contener al menos las columnas: descripcion, monto_usdt")
                    return
                self.db.import_transactions_from_df(df)
                self.refresh_ui()
                QMessageBox.information(self, "Éxito", f"Importadas {len(df)} filas desde {path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error al importar: {e}")

    def get_selected_transaction_id(self):
        items = self.table_mov.selectedItems()
        if not items:
            return None
        row = items[0].row()
        id_item = self.table_mov.item(row, 0)
        try:
            return int(id_item.text()) if id_item else None
        except:
            return None

    def edit_selected_transaction(self):
        tx_id = self.get_selected_transaction_id()
        if not tx_id:
            QMessageBox.warning(self, "Error", "Seleccione una transacción para editar.")
            return
        dlg = TransactionDialog(self, self.db, tx_id=tx_id)
        if dlg.exec():
            self.refresh_ui()

    def delete_selected_transaction(self):
        tx_id = self.get_selected_transaction_id()
        if not tx_id:
            QMessageBox.warning(self, "Error", "Seleccione una transacción para eliminar.")
            return
        if QMessageBox.question(self, "Eliminar", "¿Confirmar eliminación de la transacción?") == QMessageBox.Yes:
            self.db.delete_transaction(tx_id)
            self.refresh_ui()

    # --- PENDIENTES ---
    def calc_p_ves_to_usdt(self):
        if self.p_monto_ves.hasFocus():
            try:
                t = self.db.get_tasa()
                v = float(self.p_monto_ves.text())
                self.p_monto.setText(f"{v/t:.2f}")
            except: self.p_monto.clear()

    def calc_p_usdt_to_ves(self):
        if self.p_monto.hasFocus():
            try:
                t = self.db.get_tasa()
                u = float(self.p_monto.text())
                self.p_monto_ves.setText(f"{u*t:.2f}")
            except: self.p_monto_ves.clear()

    def add_pendiente(self):
        try:
            cli = self.p_cliente.text()
            monto = float(self.p_monto.text())
            desc = self.p_desc.text()
            if not cli or monto <= 0: raise ValueError
            
            self.db.add_pendiente(cli, monto, desc)
            self.p_cliente.clear(); self.p_monto.clear(); self.p_monto_ves.clear(); self.p_desc.clear()
            self.refresh_ui()
            QMessageBox.information(self, "Éxito", "Deuda registrada.")
        except ValueError:
            QMessageBox.warning(self, "Error", "Datos inválidos (asegúrese de ingresar un monto).")

    def load_pendientes_table(self):
        rows = self.db.get_connection().cursor().execute("SELECT * FROM pendientes WHERE estado='PENDIENTE'").fetchall()
        self.table_pend.setRowCount(len(rows))
        
        for i, row in enumerate(rows):
            tasa = self.db.get_tasa()
            monto_total = float(row['monto_usdt'])
            pagado = float(row['monto_pagado']) if row['monto_pagado'] is not None else 0.0
            saldo = monto_total - pagado
            saldo_ves = saldo * tasa

            self.table_pend.setItem(i, 0, QTableWidgetItem(str(row['id'])))
            self.table_pend.setItem(i, 1, QTableWidgetItem(row['cliente']))
            self.table_pend.setItem(i, 2, QTableWidgetItem(f"{monto_total:,.2f} $"))
            self.table_pend.setItem(i, 3, QTableWidgetItem(f"{pagado:,.2f} $"))
            self.table_pend.setItem(i, 4, QTableWidgetItem(f"{saldo:,.2f} $"))
            self.table_pend.setItem(i, 5, QTableWidgetItem(f"{saldo_ves:,.2f} Bs"))
            self.table_pend.setItem(i, 6, QTableWidgetItem(row['fecha']))

            # Crear celda con dos botones: Registrar Pago Parcial y Ver Historial
            widget = QWidget()
            h = QHBoxLayout(widget)
            h.setContentsMargins(0,0,0,0)
            btn_reg = QPushButton("Registrar Pago")
            btn_reg.setObjectName("btn_success")
            btn_reg.clicked.connect(lambda _, r=row: self.register_partial_payment_dialog(r))
            btn_hist = QPushButton("Historial")
            btn_hist.clicked.connect(lambda _, r=row: self.view_pendiente_history(r))
            h.addWidget(btn_reg)
            h.addWidget(btn_hist)
            self.table_pend.setCellWidget(i, 7, widget)

    def cobrar_pendiente(self, row):
        """Cobrar el monto restante de una deuda (si corresponde)."""
        monto_total = float(row['monto_usdt'])
        pagado = float(row['monto_pagado']) if row['monto_pagado'] is not None else 0.0
        restante = monto_total - pagado
        if restante <= 0:
            QMessageBox.information(self, "Info", "La deuda ya está cubierta.")
            # Asegurar estado
            self.db.marcar_pendiente_pagado(row['id'])
            self.refresh_ui()
            return

        reply = QMessageBox.question(self, "Confirmar Cobro",
                                   f"¿Confirmar que {row['cliente']} ha pagado {restante:.2f} $?",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                # Registrar pago parcial por el restante (marcará PAGADO si queda en 0)
                aplicado = self.db.add_partial_payment(row['id'], restante, metodo='Cobro final', nota='Cobro completado (UI)')
                tasa = self.db.get_tasa()
                desc = f"Cobro deuda: {row['cliente']} - {row['descripcion']}"
                self.db.add_transaction(desc, aplicado, aplicado * tasa, "Ventas", "INGRESO")
                self.refresh_ui()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudo registrar el cobro: {e}")

    def register_partial_payment_dialog(self, row):
        """Diálogo para registrar un pago parcial sobre una deuda."""
        monto_total = float(row['monto_usdt'])
        pagado = float(row['monto_pagado']) if row['monto_pagado'] is not None else 0.0
        restante = monto_total - pagado
        if restante <= 0:
            QMessageBox.information(self, "Info", "No hay saldo pendiente para pagar.")
            return
        monto, ok = QInputDialog.getDouble(self, "Registrar Pago Parcial", f"Restante: {restante:.2f} $\nMonto a registrar:", 0.00, 0.01, restante, 2)
        if not ok or monto <= 0:
            return
        metodo, ok2 = QInputDialog.getText(self, "Método de Pago", "Método (opcional):")
        if not ok2: metodo = ''
        nota, ok3 = QInputDialog.getText(self, "Nota", "Nota (opcional):")
        if not ok3: nota = ''
        try:
            aplicado = self.db.add_partial_payment(row['id'], monto, metodo, nota)
            tasa = self.db.get_tasa()
            desc = f"Pago parcial: {row['cliente']} - {row['descripcion']}"
            self.db.add_transaction(desc, aplicado, aplicado * tasa, "Ventas", "INGRESO")
            QMessageBox.information(self, "Éxito", f"Pago registrado: {aplicado:.2f} $")
            self.refresh_ui()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def view_pendiente_history(self, row):
        payments = self.db.get_payments_for_pendiente(row['id'])
        dlg = PaymentHistoryDialog(payments, self)
        dlg.exec()

    # --- METAS ---
    # Funciones de metas eliminadas; se mantiene el encabezado para legibilidad.
    def add_meta(self):
        pass

    def load_metas_list(self):
        # Metas ya no se usan; esta función no hace nada.
        return

    def abonar_meta(self, meta):
        # Funcionalidad de ahorro quitada
        pass

    def delete_meta(self, mid):
        # Ya no hay meta que eliminar
        pass

    # --- CONFIG ---
    def update_tasa_global(self):
        try:
            nt = float(self.cfg_tasa.text())
            self.db.set_tasa(nt)
            QMessageBox.information(self, "Éxito", "Tasa (legacy/USDT) actualizada.")
        except: QMessageBox.warning(self, "Error", "Tasa inválida.")

    def update_tasa_usdt_ui(self):
        try:
            rate = self.db.update_tasa_usdt_from_api()
            self.cfg_tasa_usdt.setText(str(rate))
            self.cfg_tasa.setText(str(rate))
            QMessageBox.information(self, "Éxito", f"Tasa USDT actualizada desde API: {rate:.2f} VES/USDT")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo actualizar tasa USDT: {e}")

    def save_tasa_usdt_ui(self):
        try:
            nt = float(self.cfg_tasa_usdt.text())
            self.db.set_tasa_usdt(nt)
            QMessageBox.information(self, "Éxito", f"Tasa USDT guardada manualmente: {nt:.2f} VES/USDT")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Tasa USDT inválida o campo vacío: {e}")

    def tasa_mode_changed_ui(self):
        mode = self.cb_tasa_mode.currentData()
        self.db.set_tasa_mode(mode)
        self._apply_tasa_mode_to_ui()

    def _apply_tasa_mode_to_ui(self):
        mode = self.db.get_tasa_mode()
        if mode == 'api':
            # cuando API está activo, permitir actualización automática
            self.btn_upd_tasa_usdt.setEnabled(True)
            self.btn_save_tasa_usdt.setEnabled(False)
        else:
            # modo manual: permitir guardar y desactivar botón API
            self.btn_upd_tasa_usdt.setEnabled(False)
            self.btn_save_tasa_usdt.setEnabled(True)

    def update_tasa_bcv_ui(self):
        """Guardar manualmente la tasa BCV (entrada por usuario)."""
        try:
            nt = float(self.cfg_tasa_bcv.text())
            self.db.set_tasa_bcv(nt)
            QMessageBox.information(self, "Éxito", f"Tasa BCV guardada: {nt:.2f} VES/USD")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Tasa BCV inválida o campo vacío: {e}")

    # Handler para crear usuarios eliminado.

    def create_backup(self):
        f, _ = QFileDialog.getSaveFileName(self, "Guardar Backup", f"backup_{datetime.now().strftime('%Y%m%d')}.db", "DB Files (*.db)")
        if f:
            shutil.copy(self.db.db_name, f)
            QMessageBox.information(self, "Éxito", "Copia creada.")

    def export_data_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar Datos (JSON)", f"export_{datetime.now().strftime('%Y%m%d')}.json", "JSON Files (*.json)")
        if path:
            try:
                self.db.export_db_to_json(path)
                QMessageBox.information(self, "Éxito", f"Datos exportados a {path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudo exportar: {e}")

    def import_data_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importar Datos (JSON)", "", "JSON Files (*.json)")
        if path:
            if QMessageBox.question(self, "Importar", "Se aplicará INSERT OR REPLACE en las tablas existentes. Continuar?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                try:
                    counts = self.db.import_db_from_json(path)
                    msg = "\n".join([f"{t}: {n} filas" for t,n in counts.items()])
                    QMessageBox.information(self, "Éxito", f"Importación completada:\n{msg}")
                    self.refresh_ui()
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"No se pudo importar: {e}")

    def import_from_old_db(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importar desde DB antigua", "", "DB Files (*.db)")
        if path:
            if QMessageBox.question(self, "Importar DB", "Se importarán tablas desde la DB antigua y se aplicará INSERT OR REPLACE en las tablas existentes. Continuar?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                try:
                    counts = self.db.import_from_sqlite_file(path)
                    msg = "\n".join([f"{t}: {n} filas" for t,n in counts.items()])
                    QMessageBox.information(self, "Éxito", f"Importación DB completada:\n{msg}")
                    self.refresh_ui()
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"No se pudo importar la DB: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Fuentes y Estilos Globales
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    # Aplicar stylesheet global para asegurar estilos en diálogos nativos
    app.setStyleSheet(get_stylesheet("light"))
    
    # Paleta dinámica manejada desde el stylesheet nativo
    app.setStyle("Fusion")
    
    # Pre-condicionar variables Theming para primer inicio
    window = MainWindow()
    window.theme_mode = 'light'
    window.show()
    sys.exit(app.exec())
