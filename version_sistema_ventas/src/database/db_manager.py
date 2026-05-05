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

class DatabaseManager:
    def __init__(self, db_name="finanzas_pro.db"):
        # En el ejecutable empaquetado, sys.executable apunta al .exe y
        # os.path.dirname nos da la carpeta raíz del paquete dist.
        # En desarrollo normal, __file__ da la carpeta del script.
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_name = os.path.join(base_dir, db_name)

        # Conexión persistente con optimizaciones de rendimiento
        self._conn = sqlite3.connect(self.db_name, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")    # Write-Ahead Logging – lecturas no bloquean escrituras
        self._conn.execute("PRAGMA synchronous=NORMAL")  # Más rápido, suficientemente seguro
        self._conn.execute("PRAGMA cache_size=-8000")    # 8 MB de caché de página en RAM
        self._conn.execute("PRAGMA temp_store=MEMORY")   # Tablas temporales en RAM
        self._conn.execute("PRAGMA mmap_size=268435456") # Memory-mapped I/O 256 MB

        # Caché en memoria para evitar queries redundantes
        self._rate_cache = {}          # {'bcv': float, 'usdt': float, 'mode': str}
        self._config_cache = {}        # {clave: valor}  cache general de config
        self._config_dirty = True      # fuerza recarga en primer acceso
        self._invalidate_cache()
        self.exchange = ExchangeRates(ttl=3600)  # Agregado para usar en update_tasa_from_api
        self.init_tables()

    def get_connection(self):
        """Retorna la conexión persistente configurada."""
        return self._conn

    def _invalidate_cache(self):
        """Limpia las cachés en memoria. Llamar después de escribir config."""
        self._rate_cache.clear()
        self._config_cache.clear()
        self._config_dirty = True

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
                stock INTEGER DEFAULT 0, categoria TEXT,
                destacado INTEGER DEFAULT 0)''')

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
                categoria TEXT DEFAULT 'Servicios',
                destacado INTEGER DEFAULT 0)''')

            # Actualizar Detalle Ventas para soportar servicios
            try:
                cursor.execute("ALTER TABLE detalle_ventas ADD COLUMN servicio_id INTEGER")
            except: pass

            # Migraciones para columnas nuevas
            try:
                cursor.execute("ALTER TABLE inventario ADD COLUMN destacado INTEGER DEFAULT 0")
            except: pass
            try:
                cursor.execute("ALTER TABLE servicios ADD COLUMN destacado INTEGER DEFAULT 0")
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
        if 'bcv' in self._rate_cache:
            return self._rate_cache['bcv']
        conn = self.get_connection()
        val = conn.cursor().execute("SELECT valor FROM config WHERE clave='tasa_bcv'").fetchone()
        result = float(val['valor']) if val else 60.0
        self._rate_cache['bcv'] = result
        return result

    def set_tasa_bcv(self, nueva_tasa):
        conn = self.get_connection()
        conn.cursor().execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('tasa_bcv', ?)", (str(nueva_tasa),))
        conn.commit()
        self._rate_cache['bcv'] = float(nueva_tasa)
        self._config_cache['tasa_bcv'] = str(nueva_tasa)

    def get_tasa_usdt(self):
        if 'usdt' in self._rate_cache:
            return self._rate_cache['usdt']
        conn = self.get_connection()
        val = conn.cursor().execute("SELECT valor FROM config WHERE clave='tasa_usdt'").fetchone()
        result = float(val['valor']) if val else 60.0
        self._rate_cache['usdt'] = result
        return result

    def set_tasa_usdt(self, nueva_tasa):
        conn = self.get_connection()
        conn.cursor().execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('tasa_usdt', ?)", (str(nueva_tasa),))
        conn.commit()
        self._rate_cache['usdt'] = float(nueva_tasa)
        self._config_cache['tasa_usdt'] = str(nueva_tasa)

    def get_tasa_mode(self):
        """Devuelve 'api' o 'manual' (fuente de la tasa USDT)."""
        if 'tasa_mode' in self._config_cache:
            return self._config_cache['tasa_mode']
        conn = self.get_connection()
        val = conn.cursor().execute("SELECT valor FROM config WHERE clave='tasa_mode'").fetchone()
        result = val['valor'] if val else 'api'
        self._config_cache['tasa_mode'] = result
        return result

    def set_tasa_mode(self, mode: str):
        conn = self.get_connection()
        conn.cursor().execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('tasa_mode', ?)", (mode,))
        conn.commit()
        self._config_cache['tasa_mode'] = mode

    def get_config(self, clave, default=""):
        # Usar caché en memoria para evitar lecturas repetidas a disco
        if clave in self._config_cache:
            return self._config_cache[clave]
        conn = self.get_connection()
        val = conn.cursor().execute("SELECT valor FROM config WHERE clave=?", (clave,)).fetchone()
        result = val['valor'] if val else default
        self._config_cache[clave] = result
        return result

    def set_config(self, clave, valor):
        conn = self.get_connection()
        conn.cursor().execute("INSERT OR REPLACE INTO config (clave, valor) VALUES (?, ?)", (clave, str(valor)))
        conn.commit()
        # Actualizar caché en lugar de invalidar todo
        self._config_cache[clave] = str(valor)
        # También limpiar caché de tasas si se cambia una tasa
        if clave in ('tasa_bcv', 'tasa_usdt', 'tasa_ves', 'tasa_mode'):
            self._rate_cache.clear()
    def update_tasa_bcv_from_api(self):
        """Actualiza la tasa BCV desde la API específica de BCV."""
        try:
            er = ExchangeRates()
            rate = er.get_bcv_rate()
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
    def add_product(self, codigo, nombre, descripcion, costo, precio, stock, categoria, destacado=0):
        with self.get_connection() as conn:
            conn.cursor().execute("INSERT INTO inventario (codigo, nombre, descripcion, costo, precio, stock, categoria, destacado) VALUES (?,?,?,?,?,?,?,?)",
                                  (codigo, nombre, descripcion, costo, precio, stock, categoria, destacado))
            conn.commit()

    def update_product(self, pid, codigo, nombre, descripcion, costo, precio, stock, categoria, destacado=0):
        with self.get_connection() as conn:
            conn.cursor().execute("UPDATE inventario SET codigo=?, nombre=?, descripcion=?, costo=?, precio=?, stock=?, categoria=?, destacado=? WHERE id=?",
                                  (codigo, nombre, descripcion, costo, precio, stock, categoria, destacado, pid))
            conn.commit()

    def delete_product(self, pid):
         with self.get_connection() as conn:
            conn.cursor().execute("DELETE FROM inventario WHERE id=?", (pid,))
            conn.commit()

    def get_inventory(self):
        with self.get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM inventario ORDER BY destacado DESC, nombre ASC", conn)

    # --- SERVICIOS ---
    def add_service(self, codigo, nombre, descripcion, precio, categoria="Servicios", destacado=0):
        with self.get_connection() as conn:
            conn.cursor().execute("INSERT INTO servicios (codigo, nombre, descripcion, precio, categoria, destacado) VALUES (?,?,?,?,?,?)",
                                  (codigo, nombre, descripcion, precio, categoria, destacado))
            conn.commit()

    def update_service(self, sid, codigo, nombre, descripcion, precio, categoria, destacado=0):
        with self.get_connection() as conn:
            conn.cursor().execute("UPDATE servicios SET codigo=?, nombre=?, descripcion=?, precio=?, categoria=?, destacado=? WHERE id=?",
                                  (codigo, nombre, descripcion, precio, categoria, destacado, sid))
            conn.commit()

    def delete_service(self, sid):
        with self.get_connection() as conn:
            conn.cursor().execute("DELETE FROM servicios WHERE id=?", (sid,))
            conn.commit()

    def get_services(self):
        with self.get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM servicios ORDER BY destacado DESC, nombre ASC", conn)

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
                # Obtener nombre del cliente para la descripción del movimiento
                cliente_nombre = "Sin Cliente"
                if cliente_id:
                    cliente_row = cur.execute("SELECT nombre FROM clientes WHERE id=?", (cliente_id,)).fetchone()
                    if cliente_row:
                        cliente_nombre = cliente_row['nombre']
                
                desc_venta = f"Venta #{venta_id} - {cliente_nombre}"
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

    def get_venta_header(self, venta_id):
        """Retorna la información de cabecera de la venta (cliente, fecha, total)."""
        query = """
        SELECT v.*, c.nombre as cliente_nombre 
        FROM ventas v 
        LEFT JOIN clientes c ON v.cliente_id = c.id 
        WHERE v.id = ?
        """
        with self.get_connection() as conn:
            row = conn.cursor().execute(query, (venta_id,)).fetchone()
            return dict(row) if row else None

# =============================================================================
# WIDGET: GRÁFICO DONUT (Matplotlib embebido)
# =============================================================================
