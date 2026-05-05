"""
Subpaquete de diálogos modales del Sistema de Ventas.

Exports:
  - TransactionDialog      → Registrar ingresos/gastos
  - PaymentHistoryDialog   → Historial de pagos de una deuda
  - SaleDetailsDialog      → Detalle de una venta
  - ClientDialog           → Alta/edición de clientes
  - ServiceDialog          → Alta/edición de servicios
  - ProductDialog          → Alta/edición de productos
  - HelpDialog             → Ayuda y atajos de teclado
"""
from .transaction_dialog      import TransactionDialog
from .payment_history_dialog  import PaymentHistoryDialog
from .sale_details_dialog     import SaleDetailsDialog
from .client_dialog           import ClientDialog
from .service_dialog          import ServiceDialog
from .product_dialog          import ProductDialog
from .help_dialog             import HelpDialog

__all__ = [
    "TransactionDialog",
    "PaymentHistoryDialog",
    "SaleDetailsDialog",
    "ClientDialog",
    "ServiceDialog",
    "ProductDialog",
    "HelpDialog",
]
