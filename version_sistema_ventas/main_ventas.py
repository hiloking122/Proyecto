import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

# Importaciones internas del proyecto
from src.styles import get_stylesheet
from src.ui.widgets.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Fuentes y Estilos Globales - Fuente más grande para mejor legibilidad
    font = QFont("Segoe UI", 10)
    font.setHintingPreference(QFont.PreferFullHinting)
    app.setFont(font)
    
    # Estilo Fusion + Stylesheet premium
    app.setStyle("Fusion")
    app.setStyleSheet(get_stylesheet("light"))
    
    window = MainWindow()
    window.theme_mode = 'light'
    window.showMaximized()
    sys.exit(app.exec())
