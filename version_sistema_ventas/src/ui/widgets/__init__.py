"""
Subpaquete de widgets reutilizables.

Exports:
  - MainWindow  → Ventana principal de la aplicación
  - ChartWidget → Widget de gráficos con soporte de tema claro/oscuro
"""
from .main_window import MainWindow
from .chart_widget import ChartWidget

__all__ = ["MainWindow", "ChartWidget"]
