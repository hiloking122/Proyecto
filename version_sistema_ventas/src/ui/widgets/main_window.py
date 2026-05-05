# =============================================================================
# IMPORTS - Librerías estándar
# =============================================================================
import sys
import os
import io
import json
import shutil
import logging
import re
import threading
from datetime import datetime

# Terceros: datos
import pandas as pd  # type: ignore

# =============================================================================
# IMPORTS - PySide6 (Qt Framework)
# =============================================================================
from PySide6.QtWidgets import (  # type: ignore
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog, QFrame,
    QScrollArea, QInputDialog, QStackedWidget,
    QDateEdit, QDialog, QFormLayout, QComboBox,
    QAbstractItemView, QListWidget, QButtonGroup,
    QGroupBox, QGridLayout, QCheckBox, QDoubleSpinBox, QSpinBox,
    QDateTimeEdit, QListWidgetItem, QCompleter, QTabWidget,
)
from PySide6.QtCore import Qt, QDate, Signal, QStringListModel  # type: ignore
from PySide6.QtGui import (  # type: ignore
    QColor, QFont, QIcon, QPalette, QTextDocument,
    QPageLayout, QPageSize, QShortcut, QKeySequence,
    QIntValidator, QDoubleValidator,
)
from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog  # type: ignore
import qtawesome as qta  # type: ignore

# =============================================================================
# IMPORTS - Matplotlib (Gráficos)
# =============================================================================
import matplotlib  # type: ignore
try:
    matplotlib.use('QtAgg')
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas  # type: ignore
except Exception:
    matplotlib.use('Qt5Agg')
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas  # type: ignore
from matplotlib.figure import Figure  # type: ignore
import matplotlib.pyplot as plt  # type: ignore
import matplotlib.ticker as ticker  # type: ignore

# =============================================================================
# IMPORTS - Módulos internos del proyecto
# =============================================================================
from src.database.db_manager        import DatabaseManager  # type: ignore
from src.exchange                   import ExchangeRates  # type: ignore
from src.search                     import GlobalSearch  # type: ignore
from src.notifications              import ReminderManager  # type: ignore
from src.styles                     import get_stylesheet  # type: ignore
from src.icons                      import load_icon  # type: ignore
from src.ui.widgets.chart_widget    import ChartWidget  # type: ignore
from src.ui.dialogs.transaction_dialog     import TransactionDialog  # type: ignore
from src.ui.dialogs.payment_history_dialog import PaymentHistoryDialog  # type: ignore
from src.ui.dialogs.sale_details_dialog    import SaleDetailsDialog  # type: ignore
from src.ui.dialogs.client_dialog          import ClientDialog  # type: ignore
from src.ui.dialogs.service_dialog         import ServiceDialog  # type: ignore
from src.ui.dialogs.product_dialog         import ProductDialog  # type: ignore
from src.ui.dialogs.help_dialog            import HelpDialog  # type: ignore

# =============================================================================
# CONSTANTES GLOBALES
# =============================================================================
STYLESHEET = get_stylesheet("light")

