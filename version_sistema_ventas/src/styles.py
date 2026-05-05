# =============================================================================
# SISTEMA DE GESTIÓN EMPRESARIAL - ESTILOS PREMIUM v3.0
# Diseño moderno, accesible y rápido con soporte Dark/Light
# Optimizado para usabilidad y claridad visual
# =============================================================================

COLORS = {
    "bg_primary":    "#ffffff",
    "bg_secondary":  "#f8fafc",
    "bg_tertiary":   "#f1f5f9",
    "border":        "#e2e8f0",
    "accent":        "#2563eb",
    "accent_hover":  "#1d4ed8",
    "accent_light":  "#dbeafe",
    "text_main":     "#0f172a",
    "text_body":     "#1e293b",
    "text_muted":    "#64748b",
    "success":       "#10b981",
    "success_light": "#d1fae5",
    "danger":        "#ef4444",
    "danger_light":  "#fee2e2",
    "warning":       "#f59e0b",
    "warning_light": "#fef3c7",
    "info":          "#06b6d4",
    "purple":        "#8b5cf6",
    "sidebar_width": "240px",
}

LIGHT_STYLESHEET = """
/* ============================================================
   BASE
   ============================================================ */
QMainWindow, QDialog {
    background-color: #f8fafc;
    color: #0f172a;
    font-family: 'Segoe UI', 'Inter', 'Roboto', sans-serif;
    font-size: 13px;
}

QWidget {
    font-family: 'Segoe UI', 'Inter', 'Roboto', sans-serif;
    color: #1e293b;
    font-size: 13px;
}

/* ============================================================
   SIDEBAR (Navegación lateral)
   ============================================================ */
QListWidget#Sidebar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1e293b, stop:1 #0f172a);
    border: none;
    border-right: 1px solid #334155;
    padding: 8px 0px;
    font-size: 13px;
    font-weight: 500;
    outline: none;
}

QListWidget#Sidebar::item {
    padding: 12px 16px;
    margin: 2px 8px;
    border-radius: 10px;
    color: #94a3b8;
    min-height: 22px;
}

QListWidget#Sidebar::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #2563eb, stop:1 #3b82f6);
    color: #ffffff;
    font-weight: 700;
}

QListWidget#Sidebar::item:hover:!selected {
    background-color: rgba(148, 163, 184, 0.12);
    color: #e2e8f0;
}

/* ============================================================
   NAVBAR (Barra superior)
   ============================================================ */
QFrame#Navbar {
    background-color: #ffffff;
    border-bottom: 1px solid #e2e8f0;
    min-height: 64px;
}

QLineEdit#NavSearch {
    background-color: #f1f5f9;
    border: 1.5px solid transparent;
    border-radius: 20px;
    padding: 8px 18px;
    color: #1e293b;
    font-size: 13px;
}

QLineEdit#NavSearch:focus {
    border: 1.5px solid #3b82f6;
    background-color: #ffffff;
}

/* ============================================================
   PANELS Y CARDS
   ============================================================ */
QFrame#ContentPanel {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 16px;
}

QFrame#StatCard {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 20px 16px;
    min-height: 90px;
}

QFrame#POSPanel {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 16px;
}

QFrame#CartPanel {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 16px;
}

QFrame#KPIcard_success {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #10b981;
    border-radius: 14px;
    padding: 16px;
}

QFrame#KPIcard_danger {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #ef4444;
    border-radius: 14px;
    padding: 16px;
}

QFrame#KPIcard_primary {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #2563eb;
    border-radius: 14px;
    padding: 16px;
}

QFrame#KPIcard_warning {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #f59e0b;
    border-radius: 14px;
    padding: 16px;
}

QFrame#PanelAlert_warning {
    background-color: #fffbeb;
    border: 1px solid #fcd34d;
    border-left: 4px solid #f59e0b;
    border-radius: 10px;
    padding: 10px 14px;
}

/* ============================================================
   GROUPBOX
   ============================================================ */
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    margin-top: 18px;
    padding-top: 24px;
    padding-left: 8px;
    padding-right: 8px;
    padding-bottom: 10px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    color: #1e293b;
    font-weight: 700;
    font-size: 13px;
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    top: -6px;
    left: 12px;
}

/* ============================================================
   SCROLL AREAS
   ============================================================ */
QScrollArea, QScrollArea > QWidget > QWidget {
    background-color: transparent;
    border: none;
}

QScrollBar:vertical {
    background-color: transparent;
    width: 6px;
    border-radius: 3px;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background-color: #cbd5e1;
    border-radius: 3px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background-color: #94a3b8;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: transparent;
    height: 6px;
    border-radius: 3px;
    margin: 2px;
}

QScrollBar::handle:horizontal {
    background-color: #cbd5e1;
    border-radius: 3px;
    min-width: 24px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #94a3b8;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ============================================================
   LISTAS
   ============================================================ */
QListWidget {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    outline: none;
}

QListWidget::item {
    padding: 8px 12px;
    border-radius: 8px;
    margin: 2px 4px;
}

QListWidget::item:selected {
    background-color: #eff6ff;
    color: #1e293b;
}

QListWidget::item:hover:!selected {
    background-color: #f8fafc;
}

/* ============================================================
   LABELS Y TIPOGRAFÍA
   ============================================================ */
QLabel#h1 {
    font-size: 24px;
    font-weight: 800;
    color: #0f172a;
    letter-spacing: -0.5px;
}

QLabel#h2 {
    font-size: 17px;
    font-weight: 700;
    color: #1e293b;
}

QLabel#h3 {
    font-size: 14px;
    font-weight: 600;
    color: #334155;
}

QLabel#subtitle {
    font-size: 11px;
    font-weight: 600;
    color: #64748b;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

QLabel#value_success {
    font-size: 24px;
    font-weight: 800;
    color: #10b981;
    letter-spacing: -0.5px;
}

QLabel#value_danger {
    font-size: 24px;
    font-weight: 800;
    color: #ef4444;
    letter-spacing: -0.5px;
}

QLabel#value_primary {
    font-size: 24px;
    font-weight: 800;
    color: #2563eb;
    letter-spacing: -0.5px;
}

QLabel#value_warning {
    font-size: 24px;
    font-weight: 800;
    color: #f59e0b;
    letter-spacing: -0.5px;
}

QLabel#value_purple {
    font-size: 24px;
    font-weight: 800;
    color: #8b5cf6;
    letter-spacing: -0.5px;
}

QLabel#badge_success {
    background-color: #d1fae5;
    color: #065f46;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 700;
}

QLabel#badge_danger {
    background-color: #fee2e2;
    color: #991b1b;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 700;
}

QLabel#badge_warning {
    background-color: #fef3c7;
    color: #92400e;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 700;
}

QLabel#calc_preview {
    background-color: #f0fdf4;
    border: 1px solid #86efac;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 13px;
    color: #166534;
}

QLabel#calc_preview_warn {
    background-color: #fefce8;
    border: 1px solid #fde047;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 13px;
    color: #713f12;
}

/* ============================================================
   BOTONES - Tamaño mínimo aumentado para mejor usabilidad
   ============================================================ */
QPushButton {
    background-color: #ffffff;
    border: 1.5px solid #cbd5e1;
    color: #334155;
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: 600;
    font-size: 13px;
    min-height: 34px;
}

QPushButton:hover {
    background-color: #f8fafc;
    border: 1.5px solid #94a3b8;
    color: #1e293b;
}

QPushButton:pressed {
    background-color: #f1f5f9;
    border-color: #64748b;
}

QPushButton:disabled {
    color: #94a3b8;
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
}

QPushButton#btn_primary {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #3b82f6, stop:1 #2563eb);
    color: #ffffff;
    border: none;
}
QPushButton#btn_primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #60a5fa, stop:1 #3b82f6);
}
QPushButton#btn_primary:pressed { background-color: #1d4ed8; }

QPushButton#btn_success {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #34d399, stop:1 #10b981);
    color: #ffffff;
    border: none;
}
QPushButton#btn_success:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #6ee7b7, stop:1 #34d399);
}
QPushButton#btn_success:pressed { background-color: #059669; }

QPushButton#btn_danger {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f87171, stop:1 #ef4444);
    color: #ffffff;
    border: none;
}
QPushButton#btn_danger:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #fca5a5, stop:1 #f87171);
}
QPushButton#btn_danger:pressed { background-color: #dc2626; }

QPushButton#btn_warning {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #fbbf24, stop:1 #f59e0b);
    color: #1e293b;
    border: none;
    font-weight: 700;
}
QPushButton#btn_warning:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #fcd34d, stop:1 #fbbf24);
}

QPushButton#btn_pos_large {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #34d399, stop:1 #059669);
    color: #ffffff;
    font-size: 16px;
    font-weight: 800;
    padding: 16px;
    border-radius: 12px;
    border: none;
    letter-spacing: 0.5px;
    min-height: 52px;
}
QPushButton#btn_pos_large:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #6ee7b7, stop:1 #10b981);
}
QPushButton#btn_pos_large:pressed { background-color: #047857; }

QPushButton#btn_outline {
    background-color: transparent;
    border: 2px solid #2563eb;
    color: #2563eb;
    font-weight: 700;
    border-radius: 8px;
}
QPushButton#btn_outline:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #3b82f6, stop:1 #2563eb);
    color: white;
    border: none;
}
QPushButton#btn_outline:hover:!checked {
    background-color: #eff6ff;
    color: #1d4ed8;
}

QPushButton#btn_calc {
    background-color: #f0fdf4;
    border: 1px solid #86efac;
    color: #166534;
    border-radius: 8px;
    padding: 6px 10px;
    font-weight: 700;
    font-size: 15px;
}
QPushButton#btn_calc:hover {
    background-color: #dcfce7;
    border-color: #4ade80;
}

QPushButton#btn_theme, QPushButton#btn_help {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 6px;
    min-width: 38px;
    min-height: 38px;
}
QPushButton#btn_theme:hover, QPushButton#btn_help:hover {
    background-color: #f1f5f9;
}

/* ============================================================
   TABLAS
   ============================================================ */
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #fafafa;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    color: #1e293b;
    gridline-color: #f1f5f9;
    font-size: 13px;
    selection-background-color: #eff6ff;
    outline: none;
}

QTableWidget::item {
    padding: 8px 10px;
    border: none;
}

QTableWidget::item:selected {
    background-color: #eff6ff;
    color: #1e293b;
}

QTableWidget::item:hover {
    background-color: #f0f9ff;
}

QHeaderView::section {
    background-color: #f8fafc;
    color: #475569;
    font-weight: 700;
    font-size: 11px;
    padding: 10px 8px;
    border: none;
    border-bottom: 2px solid #e2e8f0;
    border-right: 1px solid #f1f5f9;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

QHeaderView::section:hover {
    background-color: #f1f5f9;
    color: #1e293b;
}

QHeaderView::section:first {
    border-top-left-radius: 10px;
}

/* ============================================================
   TABS
   ============================================================ */
QTabWidget::pane {
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    background-color: #ffffff;
}

QTabBar::tab {
    background-color: #f8fafc;
    color: #64748b;
    padding: 10px 20px;
    border: 1px solid #e2e8f0;
    border-bottom: none;
    border-radius: 8px 8px 0px 0px;
    margin-right: 2px;
    font-weight: 600;
    font-size: 13px;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #2563eb;
    border-bottom: 2px solid #2563eb;
}

QTabBar::tab:hover:!selected {
    background-color: #f1f5f9;
    color: #1e293b;
}

/* ============================================================
   INPUTS
   ============================================================ */
QLineEdit, QComboBox, QDateEdit, QDateTimeEdit, QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    border: 1.5px solid #e2e8f0;
    border-radius: 8px;
    padding: 8px 12px;
    color: #1e293b;
    font-size: 13px;
    min-height: 34px;
    selection-background-color: #dbeafe;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QDateEdit:focus, QDateTimeEdit:focus {
    border: 2px solid #3b82f6;
    background-color: #fafcff;
    outline: none;
}

QLineEdit:hover:!focus, QComboBox:hover:!focus {
    border: 1.5px solid #94a3b8;
}

QLineEdit:disabled, QComboBox:disabled {
    background-color: #f8fafc;
    color: #94a3b8;
    border: 1px solid #e2e8f0;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox::down-arrow {
    width: 12px;
    height: 12px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    selection-background-color: #eff6ff;
    selection-color: #1e293b;
    outline: none;
    padding: 4px;
}

QComboBox QAbstractItemView::item {
    padding: 8px 12px;
    border-radius: 6px;
    min-height: 28px;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #eff6ff;
    color: #2563eb;
}

/* CheckBox mejorado */
QCheckBox {
    spacing: 10px;
    font-size: 13px;
    color: #334155;
    font-weight: 500;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #cbd5e1;
    border-radius: 5px;
    background-color: #ffffff;
}

QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #2563eb;
    image: none;
}

QCheckBox::indicator:hover {
    border-color: #3b82f6;
}

/* ============================================================
   FORM LAYOUT
   ============================================================ */
QFormLayout {
    vertical-spacing: 14px;
}

/* ============================================================
   SEPARADORES
   ============================================================ */
QFrame[frameShape="4"], QFrame[frameShape="5"] {
    border: none;
    border-top: 1px solid #e2e8f0;
    max-height: 1px;
}

/* ============================================================
   STATUS BAR
   ============================================================ */
QStatusBar {
    background-color: #f8fafc;
    color: #64748b;
    border-top: 1px solid #e2e8f0;
    font-size: 12px;
    padding: 2px 8px;
}

QStatusBar::item {
    border: none;
}

/* ============================================================
   TOOLTIP - Estilo mejorado más legible
   ============================================================ */
QToolTip {
    background-color: #0f172a;
    color: #f8fafc;
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 12px;
    font-weight: 500;
    opacity: 230;
}

/* ============================================================
   SPINBOX ARROWS
   ============================================================ */
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    border: none;
    background: transparent;
    width: 18px;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #f1f5f9;
    border-radius: 4px;
}

"""


