import os
from PySide6.QtGui import QIcon

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
ICONS_DIR = os.path.join(BASE_DIR, 'assets', 'icons')


def load_icon(name: str) -> QIcon:
    """Carga un icono desde assets/icons/{name}.png o .svg si existe. Devuelve QIcon vacío si no hay archivo.
    Uso: from src.icons import load_icon; btn.setIcon(load_icon('search'))
    """
    for ext in ('.png', '.svg', '.ico'):
        path = os.path.join(ICONS_DIR, f"{name}{ext}")
        if os.path.exists(path):
            return QIcon(path)
    return QIcon()
