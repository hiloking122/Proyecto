"""
Subpaquete de acceso a datos (SQLite).

Exports:
  - DatabaseManager → Gestor central de la base de datos (CRUD + configuración)
"""
from .db_manager import DatabaseManager

__all__ = ["DatabaseManager"]