class MainWindow(QMainWindow):
    tasa_synced = Signal(float)  # Para actualizar UI desde hilos

    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.tasa_synced.connect(self._on_tasa_synced)
        self.setWindowTitle("💼 Sistema de Ventas - Impresiones Yonathan")
        # Tamaño inicial responsivo: 85% de la pantalla disponible
        screen = QApplication.primaryScreen().availableGeometry()
        init_w = max(800, int(screen.width() * 0.85))
        init_h = max(600, int(screen.height() * 0.85))
        self.resize(init_w, init_h)
        self.setMinimumSize(800, 500)  # Tamaño mínimo para evitar colapso de UI
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
        navbar.setFixedHeight(68)
        navbar.setObjectName("Navbar")
        navbar.setContentsMargins(16, 6, 16, 6)
        nav_layout = QHBoxLayout(navbar)
        nav_layout.setSpacing(8)

        # Logo / Marca
        lbl_brand = QLabel("💼 <b>Impresiones Yonathan</b>")
        lbl_brand.setObjectName("h3")
        lbl_brand.setToolTip("Sistema de Ventas v2.0")

        # ─── Botones de acceso rápido ───
        btn_quick_pos = QPushButton("🛍️ POS")
        btn_quick_pos.setObjectName("btn_success")
        btn_quick_pos.setFixedHeight(36)
        btn_quick_pos.setToolTip("Ir al Punto de Venta (F1)")
        btn_quick_pos.setCursor(Qt.PointingHandCursor)
        btn_quick_pos.clicked.connect(lambda: self.switch_page(1))

        btn_quick_mov = QPushButton("+ Movimiento")
        btn_quick_mov.setObjectName("btn_primary")
        btn_quick_mov.setFixedHeight(36)
        btn_quick_mov.setToolTip("Registrar nuevo ingreso o gasto")
        btn_quick_mov.setCursor(Qt.PointingHandCursor)
        btn_quick_mov.clicked.connect(self.open_transaction_dialog)

        # ─── Barra de búsqueda ───
        self.nav_search = QLineEdit()
        self.nav_search.setObjectName("NavSearch")
        self.nav_search.setPlaceholderText("🔍 Buscar en el sistema... (Ctrl+K)")
        self.nav_search.setToolTip("Buscar productos, clientes, ventas y más (Ctrl+K)")
        self.nav_search.setMinimumWidth(160)
        self.nav_search.setMaximumWidth(500)
        self.nav_search.setFixedHeight(38)

        # ─── Tasa visible en navbar ───
        self.lbl_nav_tasa = QLabel("🏦 BCV: --- | 💵 USD: ---")
        self.lbl_nav_tasa.setStyleSheet(
            "color: #475569; font-size: 11px; background: #f1f5f9; "
            "padding: 5px 12px; border-radius: 14px; font-weight: 700;"
        )
        self.lbl_nav_tasa.setToolTip("Tasas de cambio activas\nHaga clic para actualizar")
        self.lbl_nav_tasa.setCursor(Qt.PointingHandCursor)

        # ─── Status indicator ───
        self.lbl_status = QLabel("🟢 Conectado")
        self.lbl_status.setStyleSheet("color: #10b981; font-weight: 700; font-size: 11px;")
        self.lbl_status.setToolTip("Estado del sistema")

        # ─── Botones de acción ───
        self.btn_theme = QPushButton()
        self.btn_theme.setIcon(qta.icon('fa5s.sun', color='#f59e0b'))
        self.btn_theme.setObjectName("btn_theme")
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.setToolTip("Alternar modo Claro / Oscuro (Ctrl+T)")
        self.btn_theme.setFixedSize(38, 38)
        self.btn_theme.clicked.connect(self.toggle_theme)

        self.btn_help = QPushButton()
        self.btn_help.setIcon(qta.icon('fa5s.question-circle', color='#64748b'))
        self.btn_help.setObjectName("btn_help")
        self.btn_help.setToolTip("Ayuda, Tutorial y Atajos de Teclado (F12)")
        self.btn_help.setCursor(Qt.PointingHandCursor)
        self.btn_help.setFixedSize(38, 38)
        self.btn_help.clicked.connect(self.show_help)

        # ─── Ensamblar navbar ───
        nav_layout.addWidget(lbl_brand)
        nav_layout.addSpacing(12)
        nav_layout.addWidget(btn_quick_pos)
        nav_layout.addWidget(btn_quick_mov)
        nav_layout.addStretch()
        nav_layout.addWidget(self.nav_search)
        nav_layout.addSpacing(10)
        nav_layout.addWidget(self.lbl_nav_tasa)
        nav_layout.addSpacing(6)
        nav_layout.addWidget(self.lbl_status)
        nav_layout.addSpacing(4)
        nav_layout.addWidget(self.btn_theme)
        nav_layout.addWidget(self.btn_help)

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
        # Ancho responsivo: 15% de pantalla, entre 180 y 260px
        screen_w = QApplication.primaryScreen().availableGeometry().width()
        sidebar_w = max(180, min(260, int(screen_w * 0.15)))
        self.sidebar.setFixedWidth(sidebar_w)

        # Agregar contenido al right_layout
        right_layout.addWidget(self.pages)

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(right_container)

        # Configurar Hotkeys Globales
        self.setup_hotkeys()

        # Índice de búsqueda: marcar como sucio para reconstruir al primer uso
        self._search_index_dirty = True
        
        # Background services: exchange sync, reminders, global search
        self.setup_background_tasks()
        
        # Conectar Buscador Navbar
        self.nav_search.returnPressed.connect(self.open_global_search_from_nav)
        
        # Aplicar visibilidad inicial del sidebar
        self.refresh_sidebar()
        
        self.refresh_all()

    # -----------------------------
    # Tema e icon helper
    # -----------------------------
    def load_icon(self, name: str) -> QIcon:
        """Busca el icono en assets/icons/{name}.png y devuelve QIcon, o vacío si no existe."""
        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS  # type: ignore
        else:
            base_dir = os.path.dirname(os.path.dirname(__file__))
            
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
            for s in self.shortcuts:
                try:
                    s.setEnabled(False)
                    s.deleteLater()
                except Exception:
                    pass

        self.shortcuts = []

        # --- Atajos de NAVEGACIÓN contextuales (configurables desde BD) ---
        # F1: Si estamos en POS → mostrar pestaña Productos; si no → ir a POS
        # F2: Si estamos en POS → mostrar pestaña Servicios; si no → ir a Movimientos
        hk_pos  = self.db.get_config('hk_pos', 'F1') or 'F1'
        hk_mov  = self.db.get_config('hk_movimientos', 'F2') or 'F2'
        hk_rep  = self.db.get_config('hk_reportes', 'F3') or 'F3'
        hk_inv  = self.db.get_config('hk_inventory', 'F4') or 'F4'

        def _f1_action():
            if self.pages.currentIndex() == 1:
                self._pos_show_productos()
            else:
                self.switch_page(1)

        def _f2_action():
            if self.pages.currentIndex() == 1:
                self._pos_show_servicios()
            else:
                self.switch_page(2)

        nav_hotkeys = [
            (hk_pos, _f1_action),
            (hk_mov, _f2_action),
            (hk_rep, lambda: self.switch_page(7)),
            (hk_inv, lambda: self.switch_page(4)),
        ]
        for hk, action in nav_hotkeys:
            try:
                s = QShortcut(QKeySequence(hk), self)
                s.setContext(Qt.ApplicationShortcut)
                s.activated.connect(action)
                self.shortcuts.append(s)
            except Exception as e:
                logging.warning(f"Hotkey '{hk}' no pudo registrarse: {e}")

        # Atajo de checkout configurable
        hk_checkout = self.db.get_config('hk_checkout', 'F5') or 'F5'
        try:
            s_co = QShortcut(QKeySequence(hk_checkout), self)
            s_co.setContext(Qt.ApplicationShortcut)
            s_co.activated.connect(self.process_pos_sale)
            self.shortcuts.append(s_co)
        except Exception:
            pass

        # --- Atajos FIJOS ---
        fixed_actions = [
            ("F7",     lambda: self.switch_page(1)),   # POS alternativo
            ("F10",    lambda: self.switch_page(8)),   # Calculadora
            ("F12",    self.show_help),
            ("Ctrl+T", self.toggle_theme),
            ("Ctrl+L", self.clear_pos_cart),
            ("Ctrl+F", self.focus_search),
            ("+",      lambda: self.adjust_pos_cart_qty(1)),
            ("-",      lambda: self.adjust_pos_cart_qty(-1)),
            ("Del",    self.remove_selected_from_cart),
            # Atajos inambiguos para tabs del POS
            ("Ctrl+1", self._pos_show_productos),
            ("Ctrl+2", self._pos_show_servicios),
        ]

        for keys, callback in fixed_actions:
            try:
                s = QShortcut(QKeySequence(keys), self)
                s.setContext(Qt.ApplicationShortcut)
                s.activated.connect(callback)
                self.shortcuts.append(s)
            except Exception:
                pass

        # Ctrl+K siempre registrado con ApplicationShortcut (funciona con inputs activos)
        try:
            sc_k = QShortcut(QKeySequence("Ctrl+K"), self)
            sc_k.setContext(Qt.ApplicationShortcut)
            sc_k.activated.connect(self.open_global_search_dialog)
            self.shortcuts.append(sc_k)
        except Exception:
            pass


    def _pos_show_productos(self):
        """Alterna el POS para mostrar la vista de Productos (F1 en POS)."""
        if hasattr(self, 'btn_pos_prod'):
            self.btn_pos_prod.setChecked(True)
            self.filter_pos_products()

    def _pos_show_servicios(self):
        """Alterna el POS para mostrar la vista de Servicios (F2 en POS)."""
        if hasattr(self, 'btn_pos_svc'):
            self.btn_pos_svc.setChecked(True)
            self.filter_pos_products()

    def adjust_pos_cart_qty(self, delta):
        """Ajusta la cantidad del item seleccionado en el carrito del POS."""
        if self.pages.currentIndex() != 1: return # Solo en POS
        
        row = self.pos_cart_table.currentRow()
        if 0 <= row < len(self.pos_cart):
            # Obtener el spinbox de la celda
            widget = self.pos_cart_table.cellWidget(row, 1)
            if isinstance(widget, QSpinBox):
                new_val = widget.value() + delta
                if new_val >= 1:
                    widget.setValue(new_val)
                    # update_cart_qty se activa por el signal valueChanged del spinbox

    def remove_selected_from_cart(self):
        """Borra la fila seleccionada del carrito."""
        if self.pages.currentIndex() != 1: return
        row = self.pos_cart_table.currentRow()
        if 0 <= row < len(self.pos_cart):
            # Confirmación rápida para Delete? No, para velocidad mejor directo o simple aviso
            self.remove_from_cart(row)

    def show_help(self):
        HelpDialog(self).exec()

    def focus_search(self):
        """Pone el foco en el buscador de la página actual."""
        idx = self.pages.currentIndex()
        if idx == 1: # POS
            self.pos_search.setFocus()
            self.pos_search.selectAll()
        elif idx == 2: # Movimientos
            self.search_bar.setFocus()
            self.search_bar.selectAll()
        else:
            self.nav_search.setFocus()
            self.nav_search.selectAll()

    def clear_pos_cart(self):
        """Limpia el carrito del POS con confirmación."""
        if not self.pos_cart: return
        res = QMessageBox.question(self, "Limpiar Carrito", "¿Está seguro que desea vaciar todo el carrito?", QMessageBox.Yes | QMessageBox.No)
        if res == QMessageBox.Yes:
            self.pos_cart = []
            self.refresh_cart_table()

    def create_sidebar(self):
        """Crea el sidebar con logo, navegación y footer de tasas."""
        # Contenedor principal del sidebar
        sidebar_container = QWidget()
        sidebar_container.setObjectName("SidebarContainer")
        sidebar_container.setStyleSheet(
            "QWidget#SidebarContainer {"
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 #1e293b, stop:1 #0f172a);"
            "border-right: 1px solid #334155; }"
        )
        sc_layout = QVBoxLayout(sidebar_container)
        sc_layout.setContentsMargins(0, 0, 0, 0)
        sc_layout.setSpacing(0)

        # Logo / Marca
        lbl_logo = QLabel("💼 Impresiones")
        lbl_logo.setStyleSheet(
            "color: #f8fafc; font-size: 16px; font-weight: 800; "
            "padding: 18px 18px 4px 18px; letter-spacing: 0.3px;"
        )
        sc_layout.addWidget(lbl_logo)

        lbl_sub = QLabel("Sistema de Ventas")
        lbl_sub.setStyleSheet(
            "color: #4e6b80; font-size: 10px; font-weight: 600; "
            "padding: 0px 18px 12px 18px; letter-spacing: 0.8px; text-transform: uppercase;"
        )
        sc_layout.addWidget(lbl_sub)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #334155; max-height: 1px; margin: 0px;")
        sc_layout.addWidget(sep)

        # Lista de navegación
        list_widget = QListWidget()
        list_widget.setObjectName("Sidebar")
        list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sidebar_list = list_widget

        # Se crea con los elementos pero refresh_sidebar los ocultará si es necesario
        list_widget.addItems([
            "📊  Dashboard",
            "🛍️  Punto de Venta",
            "💸  Movimientos",
            "⌛  Cuentas Pendientes",
            "📦  Inventario",
            "🛠️  Servicios",
            "👥  Clientes",
            "📈  Reportes",
            "🧮  Calculadora",
            "🔔  Notificaciones",
            "⚙️  Configuración"
        ])
        list_widget.currentRowChanged.connect(self.switch_page)
        list_widget.setCurrentRow(0)
        sc_layout.addWidget(list_widget, 1)

        # Footer: tasa de cambio
        footer = QWidget()
        footer.setStyleSheet(
            "background-color: rgba(0,0,0,0.25); border-top: 1px solid #334155;"
        )
        fl = QVBoxLayout(footer)
        fl.setContentsMargins(14, 10, 14, 12)
        fl.setSpacing(3)

        self.lbl_sidebar_bcv = QLabel("🏦 BCV: ---")
        self.lbl_sidebar_bcv.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 700;")
        self.lbl_sidebar_usdt = QLabel("💵 USD: ---")
        self.lbl_sidebar_usdt.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 700;")

        fl.addWidget(self.lbl_sidebar_bcv)
        fl.addWidget(self.lbl_sidebar_usdt)
        
        # Botón para desbloquear secciones protegidas
        btn_unlock = QPushButton("🔒 Modo Administrador")
        btn_unlock.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.05); color: #94a3b8; border: none; "
            "text-align: left; padding: 5px; font-size: 9px; border-radius: 4px; margin-top: 5px; }"
            "QPushButton:hover { background: rgba(30,58,138,0.5); color: #f8fafc; }"
        )
        btn_unlock.clicked.connect(self.unlock_admin_session)
        fl.addWidget(btn_unlock)
        
        sc_layout.addWidget(footer)

        return sidebar_container

    def switch_page(self, index):
        """Cambia la página actual del stacked widget con verificación de acceso admin."""
        # Secciones protegidas según configuración
        labels = {2: 'Movimientos', 4: 'Inventario', 7: 'Reportes'}
        protect_key = {2: 'prot_mov', 4: 'prot_inv', 7: 'prot_rep'}
        
        if isinstance(index, int): # Ensure index is an integer
            if index in protect_key:
                is_protected = self.db.get_config(protect_key[index], '0') == '1'
                if is_protected and not getattr(self, 'admin_unlocked', False):
                    # Pedir contraseña
                    stored_pass = self.db.get_config('admin_pwd', '')
                    if stored_pass:
                        pwd, ok = QInputDialog.getText(self, "Acceso Restringido", 
                                                     f"La sección '{labels[index]}' está protegida.\nIngrese la clave de administrador:", 
                                                     QLineEdit.Password)
                        if not ok: return
                        if pwd != stored_pass:
                            QMessageBox.warning(self, "Error", "Clave incorrecta. Acceso denegado.")
                            return
                        # Desbloquear sesión opcionalmente o solo este acceso
                        self.admin_unlocked = True # Desbloquea hasta reiniciar o cerrar app
                    else:
                        pass

            self.pages.setCurrentIndex(index)
            
            # Actualizar la selección de la lista del sidebar si el cambio vino de fuera
            if hasattr(self, 'sidebar_list') and self.sidebar_list is not None:
                self.sidebar_list.blockSignals(True)
                self.sidebar_list.setCurrentRow(index)
                self.sidebar_list.blockSignals(False)
        self.refresh_ui()

    def refresh_sidebar(self):
        """Oculta o muestra elementos del sidebar según la protección configurada."""
        if not hasattr(self, 'sidebar_list') or not self.sidebar_list: return
        
        # Índices: 2=Movimientos, 4=Inventario, 7=Reportes
        protect_map = {2: 'prot_mov', 4: 'prot_inv', 7: 'prot_rep'}
        is_admin = getattr(self, 'admin_unlocked', False)
        
        for row, config_key in protect_map.items():
            is_protected = self.db.get_config(config_key, '0') == '1'
            # Si está protegido y no somos admin, lo ocultamos
            self.sidebar_list.setRowHidden(row, is_protected and not is_admin)

    def unlock_admin_session(self):
        """Desbloquea las secciones protegidas mediante contraseña."""
        stored_pass = self.db.get_config('admin_pwd', '')
        if not stored_pass:
            QMessageBox.information(self, "Admin", "No hay clave configurada en Configuración.")
            return
            
        pwd, ok = QInputDialog.getText(self, "Modo Administrador", 
                                     "Ingrese clave para mostrar secciones ocultas:", 
                                     QLineEdit.Password)
        if ok and pwd == stored_pass:
            self.admin_unlocked = True
            self.refresh_sidebar()
            QMessageBox.information(self, "Éxito", "Modo Administrador activado. Secciones visibles.")
        elif ok:
            QMessageBox.warning(self, "Error", "Clave incorrecta.")




    # --- PÁGINAS ---

    def setup_dashboard_page(self):
        container = QScrollArea()
        container.setWidgetResizable(True)
        container.setFrameShape(QFrame.NoFrame)
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(18)
        
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
        self.dashboard_charts_widget = QWidget()
        grid_charts = QGridLayout(self.dashboard_charts_widget)
        grid_charts.setContentsMargins(0, 0, 0, 0)
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

        # Darle una altura mínima razonable para que los gráficos no colapsen en pantallas pequeñas
        self.dashboard_charts_widget.setMinimumHeight(450)
        layout.addWidget(self.dashboard_charts_widget, 3)

        # 3.5 COMPACT VIEW
        self.dashboard_compact_widget = QWidget()
        self.dashboard_compact_widget.setMinimumHeight(250)
        compact_layout = QHBoxLayout(self.dashboard_compact_widget)
        compact_layout.setContentsMargins(0, 0, 0, 0)
        self.tbl_compact_invoices = QTableWidget()
        self.tbl_compact_invoices.setColumnCount(4)
        self.tbl_compact_invoices.setHorizontalHeaderLabels(["ID", "Fecha", "Cliente", "Total ($)"])
        self.tbl_compact_invoices.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_compact_invoices.setEditTriggers(QAbstractItemView.NoEditTriggers)
        inv_frame = QFrame(); inv_frame.setObjectName("ContentPanel"); inv_layout = QVBoxLayout(inv_frame)
        inv_layout.addWidget(QLabel("<h2 id='h2'>📄 Últimas 10 Facturas</h2>"))
        inv_layout.addWidget(self.tbl_compact_invoices)
        
        self.tbl_compact_products = QTableWidget()
        self.tbl_compact_products.setColumnCount(3)
        self.tbl_compact_products.setHorizontalHeaderLabels(["Código", "Producto", "Stock"])
        self.tbl_compact_products.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_compact_products.setEditTriggers(QAbstractItemView.NoEditTriggers)
        prod_frame = QFrame(); prod_frame.setObjectName("ContentPanel"); prod_layout = QVBoxLayout(prod_frame)
        prod_layout.addWidget(QLabel("<h2 id='h2'>📦 Productos con Poco Stock</h2>"))
        prod_layout.addWidget(self.tbl_compact_products)

        compact_layout.addWidget(inv_frame, 1)
        compact_layout.addWidget(prod_frame, 1)
        
        layout.addWidget(self.dashboard_compact_widget, 3)

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
        
        container.setWidget(page)
        return container

    def create_kpi_card(self, title, color, val_obj_name="value"):
        card = QFrame()
        card.setObjectName(f"KPIcard_{val_obj_name.replace('value_','')}")
        vbox = QVBoxLayout(card)
        vbox.setSpacing(4)
        vbox.setContentsMargins(16, 14, 16, 14)

        lbl_t = QLabel(title.upper())
        lbl_t.setObjectName("subtitle")

        lbl_v = QLabel("0.00 $")
        lbl_v.setObjectName(val_obj_name)

        vbox.addWidget(lbl_t)
        vbox.addWidget(lbl_v)
        return card

    def setup_movimientos_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20,20,20,20)
        
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
        btn_edit = QPushButton("Editar Reg.")
        btn_edit.clicked.connect(self.edit_selected_transaction)
        btn_view = QPushButton("🔍 Ver Venta")
        btn_view.setObjectName("btn_primary")
        btn_view.clicked.connect(self.view_selected_detail)
        btn_delete = QPushButton("Eliminar")
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
        top_bar.addWidget(btn_view)
        top_bar.addWidget(btn_edit)
        top_bar.addWidget(btn_delete)
        top_bar.addStretch()
        top_bar.addWidget(self.search_bar)
        
        layout.addLayout(top_bar)
        
        # Tabla
        self.table_mov = QTableWidget()
        self.table_mov.setColumnCount(8)
        self.table_mov.setHorizontalHeaderLabels(["ID", "Fecha", "Descripción", "Monto ($)", "Monto (Bs)", "Categoría", "Tipo", "Acción"])
        # Configurar anchos iniciales
        header = self.table_mov.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive) # Permitir ajuste manual
        header.setSectionResizeMode(2, QHeaderView.Stretch)   # Descripción se estira
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents) # Botón se autoajusta
        self.table_mov.setEditTriggers(QAbstractItemView.NoEditTriggers) # Solo lectura
        
        layout.addWidget(self.table_mov)
        return page

    def setup_pendientes_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20,20,20,20)
        
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
        layout.setContentsMargins(20,20,20,20)
        
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
            lbl.setStyleSheet("font-weight: bold; font-size: 15px; color: #1e293b; padding: 2px;")

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
            lbl.setStyleSheet("font-weight: bold; font-size: 14px; color: #1e293b;")
            
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
        
        # NOTA: No se crean QShortcuts locales para F1/F2 aquí.
        # Los hotkeys globales de navegación (F1=POS, F2=Movimientos) ya están
        # registrados en setup_hotkeys(). Usar btn_pos_prod/svc directamente
        # desde la lógica de teclado global evita conflictos.
        
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
        self.pos_table.setColumnCount(7)
        self.pos_table.setHorizontalHeaderLabels(["ID", "Código", "🏷️ Nombre", "🔢 Stock", "💵 USD", "💴 VES", "Acción"])
        self.pos_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.pos_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.pos_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.pos_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.pos_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.pos_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.pos_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        
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
        # Ancho responsivo: 30% de pantalla entre 340 y 500px
        screen_w = QApplication.primaryScreen().availableGeometry().width()
        cart_w = max(340, min(500, int(screen_w * 0.30)))
        right_panel.setMinimumWidth(cart_w)
        right_panel.setMaximumWidth(cart_w + 80)
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
        # F5 ya está registrado globalmente en setup_hotkeys() -> process_pos_sale()
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
        layout.setContentsMargins(20,20,20,20)
        
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
            # Búsqueda más precisa: todos los términos deben estar presentes (AND)
            # Se usa na=False para manejar valores NaN sin crash
            terms = txt.split()
            for term in terms:
                df = df[df['nombre'].str.lower().str.contains(term, na=False) | 
                        df['codigo'].str.lower().str.contains(term, na=False) |
                        df['categoria'].str.lower().str.contains(term, na=False)]
        
        show_ves = self.db.get_config('pos_show_ves', '0') == '1'
        self.pos_table.setColumnHidden(4, not show_ves)
        
        self.pos_table.setRowCount(len(df))
        tasa = self.db.get_tasa()
        for i, row in enumerate(df.to_dict('records')):
            # Crear items
            item_id = QTableWidgetItem(str(row['id']))
            item_cod = QTableWidgetItem(row['codigo'])
            item_nom = QTableWidgetItem(str(row['nombre']))
            
            # Columna Stock (Solo para inventario)
            stock_val = row.get('stock', '∞')
            item_stock = QTableWidgetItem(str(stock_val))
            item_stock.setTextAlignment(Qt.AlignCenter)
            
            item_usd = QTableWidgetItem(f"{row['precio']:.2f} $")
            item_ves = QTableWidgetItem(f"{row['precio'] * tasa:.2f} Bs")
            
            # Aplicar resaltado si es destacado
            if row.get('destacado'):
                item_nom.setText(f"⭐ {row['nombre']}")
                font_bold = QFont("Segoe UI", 10, QFont.Bold)
                bg_color = QColor("#fef3c7")
                fg_color = QColor("#92400e")
                for it in [item_id, item_cod, item_nom, item_stock, item_usd, item_ves]:
                    it.setBackground(bg_color)
                    it.setForeground(fg_color)
                    it.setFont(font_bold)
            
            # Alerta visual si NO hay stock (Solo productos)
            if not is_service_mode and row['stock'] <= 0:
                bg_err = QColor("#fee2e2")
                fg_err = QColor("#ef4444")
                for it in [item_id, item_cod, item_nom, item_stock, item_usd, item_ves]:
                    it.setBackground(bg_err)
                    it.setForeground(fg_err)
                    if it == item_stock:
                        it.setText("⚠️ 0")
                        f_err = it.font()
                        f_err.setBold(True)
                        it.setFont(f_err)

            self.pos_table.setItem(i, 0, item_id)
            self.pos_table.setItem(i, 1, item_cod)
            self.pos_table.setItem(i, 2, item_nom)
            self.pos_table.setItem(i, 3, item_stock)
            self.pos_table.setItem(i, 4, item_usd)
            self.pos_table.setItem(i, 5, item_ves)
            
            btn = QPushButton("➕ Añadir")
            if not is_service_mode and row['stock'] <= 0:
                btn.setEnabled(False)
                btn.setText("❌ Agotado")
                btn.setObjectName("btn_danger")
            else:
                btn.setObjectName("btn_primary")
            
            btn.setCursor(Qt.PointingHandCursor)
            self.pos_table.setColumnWidth(6, 120)
            
            btn.clicked.connect(lambda _, r=row, svc=is_service_mode: self.add_to_cart(r, svc))
            self.pos_table.setCellWidget(i, 6, btn)

    def add_to_cart(self, product, is_service=False):
        # Validar stock si es un producto
        if not is_service:
            stk_disp = product.get('stock', 0)
            if stk_disp <= 0:
                QMessageBox.warning(self, "Sin Stock", f"El producto '{product['nombre']}' no tiene stock disponible.")
                return

        # Buscar si ya está
        for item in self.pos_cart:
            if item['id'] == product['id'] and item.get('is_service', False) == is_service:
                # Validar stock máximo si no es servicio
                if not is_service:
                    if item['cantidad'] + 1 > product.get('stock', 0):
                        QMessageBox.warning(self, "Límite de Stock", 
                                          f"No puedes agregar más de {product['stock']} unidades de '{product['nombre']}'.")
                        return
                        
                item['cantidad'] += 1
                self.refresh_cart_table()
                return
        
        self.pos_cart.append({
            'id': product['id'],
            'nombre': product['nombre'],
            'precio': product['precio'],
            'cantidad': 1,
            'descuento': 0.0,
            'is_service': is_service,
            'stock_available': product.get('stock', 999999) if not is_service else 999999
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
            
            # Cantidad con SpinBox (Solo enteros, sin letras ni decimales)
            spin_qty = QSpinBox()
            max_stk = item.get('stock_available', 9999)
            spin_qty.setRange(1, max_stk if max_stk > 0 else 1)
            spin_qty.setValue(int(item['cantidad']))
            spin_qty.setAlignment(Qt.AlignCenter)
            spin_qty.setFixedWidth(70)
            spin_qty.setStyleSheet(f"font-weight: bold; padding: 2px;")
            spin_qty.valueChanged.connect(lambda val, idx=i: self.update_cart_qty(idx, val))
            self.pos_cart_table.setCellWidget(i, 1, spin_qty)
            
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

    def update_cart_qty(self, index, value):
        """Actualiza la cantidad de un item en el carrito, validando stock."""
        item = self.pos_cart[index]
        if not item.get('is_service', False):
            if value > item.get('stock_available', 999999):
                QMessageBox.warning(self, "Límite de Stock", 
                                  f"Solo hay {item['stock_available']} unidades disponibles.")
                # El spinbox volverá al valor anterior si se maneja adecuadamente o refresh
                self.refresh_cart_table()
                return
        
        item['cantidad'] = value
        self.refresh_cart_table()

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
        for row in df.to_dict('records'):
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
                alert.exec()

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
        for i, row in enumerate(df.to_dict('records')):
            self.tbl_clients.setItem(i, 0, QTableWidgetItem(str(row['id'])))
            self.tbl_clients.setItem(i, 1, QTableWidgetItem(row['nombre']))
            self.tbl_clients.setItem(i, 2, QTableWidgetItem(row['cedula']))
            self.tbl_clients.setItem(i, 3, QTableWidgetItem(row['telefono']))
            self.tbl_clients.setItem(i, 4, QTableWidgetItem(row['direccion']))

    def setup_inventory_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20,20,20,20)
        
        top = QHBoxLayout()
        btn_add = QPushButton("Nuevo Producto"); btn_add.setObjectName("btn_success"); btn_add.clicked.connect(self.add_product_dialog)
        btn_edit = QPushButton("Editar"); btn_edit.clicked.connect(self.edit_product_dialog)
        btn_del = QPushButton("Eliminar"); btn_del.setObjectName("btn_danger"); btn_del.clicked.connect(self.delete_product)
        btn_import_inv = QPushButton("📥 Importar CSV/Excel"); btn_import_inv.clicked.connect(self.import_inventory_file)
        btn_export_inv_xl = QPushButton("📤 Exportar Excel"); btn_export_inv_xl.clicked.connect(self.export_inventory_excel)
        btn_export_inv_csv = QPushButton("📄 Exportar CSV"); btn_export_inv_csv.clicked.connect(self.export_inventory_csv)
        top.addWidget(btn_add); top.addWidget(btn_edit); top.addWidget(btn_del)
        top.addWidget(btn_import_inv); top.addWidget(btn_export_inv_xl); top.addWidget(btn_export_inv_csv)
        top.addStretch()
        layout.addLayout(top)
        
        # Barra de búsqueda para inventario
        search_layout = QHBoxLayout()
        self.inventory_search = QLineEdit()
        self.inventory_search.setPlaceholderText("🔍 Buscar productos por nombre, código o categoría...")
        self.inventory_search.setFixedHeight(35)
        self.inventory_search.textChanged.connect(self.load_inventory_table)
        search_layout.addWidget(self.inventory_search)
        layout.addLayout(search_layout)

        # Alerta de stock (oculta por defecto)
        self.lbl_inv_warning = QLabel("")
        self.lbl_inv_warning.setStyleSheet("background-color: #fee2e2; color: #ef4444; border: 1px solid #fecaca; padding: 10px; border-radius: 8px; font-weight: bold;")
        self.lbl_inv_warning.setVisible(False)
        layout.addWidget(self.lbl_inv_warning)
        
        self.tbl_inv = QTableWidget()
        self.tbl_inv.setColumnCount(9)
        self.tbl_inv.setHorizontalHeaderLabels(["ID", "Código", "Nombre", "Costo $", "Precio $", "Margen %", "Stock", "Categoría", "⭐"])
        hdr = self.tbl_inv.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)   # Nombre se estira
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # ID
        hdr.setSectionResizeMode(8, QHeaderView.ResizeToContents)  # Destacado
        self.tbl_inv.setAlternatingRowColors(True)
        self.tbl_inv.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_inv.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tbl_inv.verticalHeader().setVisible(False)
        self.tbl_inv.setShowGrid(False)
        self.tbl_inv.verticalHeader().setDefaultSectionSize(40)
        self.tbl_inv.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.tbl_inv)
        return page

    def setup_services_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20,20,20,20)
        
        top = QHBoxLayout()
        btn_add = QPushButton("Nuevo Servicio"); btn_add.setObjectName("btn_success"); btn_add.clicked.connect(self.add_service_dialog)
        btn_edit = QPushButton("Editar"); btn_edit.clicked.connect(self.edit_service_dialog)
        btn_del = QPushButton("Eliminar"); btn_del.setObjectName("btn_danger"); btn_del.clicked.connect(self.delete_service)
        btn_import_svc = QPushButton("📥 Importar Excel/CSV"); btn_import_svc.clicked.connect(self.import_services_excel)
        btn_export_svc_xl = QPushButton("📤 Exportar Excel"); btn_export_svc_xl.clicked.connect(self.export_services_excel)
        btn_export_svc_csv = QPushButton("📄 Exportar CSV"); btn_export_svc_csv.clicked.connect(self.export_services_csv)
        top.addWidget(btn_add); top.addWidget(btn_edit); top.addWidget(btn_del)
        top.addWidget(btn_import_svc); top.addWidget(btn_export_svc_xl); top.addWidget(btn_export_svc_csv)
        top.addStretch()
        layout.addLayout(top)
        
        # Barra de búsqueda para servicios
        search_layout = QHBoxLayout()
        self.services_search = QLineEdit()
        self.services_search.setPlaceholderText("🔍 Buscar servicios por nombre, código o categoría...")
        self.services_search.setFixedHeight(35)
        self.services_search.textChanged.connect(self.load_services_table)
        search_layout.addWidget(self.services_search)
        layout.addLayout(search_layout)

        self.tbl_services = QTableWidget()
        self.tbl_services.setColumnCount(6)
        self.tbl_services.setHorizontalHeaderLabels(["ID", "Código", "Nombre", "Precio", "Categoría", "⭐"])
        self.tbl_services.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_services.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        layout.addWidget(self.tbl_services)
        return page

    def setup_reports_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20,20,20,20)
        
        header = QHBoxLayout()
        header.addWidget(QLabel("<h2>📊 Reportes Dinámicos y Analíticas (Cono Monetario)</h2>"))
        header.addStretch()
        self.rep_period = QComboBox()
        self.rep_period.setMinimumWidth(160)
        self.rep_period.setMaximumWidth(220)
        self.rep_period.addItems(["📅 Hoy", "📆 Esta Semana", "📅 Este Mes", "🗓️ Este Año", "♾️ Todo el Tiempo"])
        self.rep_period.currentIndexChanged.connect(self.refresh_reports)
        
        self.rep_search = QLineEdit()
        self.rep_search.setPlaceholderText("🔍 Buscar venta por cliente o ID...")
        self.rep_search.setMinimumWidth(180)
        self.rep_search.setMaximumWidth(400)
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
        btn_refresh.setMinimumWidth(180)
        btn_refresh.clicked.connect(self.refresh_reports)
        
        btn_sales_chart = QPushButton("📊 Ventas por Producto")
        btn_sales_chart.setMinimumWidth(180)
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
        self.tbl_sales.setHorizontalHeaderLabels(["ID", "Fecha", "Cliente", "Total USD", "Método", "Acción"])
        header_sales = self.tbl_sales.horizontalHeader()
        header_sales.setSectionResizeMode(QHeaderView.Interactive)
        header_sales.setSectionResizeMode(2, QHeaderView.Stretch) # Cliente ocupa espacio
        header_sales.setSectionResizeMode(5, QHeaderView.ResizeToContents) # Botón se autoajusta
        self.tbl_sales.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(QLabel("<b>📋 Historial de Ventas - Detalles</b>"))
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
        path, _ = QFileDialog.getSaveFileName(self, "Exportar Inventario (Excel)",
                                              f"inventario_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                              "Excel Files (*.xlsx)")
        if path:
            try:
                df = self.db.get_inventory()
                df.to_excel(path, index=False)
                QMessageBox.information(self, "Éxito", f"Inventario exportado a {path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Fallo al exportar: {e}")

    def export_inventory_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar Inventario (CSV)",
                                              f"inventario_{datetime.now().strftime('%Y%m%d')}.csv",
                                              "CSV Files (*.csv)")
        if path:
            try:
                df = self.db.get_inventory()
                df.to_csv(path, index=False, encoding='utf-8-sig')
                QMessageBox.information(self, "Éxito", f"Inventario CSV exportado a {path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Fallo al exportar CSV: {e}")

    def import_inventory_file(self):
        """Importa productos desde CSV o Excel.
        Columnas esperadas: codigo, nombre, descripcion, costo, precio, stock, categoria, destacado
        """
        path, _ = QFileDialog.getOpenFileName(self, "Importar Inventario (CSV o Excel)", "",
                                              "Archivos (*.csv *.xlsx);;CSV (*.csv);;Excel (*.xlsx)")
        if not path:
            return
        mode = QMessageBox.question(
            self, "Modo de importacion",
            "Seleccione el modo de importacion:\n\n"
            "Si -> REEMPLAZAR todo el inventario existente\n"
            "No -> AGREGAR al inventario actual (sin borrar)",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if mode == QMessageBox.Cancel:
            return
        try:
            if path.lower().endswith('.csv'):
                df = pd.read_csv(path, encoding='utf-8-sig')
            else:
                df = pd.read_excel(path)
            df.columns = [str(c).strip().lower() for c in df.columns]
            if 'nombre' not in df.columns:
                QMessageBox.warning(self, "Error",
                    "El archivo debe tener la columna 'nombre'.\nDetectadas: " + ", ".join(df.columns.tolist()))
                return
            if mode == QMessageBox.Yes:
                with self.db.get_connection() as conn:
                    conn.cursor().execute("DELETE FROM inventario")
                    conn.commit()
            count = 0
            errors = 0
            for row in df.to_dict('records'):
                try:
                    nombre = str(row.get('nombre', '')).strip()
                    if not nombre or nombre.lower() == 'nan':
                        continue
                    codigo = str(row.get('codigo', f"IMP-{count:04d}")).strip()
                    if codigo.lower() == 'nan': codigo = f"IMP-{count:04d}"
                    desc   = str(row.get('descripcion', '')).strip()
                    if desc.lower() == 'nan': desc = ''
                    costo  = float(str(row.get('costo', 0)).replace(',', '.') or 0)
                    precio = float(str(row.get('precio', 0)).replace(',', '.') or 0)
                    stock  = int(float(str(row.get('stock', 0)).replace(',', '.') or 0))
                    cat    = str(row.get('categoria', 'General')).strip()
                    if cat.lower() == 'nan': cat = 'General'
                    dest   = int(float(str(row.get('destacado', 0)).replace(',', '.') or 0))
                    try:
                        self.db.add_product(codigo, nombre, desc, costo, precio, stock, cat, dest)
                    except Exception:
                        with self.db.get_connection() as conn:
                            r2 = conn.cursor().execute("SELECT id FROM inventario WHERE codigo=?", (codigo,)).fetchone()
                            if r2:
                                self.db.update_product(r2['id'], codigo, nombre, desc, costo, precio, stock, cat, dest)
                    count += 1
                except Exception:
                    errors += 1
            msg = f"Importacion completada: {count} producto(s) importados."
            if errors:
                msg += f"\n{errors} fila(s) omitidas por error."
            QMessageBox.information(self, "Importacion completa", msg)
            self.load_inventory_table()
            self.filter_pos_products()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo importar:\n{e}")

    def export_services_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar Servicios (Excel)",
                                              f"servicios_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                              "Excel Files (*.xlsx)")
        if path:
            try:
                df = self.db.get_services()
                df.to_excel(path, index=False)
                QMessageBox.information(self, "Exito", f"Servicios exportados a {path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Fallo al exportar: {e}")

    def export_services_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar Servicios (CSV)",
                                              f"servicios_{datetime.now().strftime('%Y%m%d')}.csv",
                                              "CSV Files (*.csv)")
        if path:
            try:
                df = self.db.get_services()
                df.to_csv(path, index=False, encoding='utf-8-sig')
                QMessageBox.information(self, "Exito", f"Servicios CSV exportados a {path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Fallo al exportar CSV: {e}")

    def import_services_excel(self):
        """Importa servicios desde Excel o CSV.
        Formatos soportados:
        1) Con cabeceras: codigo, nombre, descripcion, precio, categoria
        2) Legacy sin cabecera: col0=nombre, col1=porcentaje, col2=precio
        """
        path, _ = QFileDialog.getOpenFileName(self, "Importar Servicios (Excel o CSV)", "",
                                              "Archivos (*.csv *.xlsx);;CSV (*.csv);;Excel (*.xlsx)")
        if not path:
            return
        mode = QMessageBox.question(
            self, "Modo de importacion",
            "Seleccione el modo de importacion:\n\n"
            "Si -> REEMPLAZAR todos los servicios existentes\n"
            "No -> AGREGAR a los servicios actuales",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if mode == QMessageBox.Cancel:
            return
        try:
            if path.lower().endswith('.csv'):
                df_raw = pd.read_csv(path, encoding='utf-8-sig')
            else:
                df_raw = pd.read_excel(path)
            col_lower = [str(c).strip().lower() for c in df_raw.columns]
            has_header = 'nombre' in col_lower or 'precio' in col_lower
            if mode == QMessageBox.Yes:
                with self.db.get_connection() as conn:
                    conn.cursor().execute("DELETE FROM servicios")
                    conn.commit()
            count = 0
            errors = 0
            if has_header:
                df_raw.columns = col_lower
                for row in df_raw.to_dict('records'):
                    try:
                        nombre = str(row.get('nombre', '')).strip()
                        if not nombre or nombre.lower() == 'nan': continue
                        codigo = str(row.get('codigo', f"SVC-{count:04d}")).strip()
                        if codigo.lower() == 'nan': codigo = f"SVC-{count:04d}"
                        desc   = str(row.get('descripcion', '')).strip()
                        if desc.lower() == 'nan': desc = ''
                        precio = float(str(row.get('precio', 0)).replace(',', '.') or 0)
                        cat    = str(row.get('categoria', 'Servicios')).strip()
                        if cat.lower() == 'nan': cat = 'Servicios'
                        dest   = int(float(str(row.get('destacado', 0)).replace(',', '.') or 0))
                        self.db.add_service(codigo, nombre, desc, precio, cat, dest)
                        count += 1
                    except Exception:
                        errors += 1
            else:
                for row in df_raw.to_dict('records'):
                    try:
                        row_vals = list(row.values())
                        name    = str(row_vals[0]).strip()
                        pct_val = str(row_vals[1]).strip() if len(row_vals) > 1 else ''
                        precio  = float(row_vals[2]) if len(row_vals) > 2 else 0.0
                        if name == 'nan' or name == '': continue
                        full_name = (f"{name} ({pct_val}%)"
                                     if pct_val.replace('.0', '').isdigit()
                                     else f"{name} {pct_val}")
                        if pct_val == 'nan': full_name = name
                        self.db.add_service(f"SVC-{count:04d}", full_name, "Importado de Excel", precio)
                        count += 1
                    except Exception:
                        errors += 1
            msg = f"Importacion completada: {count} servicio(s) importados."
            if errors:
                msg += f"\n{errors} fila(s) omitidas por error."
            QMessageBox.information(self, "Importacion completa", msg)
            self.refresh_ui()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo importar el archivo:\n{e}")

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
        txt = self.services_search.text().lower()
        df = self.db.get_services()
        
        if txt:
            terms = txt.split()
            for term in terms:
                df = df[df['nombre'].str.lower().str.contains(term) | 
                        df['codigo'].str.lower().str.contains(term) |
                        df['categoria'].str.lower().str.contains(term)]
        
        self.tbl_services.setRowCount(len(df))
        for i, row in enumerate(df.to_dict('records')):
            self.tbl_services.setItem(i, 0, QTableWidgetItem(str(row['id'])))
            self.tbl_services.setItem(i, 1, QTableWidgetItem(row['codigo']))
            self.tbl_services.setItem(i, 2, QTableWidgetItem(row['nombre']))
            self.tbl_services.setItem(i, 3, QTableWidgetItem(f"{row['precio']:.2f} $"))
            self.tbl_services.setItem(i, 4, QTableWidgetItem(row['categoria']))
            self.tbl_services.setItem(i, 5, QTableWidgetItem("⭐" if row.get('destacado') == 1 else ""))


    def load_inventory_table(self):
        txt = self.inventory_search.text().lower() if hasattr(self, 'inventory_search') else ""
        df = self.db.get_inventory()

        if txt:
            terms = txt.split()
            for term in terms:
                df = df[
                    df['nombre'].str.lower().str.contains(term, na=False) |
                    df['codigo'].str.lower().str.contains(term, na=False) |
                    df['categoria'].str.lower().str.contains(term, na=False)
                ]

        self.tbl_inv.setRowCount(len(df))

        low_stock_count = 0
        for i, row in enumerate(df.to_dict('records')):
            stk = int(row['stock'])
            costo = float(row['costo'] or 0)
            precio = float(row['precio'] or 0)
            if stk <= 0:
                low_stock_count += 1

            # Calcular margen %
            if costo > 0 and precio >= costo:
                margen = ((precio - costo) / costo) * 100
                margen_txt = f"{margen:.1f}%"
            elif costo > 0:
                margen = ((precio - costo) / costo) * 100
                margen_txt = f"{margen:.1f}%"  # puede ser negativo
            else:
                margen = 0
                margen_txt = "---"

            self.tbl_inv.setItem(i, 0, QTableWidgetItem(str(row['id'])))
            self.tbl_inv.setItem(i, 1, QTableWidgetItem(str(row['codigo'] or '')))
            self.tbl_inv.setItem(i, 2, QTableWidgetItem(str(row['nombre'] or '')))

            cost_item = QTableWidgetItem(f"${costo:.2f}")
            self.tbl_inv.setItem(i, 3, cost_item)

            price_item = QTableWidgetItem(f"${precio:.2f}")
            self.tbl_inv.setItem(i, 4, price_item)

            # Margen con color según rentabilidad
            margin_item = QTableWidgetItem(margen_txt)
            margin_item.setTextAlignment(Qt.AlignCenter)
            if margen >= 25:
                margin_item.setForeground(QColor("#059669"))  # Verde bonito
            elif margen >= 10:
                margin_item.setForeground(QColor("#d97706"))  # Naranja
            elif costo > 0:
                margin_item.setForeground(QColor("#dc2626"))  # Rojo
            self.tbl_inv.setItem(i, 5, margin_item)

            # Stock con alerta visual
            stock_item = QTableWidgetItem(str(stk))
            stock_item.setTextAlignment(Qt.AlignCenter)
            if stk <= 0:
                stock_item.setBackground(QColor("#fee2e2"))
                stock_item.setForeground(QColor("#dc2626"))
                font = stock_item.font()
                font.setBold(True)
                stock_item.setFont(font)
            elif stk <= 5:
                stock_item.setBackground(QColor("#fef3c7"))
                stock_item.setForeground(QColor("#b45309"))
            self.tbl_inv.setItem(i, 6, stock_item)

            self.tbl_inv.setItem(i, 7, QTableWidgetItem(str(row['categoria'] or '')))
            dest_item = QTableWidgetItem("⭐" if row.get('destacado') == 1 else "")
            dest_item.setTextAlignment(Qt.AlignCenter)
            self.tbl_inv.setItem(i, 8, dest_item)

        # Actualizar banner de advertencia
        if hasattr(self, 'lbl_inv_warning'):
            if low_stock_count > 0:
                self.lbl_inv_warning.setText(
                    f"⚠️ ATENCIÓN: Hay {low_stock_count} producto(s) sin stock suficiente. Se recomienda realizar un re-stock.")
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
        ventas_list = self.db.get_ventas()
        sales_df = pd.DataFrame(ventas_list) if ventas_list else pd.DataFrame()
        if not sales_df.empty and 'fecha' in sales_df.columns:
            try:
                sales_df['fecha_datetime'] = pd.to_datetime(sales_df['fecha'])
            except:
                pass
            if 'fecha_datetime' in sales_df.columns:
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
        if not sales_df.empty:
            search_q = self.rep_search.text().lower().strip()
            if search_q:
                sales_df = sales_df[
                    sales_df['cliente'].str.lower().str.contains(search_q, na=False) |
                    sales_df['id'].astype(str).str.contains(search_q)
                ]

        self.tbl_sales.setRowCount(len(sales_df))
        for i, row in enumerate(sales_df.to_dict('records')):
            v_id = row.get('id','')
            self.tbl_sales.setItem(i, 0, QTableWidgetItem(str(v_id)))
            self.tbl_sales.setItem(i, 1, QTableWidgetItem(str(row.get('fecha',''))))
            
            c_name = row.get('cliente')
            if not c_name or str(c_name).lower() == 'none':
                c_item = QTableWidgetItem("👤 Sin Cliente")
                c_item.setForeground(QColor("orange"))
            else:
                c_item = QTableWidgetItem(str(c_name))
            
            self.tbl_sales.setItem(i, 2, c_item)
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
        layout.setContentsMargins(20,20,20,20)
        
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
        self.cb_tasa_mode.addItem("🌐 API (Al Cambio Automático)", "api")
        self.cb_tasa_mode.addItem("✍️ Manual", "manual")
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
        btn_upd_tasa_bcv = QPushButton("Actualizar Tasa BCV (API)")
        btn_upd_tasa_bcv.clicked.connect(self.sync_bcv_rate_ui)
        btn_save_tasa_bcv = QPushButton("Guardar Manual")
        btn_save_tasa_bcv.clicked.connect(self.update_tasa_bcv_ui)
        self.btn_upd_tasa_bcv = btn_upd_tasa_bcv

        self.cfg_tasa = QLineEdit() # Legacy visual
        btn_upd_tasa = QPushButton("Guardar Tasa Sistema")
        btn_upd_tasa.clicked.connect(self.update_tasa_global)
        
        h_usdt = QHBoxLayout()
        h_usdt.addWidget(btn_upd_tasa_usdt); h_usdt.addWidget(btn_save_tasa_usdt)
        
        h_bcv = QHBoxLayout()
        h_bcv.addWidget(btn_upd_tasa_bcv); h_bcv.addWidget(btn_save_tasa_bcv)
        
        form_cono.addRow("🚀 Tipo de Obtención:", self.cb_tasa_mode)
        form_cono.addRow(QLabel("<hr>"))
        form_cono.addRow("💲 Tasa Mercado Paralelo (USD -> VES):", self.cfg_tasa_usdt)
        form_cono.addRow("", h_usdt)
        form_cono.addRow(QLabel("<br>"))
        form_cono.addRow("🏛️ Tasa Emisión BCV (USD -> VES):", self.cfg_tasa_bcv)
        form_cono.addRow("", h_bcv)
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
        gb_pos_ui = QGroupBox("🛒 Configuración de Interfaz POS y Dashboard")
        form_pos_ui = QFormLayout(gb_pos_ui)
        
        self.cfg_pos_ves = QCheckBox("Mostrar columna de Bolívares (VES) en POS")
        self.cfg_pos_ves.setChecked(self.db.get_config('pos_show_ves') == '1')
        
        self.cfg_pos_disc = QCheckBox("Habilitar opción de descuento del 25% en POS")
        self.cfg_pos_disc.setChecked(self.db.get_config('pos_enable_discount') == '1')
        # reacción inmediata cuando el usuario cambia la casilla
        self.cfg_pos_disc.stateChanged.connect(self.update_pos_discount_ui)

        self.cfg_dash_compact = QCheckBox("Modo Dashboard Compacto (Ocultar Gráficas y mostrar tablas)")
        self.cfg_dash_compact.setChecked(self.db.get_config('dashboard_compact') == '1')
        
        form_pos_ui.addRow(self.cfg_pos_ves)
        form_pos_ui.addRow(self.cfg_pos_disc)
        form_pos_ui.addRow(self.cfg_dash_compact)
        form_ly.addWidget(gb_pos_ui)

        # --- 4.5 Jerarquía de Uso y Seguridad ---
        gb_access = QGroupBox("🔐 Jerarquía de Uso y Control de Acceso")
        form_acc = QFormLayout(gb_access)
        
        self.cfg_admin_pwd = QLineEdit()
        self.cfg_admin_pwd.setEchoMode(QLineEdit.Password)
        self.cfg_admin_pwd.setPlaceholderText("Clave para proteger secciones")
        self.cfg_admin_pwd.setText(self.db.get_config('admin_pwd', ''))
        
        self.cfg_prot_mov = QCheckBox("Proteger / Ocultar Movimientos")
        self.cfg_prot_mov.setChecked(self.db.get_config('prot_mov') == '1')
        
        self.cfg_prot_rep = QCheckBox("Proteger / Ocultar Reportes")
        self.cfg_prot_rep.setChecked(self.db.get_config('prot_rep') == '1')

        self.cfg_prot_inv = QCheckBox("Proteger / Ocultar Inventario")
        self.cfg_prot_inv.setChecked(self.db.get_config('prot_inv') == '1')
        
        form_acc.addRow("Clave Administrador:", self.cfg_admin_pwd)
        form_acc.addRow(self.cfg_prot_mov)
        form_acc.addRow(self.cfg_prot_rep)
        form_acc.addRow(self.cfg_prot_inv)
        form_ly.addWidget(gb_access)
        
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
        form_ly.addWidget(gb_hk)  # ← Era el bug: faltaba agregar el groupbox al layout
        
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
        try:
            # 1. Configuración Básica e Interfaz
            self.db.set_config('pos_show_ves', '1' if self.cfg_pos_ves.isChecked() else '0')
            self.db.set_config('pos_enable_discount', '1' if self.cfg_pos_disc.isChecked() else '0')
            self.db.set_config('dashboard_compact', '1' if self.cfg_dash_compact.isChecked() else '0')
            self.db.set_config('hk_pos', self.hk_pos.text())
            self.db.set_config('hk_movimientos', self.hk_mov.text())
            self.db.set_config('hk_reportes', self.hk_rep.text())
            self.db.set_config('hk_inventory', self.hk_inv.text())
            self.db.set_config('hk_checkout', self.hk_checkout.text())
            
            # 1.5 Guardar Seguridad
            self.db.set_config('admin_pwd', self.cfg_admin_pwd.text())
            self.db.set_config('prot_mov', '1' if self.cfg_prot_mov.isChecked() else '0')
            self.db.set_config('prot_rep', '1' if self.cfg_prot_rep.isChecked() else '0')
            self.db.set_config('prot_inv', '1' if self.cfg_prot_inv.isChecked() else '0')
            
            # Aplicar cambios de visibilidad inmediatos
            self.refresh_sidebar()

            # 2. Guardar Tasas (si son válidas)
            try:
                t_usdt = float(self.cfg_tasa_usdt.text().replace(',', '.'))
                self.db.set_tasa_usdt(t_usdt)
                t_bcv = float(self.cfg_tasa_bcv.text().replace(',', '.'))
                self.db.set_tasa_bcv(t_bcv)
                t_legacy = float(self.cfg_tasa.text().replace(',', '.'))
                self.db.set_tasa(t_legacy)
            except ValueError:
                 logging.warning("Algunas tasas no pudieron guardarse por formato inválido.")

            # 3. Guardar Telegram
            self.db.set_telegram_config(self.tg_token.text(), self.tg_chat.text())

            # 4. Finalizar
            self.setup_hotkeys()
            self.refresh_ui()
            self.update_pos_discount_ui()
            self.refresh_cart_table()
            QMessageBox.information(self, "Éxito", "Configuración completa guardada correctamente.")
        except RuntimeError:
            QMessageBox.warning(self, "Error", "Error de instancia: Por favor recargue la página de configuración.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al guardar: {e}")

    def save_telegram_config(self):
        self.db.set_telegram_config(self.tg_token.text(), self.tg_chat.text())
        self.reminder_manager.set_telegram_config(self.tg_token.text(), self.tg_chat.text())
        QMessageBox.information(self, "Info", "Configuración guardada.")

    # =========================================================================
    # LÓGICA DE NEGOCIO Y ACTUALIZACIÓN UI
    # =========================================================================

    def refresh_ui(self):
        """Actualiza los elementos de interfaz de la página activa (lazy refresh)."""
        # 1. Actualizar tasas visibles en navbar y sidebar (siempre)
        try:
            bcv = self.db.get_tasa_bcv()
            usdt = self.db.get_tasa_usdt()
            tasa_txt = f"🏦 BCV: {bcv:,.2f} | 💵 USD: {usdt:,.2f}"
            if hasattr(self, 'lbl_nav_tasa'):
                self.lbl_nav_tasa.setText(tasa_txt)
            if hasattr(self, 'lbl_sidebar_bcv'):
                self.lbl_sidebar_bcv.setText(f"🏦 BCV: {bcv:,.0f} Bs")
            if hasattr(self, 'lbl_sidebar_usdt'):
                self.lbl_sidebar_usdt.setText(f"💵 USD: {usdt:,.0f} Bs")
        except: pass

        # 2. Actualizar KPI Cards del Dashboard (datos rápidos - siempre)
        try:
            self.lbl_last_update.setText(f"Actualizado: {datetime.now().strftime('%H:%M:%S')}")
            kpis = self.db.get_balance_summary()
            self.kpi_ingresos.findChild(QLabel, "value_success").setText(f"{kpis['ingreso']:,.2f} $")
            self.kpi_gastos.findChild(QLabel, "value_danger").setText(f"{kpis['gasto']:,.2f} $")
            self.kpi_ventas.findChild(QLabel, "value_primary").setText(f"{kpis['balance'] + kpis['gasto']:,.2f} $")
        except: pass

        try:
            conn = self.db.get_connection()
            res = conn.execute("SELECT SUM(monto_usdt - monto_pagado) as deuda FROM pendientes WHERE estado='PENDIENTE'").fetchone()
            deuda = res['deuda'] if res else 0
            self.kpi_debt.findChild(QLabel, "value_warning").setText(f"{deuda or 0:,.2f} $")
        except: pass

        # 3. Acciones recientes (siempre, es barato)
        if hasattr(self, 'recent_list'):
            self.recent_list.clear()
            for act in self.db.get_recent_actions(limit=8):
                text = f"{act['fecha']} | {act['descripcion']} | {act['monto_usdt']:.2f} $"
                self.recent_list.addItem(text)

        self.update_pos_discount_ui()

        # ── LAZY REFRESH: Solo actualizar la página actualmente visible ──
        idx = self.pages.currentIndex()
        if idx == 0:    # Dashboard
            self._refresh_dashboard_charts()
        elif idx == 1:  # POS
            self.refresh_pos_clients()
            self.filter_pos_products()
        elif idx == 2:  # Movimientos
            self.load_transactions_table()
        elif idx == 3:  # Pendientes
            self.load_pendientes_table()
        elif idx == 4:  # Inventario
            self.load_inventory_table()
        elif idx == 5:  # Servicios
            self.load_services_table()
        elif idx == 6:  # Clientes
            self.refresh_clients_table()
        elif idx == 7:  # Reportes
            self.refresh_reports()
        elif idx == 9:  # Notificaciones
            self.refresh_reminders_table()
        elif idx == 10: # Configuración
            try:
                self.cfg_tasa_usdt.setText(str(self.db.get_tasa_usdt()))
                self.cfg_tasa_bcv.setText(str(self.db.get_tasa_bcv()))
                self.cfg_tasa.setText(str(self.db.get_tasa()))
                mode = self.db.get_tasa_mode()
                ci = self.cb_tasa_mode.findData(mode)
                if ci >= 0:
                    self.cb_tasa_mode.setCurrentIndex(ci)
                self._apply_tasa_mode_to_ui()
            except: pass

        # Marcar índice de búsqueda como sucio
        self._search_index_dirty = True

    def refresh_all(self):
        """Recarga TODO el sistema (útil tras importaciones masivas o cambios críticos)."""
        self.db._invalidate_cache()
        self.refresh_ui()
        # Forzar recarga de tablas pesadas independientemente de la página actual
        self.load_transactions_table()
        self.load_pendientes_table()
        self.load_inventory_table()
        self.load_services_table()
        self.refresh_clients_table()
        self.refresh_pos_clients()
        self.filter_pos_products()
        self.build_search_index()

    def _refresh_dashboard_charts(self):
        """Actualiza solo los gráficos del dashboard (llamado cuando es la página activa)."""
        is_compact = self.db.get_config('dashboard_compact') == '1'
        if hasattr(self, 'dashboard_charts_widget'):
            self.dashboard_charts_widget.setVisible(not is_compact)
        if hasattr(self, 'dashboard_compact_widget'):
            self.dashboard_compact_widget.setVisible(is_compact)

        if is_compact:
            try:
                sales_list = self.db.get_ventas()
                sales_df = pd.DataFrame(sales_list) if sales_list else pd.DataFrame()
                if not sales_df.empty:
                    sales_df = sales_df.tail(10).iloc[::-1]
                    self.tbl_compact_invoices.setRowCount(len(sales_df))
                    for i, row in enumerate(sales_df.to_dict('records')):
                        self.tbl_compact_invoices.setItem(i, 0, QTableWidgetItem(str(row.get('id',''))))
                        self.tbl_compact_invoices.setItem(i, 1, QTableWidgetItem(str(row.get('fecha',''))))
                        c_name = row.get('cliente')
                        self.tbl_compact_invoices.setItem(i, 2, QTableWidgetItem(str(c_name if c_name and str(c_name).lower() != 'none' else 'Sin Cliente')))
                        self.tbl_compact_invoices.setItem(i, 3, QTableWidgetItem(f"{row.get('total_usd',0):.2f} $"))
                else:
                    self.tbl_compact_invoices.setRowCount(0)
            except: pass

            try:
                prod_df = self.db.get_inventory()
                if not prod_df.empty:
                    prod_df = prod_df[prod_df['stock'] <= 5].head(10)
                    self.tbl_compact_products.setRowCount(len(prod_df))
                    for i, row in enumerate(prod_df.to_dict('records')):
                        self.tbl_compact_products.setItem(i, 0, QTableWidgetItem(str(row.get('codigo',''))))
                        self.tbl_compact_products.setItem(i, 1, QTableWidgetItem(str(row.get('nombre',''))))
                        stk = QTableWidgetItem(str(row.get('stock','')))
                        stk.setForeground(QColor("red"))
                        self.tbl_compact_products.setItem(i, 2, stk)
                else:
                    self.tbl_compact_products.setRowCount(0)
            except: pass
            return

        try:
            df_cat = self.db.get_category_sales()
            if not df_cat.empty:
                data_cat = df_cat.set_index('cat')['total'].to_dict()
                self.chart_cat.plot_donut(data_cat, "Distribución de Ventas")
            else:
                self.chart_cat.plot_donut({}, "Ventas por Categoría")
        except: pass

        try:
            df_week = self.db.get_weekly_sales()
            if not df_week.empty:
                self.chart_weekly.plot_line(df_week['dia'].tolist(), df_week['total'].tolist(), "Historial de Ventas")
            else:
                self.chart_weekly.plot_line([], [], "Sin Ventas Recientes")
        except: pass

        try:
            df_top = self.db.get_top_selling_products(limit=5)
            if not df_top.empty:
                df_top = df_top.iloc[::-1]
                self.chart_top.plot_horizontal_bar(df_top['nombre'].tolist(), df_top['total_vendido'].tolist(), "Top Productos")
            else:
                self.chart_top.plot_horizontal_bar([], [], "Sin Datos")
        except: pass

        try:
            df_tx = self.db.get_dataframe()
            if not df_tx.empty:
                gastos = df_tx[df_tx['tipo'] == 'GASTO'].copy()
                if not gastos.empty:
                    gastos.loc[:, 'cat_simple'] = gastos['categoria'].apply(lambda x: x.split(' ')[0])
                    data_g = gastos.groupby('cat_simple')['monto_usdt'].sum().to_dict()
                    self.chart_expenses.plot_donut(data_g, "Gastos por Categoría")
                else:
                    self.chart_expenses.plot_donut({}, "Sin Gastos")
            else:
                self.chart_expenses.plot_donut({}, "Sin Movimientos")
        except: pass

        # Modo de tasa
        mode = self.db.get_tasa_mode()
        idx = self.cb_tasa_mode.findData(mode)
        if idx >= 0:
            self.cb_tasa_mode.setCurrentIndex(idx)
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
        # Nota: Ctrl+K se registra en setup_hotkeys() con ApplicationShortcut


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
                self.tasa_synced.emit(float(rate_usdt))
            # NOTA: no actualizamos BCV ni legacy automáticamente; son campos de guardado manual
        except Exception as e:
            print("Exchange sync failed:", e)

    def _on_tasa_synced(self, rate):
        """Handler seguro para actualizar UI desde hilos tras sincronizar tasa."""
        try:
            self.cfg_tasa_usdt.setText(str(rate))
            self.cfg_tasa.setText(str(rate))
            self.refresh_ui()
        except: pass

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
        layout.setContentsMargins(20,20,20,20)
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
        dlg.setMinimumSize(380, 220)
        dlg.resize(460, 260)
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
        dlg.setWindowTitle("🚀 Búsqueda Avanzada en todo el Sistema")
        dlg.setFixedSize(700, 500)
        v = QVBoxLayout(dlg)
        
        lbl_info = QLabel("Escriba para buscar en facturas, clientes, inventario o deudas...")
        lbl_info.setStyleSheet("color: #64748b; font-size: 13px;")
        v.addWidget(lbl_info)

        le = QLineEdit()
        le.setPlaceholderText("🔍 ¿Qué desea encontrar hoy? (ej: nombre de cliente, código de producto...)")
        le.setFixedHeight(45)
        le.setClearButtonEnabled(True)
        le.setStyleSheet("font-size: 16px; padding: 5px 10px;")
        if prefill:
            le.setText(prefill)
        
        listw = QListWidget()
        listw.setObjectName("SearchList")
        listw.setAlternatingRowColors(True)
        listw.setSpacing(2)
        v.addWidget(le); v.addWidget(listw)
        
        def do_search():
            q = le.text().strip()
            if len(q) < 2: 
                listw.clear()
                return
            
            # Reconstruir índice solo si hubo cambios en datos (lazy)
            if getattr(self, '_search_index_dirty', True):
                self.build_search_index()
                self._search_index_dirty = False
            res = self.global_search.search(q, limit=40)
            listw.clear()
            for r in res:
                # Icono según tipo
                icon = "📦" if r['type'] == 'Producto' else "🛠️" if r['type'] == 'Servicio' else "👤" if r['type'] == 'Cliente' else "💸" if r['type'] == 'Transacción' else "⌛"
                
                name = r['meta'].get('name', '')
                desc = r['meta'].get('description', '')
                
                # Widget personalizado para el item
                item = QListWidgetItem()
                item.setData(Qt.UserRole, r)
                
                # Texto limpio y legible
                display_text = f"{icon} {r['type'].upper()}: {name}\n   {desc}"
                item.setText(display_text)
                listw.addItem(item)
        
        le.textChanged.connect(do_search) 
        if prefill: do_search()

        def on_activate(item):
            r = item.data(Qt.UserRole)
            rtype = r['type']
            rid = r['meta'].get('row_id')
            
            dlg.accept() # Cerrar buscador

            if rtype == 'Transacción':
                dlg2 = TransactionDialog(self, self.db, tx_id=rid)
                dlg2.exec()
            elif rtype == 'Pendiente':
                self.switch_page(3) # Cuentas pendientes
            elif rtype == 'Producto':
                self.switch_page(4) # Inventario
            elif rtype == 'Servicio':
                self.switch_page(5) # Servicios
            elif rtype == 'Cliente':
                self.switch_page(6) # Clientes
                
            self.refresh_ui()

        listw.itemActivated.connect(on_activate)
        
        # Atajo Enter para el primer resultado
        le.returnPressed.connect(lambda: on_activate(listw.item(0)) if listw.count() > 0 else None)
        
        dlg.exec()

    def build_search_index(self):
        """Prepara el índice de búsqueda global con todos los datos relevantes."""
        items = []
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            
            # 1. Transacciones
            rows = cur.execute("SELECT id, descripcion, fecha, monto_usdt FROM transacciones").fetchall()
            for r in rows:
                items.append({
                    'id': f"tx_{r['id']}", 
                    'type': 'Transacción', 
                    'name': r['descripcion'], 
                    'description': f"Monto: {r['monto_usdt']:.2f}$ - Fecha: {r['fecha']}",
                    'row_id': r['id']
                })
            
            # 2. Pendientes
            rows = cur.execute("SELECT id, cliente, descripcion, monto_usdt FROM pendientes WHERE estado='PENDIENTE'").fetchall()
            for r in rows:
                items.append({
                    'id': f"pend_{r['id']}", 
                    'type': 'Pendiente', 
                    'name': f"Deuda: {r['cliente']}", 
                    'description': f"{r['descripcion']} - Debe: {r['monto_usdt']:.2f}$",
                    'row_id': r['id']
                })
            
            # 3. Inventario (Productos)
            rows = cur.execute("SELECT id, codigo, nombre, precio, stock FROM inventario").fetchall()
            for r in rows:
                items.append({
                    'id': f"prod_{r['id']}", 
                    'type': 'Producto', 
                    'name': r['nombre'], 
                    'sku': r['codigo'],
                    'description': f"Código: {r['codigo']} - Precio: {(r['precio'] or 0):.2f}$ - Stock: {r['stock'] or 0}",
                    'row_id': r['id']
                })

            # 4. Servicios
            rows = cur.execute("SELECT id, codigo, nombre, precio FROM servicios").fetchall()
            for r in rows:
                items.append({
                    'id': f"svc_{r['id']}", 
                    'type': 'Servicio', 
                    'name': r['nombre'], 
                    'sku': r['codigo'],
                    'description': f"Precio: {(r['precio'] or 0):.2f}$",
                    'row_id': r['id']
                })

            # 5. Clientes
            rows = cur.execute("SELECT id, nombre, cedula, telefono FROM clientes").fetchall()
            for r in rows:
                items.append({
                    'id': f"cli_{r['id']}", 
                    'type': 'Cliente', 
                    'name': r['nombre'], 
                    'description': f"Ced/RIF: {r['cedula']} - Telf: {r['telefono']}",
                    'row_id': r['id']
                })

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
            self.table_mov.setHorizontalHeaderLabels(["ID", "Fecha", "Descripción", "Monto ($)", "Monto (Bs)", "Categoría", "Tipo", "Acción"])

        filter_txt = self.search_bar.text().lower()
        df = self.db.get_dataframe()
        
        # Opcional: ajustar el header cada vez que se carga si es necesario
        header = self.table_mov.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)

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
        for i, row in enumerate(df.to_dict('records')):
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
            # Aceptamos variantes como "venta", "VENTA", "Venta #" o simplemente tener la categoría "Ventas"
            is_sale = "venta" in desc.lower() or row['categoria'] == 'Ventas'
            if is_sale:
                match = re.search(r'#(\d+)', desc)
                v_id = match.group(1) if match else None
                
                # Si no hay ID en la descripción, pero es categoría ventas, tal vez el ID es el tx_id? 
                # No, venta_id es diferente de tx_id. 
                # Pero en add_venta, desc_venta = f"Venta #{venta_id}"
                
                if v_id:
                    btn_det = QPushButton("🛒 Ver Venta")
                    btn_det.setObjectName("btn_outline")
                    btn_det.setFixedHeight(28)
                    btn_det.clicked.connect(lambda _, vid=v_id: self.show_venta_detalle(vid))
                    self.table_mov.setCellWidget(i, 7, btn_det)
                else:
                    self.table_mov.setCellWidget(i, 7, QWidget()) # Celda vacía
            else:
                self.table_mov.setCellWidget(i, 7, QWidget()) # Celda vacía

    def view_selected_detail(self):
        """Abre el detalle de la venta seleccionada en la tabla de movimientos."""
        row = self.table_mov.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Aviso", "Seleccione una fila primero.")
            return
        
        desc = self.table_mov.item(row, 2).text()
        match = re.search(r'#(\d+)', desc)
        if match:
            v_id = match.group(1)
            self.show_venta_detalle(v_id)
        else:
            QMessageBox.information(self, "Información", "Esta transacción no es una venta vinculada con productos específicos.")

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
        # Obtener la tasa UNA sola vez fuera del loop (evita N queries a la DB)
        tasa = self.db.get_tasa()
        
        for i, row in enumerate(rows):
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
            btn_reg = QPushButton("💳 Pago")
            btn_reg.setObjectName("btn_success")
            btn_reg.setToolTip("Registrar un pago parcial o total")
            btn_reg.clicked.connect(lambda _, r=row: self.register_partial_payment_dialog(r))
            btn_hist = QPushButton("📋 Hist.")
            btn_hist.setToolTip("Ver historial de pagos")
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
            self.btn_upd_tasa_bcv.setEnabled(True)
        else:
            # modo manual: permitir guardar y desactivar botón API
            self.btn_upd_tasa_usdt.setEnabled(False)
            self.btn_save_tasa_usdt.setEnabled(True)
            self.btn_upd_tasa_bcv.setEnabled(False)

    def sync_bcv_rate_ui(self):
        """Intenta sincronizar la tasa BCV desde la API."""
        try:
            rate = self.db.update_tasa_bcv_from_api()
            self.cfg_tasa_bcv.setText(str(rate))
            QMessageBox.information(self, "Éxito", f"Tasa BCV actualizada desde API Oficial: {rate:.2f} VES/USD")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo sincronizar la tasa BCV: {e}")

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
                    self.db._invalidate_cache()  # Limpiar caché tras importación
                    self.refresh_all()           # Actualización completa (importación masiva)
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
                    self.db._invalidate_cache()  # Limpiar caché tras importación
                    self.refresh_all()           # Actualización completa (importación masiva)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"No se pudo importar la DB: {e}")