def get_stylesheet(theme="light"):
    if theme == "dark":
        stylesheet = LIGHT_STYLESHEET
        replacements = [
            # Backgrounds
            ("#ffffff",  "PLACEHOLDER_BG1"),
            ("#f8fafc",  "PLACEHOLDER_BG2"),
            ("#f1f5f9",  "PLACEHOLDER_BG3"),
            ("#fafafa",  "PLACEHOLDER_BG4"),
            ("#fafcff",  "PLACEHOLDER_BG5"),
            ("#f0f9ff",  "PLACEHOLDER_BG6"),
            # Text
            ("#0f172a",  "PLACEHOLDER_TEXT0"),
            ("#1e293b",  "PLACEHOLDER_TEXT1"),
            ("#334155",  "PLACEHOLDER_TEXT3"),
            # Borders
            ("#e2e8f0",  "PLACEHOLDER_BORDER"),
            ("#cbd5e1",  "PLACEHOLDER_MUTED"),
            # Sidebar
            ("#475569",  "PLACEHOLDER_SIDEBAR"),
            # Selection
            ("#eff6ff",  "PLACEHOLDER_SELECT"),
            ("#dbeafe",  "PLACEHOLDER_SEL2"),
            # success light
            ("#d1fae5",  "PLACEHOLDER_SUCC_L"),
            ("#065f46",  "PLACEHOLDER_SUCC_DK"),
            # danger light
            ("#fee2e2",  "PLACEHOLDER_DANG_L"),
            ("#991b1b",  "PLACEHOLDER_DANG_DK"),
            # warning light
            ("#fef3c7",  "PLACEHOLDER_WARN_L"),
            ("#92400e",  "PLACEHOLDER_WARN_DK"),
            ("#fffbeb",  "PLACEHOLDER_WARN_BG"),
            ("#fcd34d",  "PLACEHOLDER_WARN_BD"),
            # accent light
            ("#dbeafe",  "PLACEHOLDER_ACC_L"),
        ]
        for old, placeholder in replacements:
            stylesheet = stylesheet.replace(old, placeholder)

        final_values = {
            "PLACEHOLDER_BG1":     "#1e293b",
            "PLACEHOLDER_BG2":     "#0f172a",
            "PLACEHOLDER_BG3":     "#1e293b",
            "PLACEHOLDER_BG4":     "#1a2535",
            "PLACEHOLDER_BG5":     "#1e2d40",
            "PLACEHOLDER_BG6":     "#0c1a2e",
            "PLACEHOLDER_TEXT0":   "#f8fafc",
            "PLACEHOLDER_TEXT1":   "#e2e8f0",
            "PLACEHOLDER_TEXT3":   "#cbd5e1",
            "PLACEHOLDER_BORDER":  "#334155",
            "PLACEHOLDER_MUTED":   "#475569",
            "PLACEHOLDER_SIDEBAR": "#94a3b8",
            "PLACEHOLDER_SELECT":  "#1e3a5f",
            "PLACEHOLDER_SEL2":    "#1e3a5f",
            "PLACEHOLDER_SUCC_L":  "#064e3b",
            "PLACEHOLDER_SUCC_DK": "#34d399",
            "PLACEHOLDER_DANG_L":  "#450a0a",
            "PLACEHOLDER_DANG_DK": "#f87171",
            "PLACEHOLDER_WARN_L":  "#422006",
            "PLACEHOLDER_WARN_DK": "#fbbf24",
            "PLACEHOLDER_WARN_BG": "#1c1200",
            "PLACEHOLDER_WARN_BD": "#b45309",
            "PLACEHOLDER_ACC_L":   "#1e3a5f",
        }
        for placeholder, new in final_values.items():
            stylesheet = stylesheet.replace(placeholder, new)

        # Dark sidebar gradient fix
        stylesheet = stylesheet.replace(
            "stop:0 #1e293b, stop:1 #0f172a",
            "stop:0 #0d1117, stop:1 #090d13"
        )

        return stylesheet
    return LIGHT_STYLESHEET
