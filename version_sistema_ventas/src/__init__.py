"""Módulo principal del prototipo: intercambio, búsqueda y recordatorios.

Silenciamos advertencias conocidas de dependencias que están fuera de nuestro control (ej: pkg_resources).
"""

import warnings
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

__all__ = ["exchange", "search", "notifications", "subscription", "export"]
