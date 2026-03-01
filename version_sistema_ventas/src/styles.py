# =============================================================================
# SISTEMA DE GESTIÓN EMPRESARIAL - ESTILOS LIGHT / PREMIUM (MODERN CLEAN UI)
# =============================================================================

COLORS = {
    "bg_primary": "#ffffff",
    "bg_secondary": "#f8fafc",
    "border": "#e2e8f0",
    "accent": "#2563eb",
    "accent_hover": "#1d4ed8",
    "text_main": "#1e293b",
    "text_muted": "#64748b",
    "success": "#10b981",
    "danger": "#ef4444",
    "warning": "#f59e0b"
}

LIGHT_STYLESHEET = """
/* --- General --- */
QMainWindow, QDialog {
    background-color: #f8fafc;
    color: #1e293b;
    font-family: 'Segoe UI', 'Inter', 'Roboto', sans-serif;
}

QWidget {
    font-family: 'Segoe UI', 'Inter', 'Roboto', sans-serif;
    color: #1e293b;
}

/* --- SIDEBAR --- */
QListWidget#Sidebar {
    background-color: #ffffff;
    border-right: 1px solid #e2e8f0;
    padding-top: 20px;
    font-size: 14px;
    font-weight: 500;
    outline: none;
}

QListWidget#Sidebar::item {
    padding: 14px 24px;
    margin: 4px 12px;
    border-radius: 10px;
    color: #475569;
}

QListWidget#Sidebar::item:selected {
    background-color: #eff6ff;
    color: #2563eb;
    font-weight: 700;
}

QListWidget#Sidebar::item:hover:!selected {
    background-color: #f1f5f9;
    color: #1e293b;
}

/* --- NAVBAR --- */
QFrame#Navbar {
    background-color: #ffffff;
    border-bottom: 1px solid #e2e8f0;
}

QLineEdit#NavSearch {
    background-color: #f1f5f9;
    border: 1px solid transparent;
    border-radius: 18px;
    padding: 8px 20px;
    color: #1e293b;
    font-size: 13px;
}

QLineEdit#NavSearch:focus {
    border: 1px solid #3b82f6;
    background-color: #ffffff;
}

/* --- PANELS Y CARDS --- */
QFrame#ContentPanel, QFrame#StatCard, QFrame#POSPanel, QFrame#CartPanel {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px;
}

QGroupBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 12px;
    margin-top: 15px;
    padding-top: 25px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 10px;
    color: #1e293b;
    font-weight: 700;
    top: -8px;
    left: 10px;
}

QScrollArea, QScrollArea > QWidget > QWidget {
    background-color: transparent;
    border: none;
}

QListWidget {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    outline: none;
}


/* --- LABELS --- */
QLabel#h1 { font-size: 26px; font-weight: 800; color: #0f172a; }
QLabel#h2 { font-size: 20px; font-weight: 700; color: #1e293b; }
QLabel#h3 { font-size: 16px; font-weight: 600; color: #334155; }
QLabel#subtitle { font-size: 13px; font-weight: 500; color: #64748b; }

QLabel#value_success { font-size: 28px; font-weight: bold; color: #10b981; }
QLabel#value_danger { font-size: 28px; font-weight: bold; color: #ef4444; }
QLabel#value_primary { font-size: 28px; font-weight: bold; color: #2563eb; }

/* --- BOTONES --- */
QPushButton {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    color: #334155;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #f8fafc;
    border: 1px solid #94a3b8;
}

QPushButton#btn_primary {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
}
QPushButton#btn_primary:hover { background-color: #1d4ed8; }

QPushButton#btn_success {
    background-color: #10b981;
    color: #ffffff;
    border: none;
}
QPushButton#btn_success:hover { background-color: #059669; }

QPushButton#btn_danger {
    background-color: #ef4444;
    color: #ffffff;
    border: none;
}
QPushButton#btn_danger:hover { background-color: #dc2626; }

QPushButton#btn_pos_large {
    background-color: #10b981;
    color: #ffffff;
    font-size: 16px;
    font-weight: 700;
    padding: 14px;
    border-radius: 10px;
    border: none;
}
QPushButton#btn_pos_large:hover { background-color: #059669; }

QPushButton#btn_outline {
    background-color: transparent;
    border: 2px solid #2563eb;
    color: #2563eb;
    font-weight: bold;
}
QPushButton#btn_outline:checked, QPushButton#btn_outline:hover {
    background-color: #2563eb;
    color: white;
}

/* --- TABLAS --- */
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    color: #334155;
    gridline-color: #f1f5f9;
    font-size: 14px;
}
QTableWidget::item {
    padding: 4px; /* Mayor padding soluciona botones cortados */
}
QTableWidget::item:selected {
    background-color: #eff6ff;
    color: #1e293b;
}

QHeaderView::section {
    background-color: #f1f5f9;
    color: #475569;
    font-weight: bold;
    font-size: 13px;
    padding: 10px;
    border: none;
    border-bottom: 2px solid #e2e8f0;
    border-right: 1px solid #e2e8f0;
}

/* --- INPUTS --- */
QLineEdit, QComboBox, QDateEdit, QDateTimeEdit, QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 8px 12px;
    color: #1e293b;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #3b82f6;
    outline: none;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    selection-background-color: #eff6ff;
    selection-color: #1e293b;
    outline: none;
}

"""

def get_stylesheet(theme="light"):
    if theme == "dark":
        stylesheet = LIGHT_STYLESHEET
        replacements = [
            ("#ffffff", "PLACEHOLDER_BG1"), ("#f8fafc", "PLACEHOLDER_BG2"),
            ("#1e293b", "PLACEHOLDER_TEXT1"), ("#0f172a", "PLACEHOLDER_TEXT2"),
            ("#334155", "PLACEHOLDER_TEXT3"), ("#e2e8f0", "PLACEHOLDER_BORDER"),
            ("#f1f5f9", "PLACEHOLDER_ALT"), ("#cbd5e1", "PLACEHOLDER_MUTED"),
            ("#475569", "PLACEHOLDER_SIDEBAR"), ("#eff6ff", "PLACEHOLDER_SELECT"),
        ]
        for old, placeholder in replacements:
            stylesheet = stylesheet.replace(old, placeholder)
        final_values = {
            "PLACEHOLDER_BG1": "#1e293b", "PLACEHOLDER_BG2": "#0f172a",
            "PLACEHOLDER_TEXT1": "#f8fafc", "PLACEHOLDER_TEXT2": "#ffffff",
            "PLACEHOLDER_TEXT3": "#e2e8f0", "PLACEHOLDER_BORDER": "#334155",
            "PLACEHOLDER_ALT": "#0f172a", "PLACEHOLDER_MUTED": "#475569",
            "PLACEHOLDER_SIDEBAR": "#cbd5e1", "PLACEHOLDER_SELECT": "#3b82f6",
        }
        for placeholder, new in final_values.items():
            stylesheet = stylesheet.replace(placeholder, new)
        return stylesheet
    return LIGHT_STYLESHEET
