# 📁 Estructura del Proyecto — VentasPro (Impresiones Yonathan)

> Última actualización: 2026-03-22

## Árbol de directorios

```
version_sistema_ventas/           ← Raíz del código fuente
│
├── main_ventas.py                ← Punto de entrada de la aplicación
├── portable.spec                 ← Spec de PyInstaller (onefile portátil)
├── reconstruir_ejecutable.bat    ← Script de construcción automatizado
├── requirements.txt              ← Dependencias Python del proyecto
├── exchange_cache.json           ← Caché de tasas de cambio BCV/USD
│
├── assets/                       ← Recursos estáticos
│   ├── app_icon.ico              ← Ícono del ejecutable
│   └── icons/                    ← Íconos adicionales de la UI
│
├── data/                         ← Datos de referencia (categorías, etc.)
│
└── src/                          ← Paquete principal del proyecto
    ├── __init__.py               ← Silencia warnings de pkg_resources
    │
    ├── database/                 ← Capa de datos (SQLite)
    │   ├── __init__.py           ← Exporta DatabaseManager
    │   ├── db_manager.py         ← CRUD completo + configuración
    │   └── finanzas_pro.db       ← Base de datos SQLite (NO incluir en VCS)
    │
    ├── ui/                       ← Paquete de interfaz de usuario
    │   ├── __init__.py
    │   │
    │   ├── widgets/              ← Componentes visuales principales
    │   │   ├── __init__.py       ← Exporta MainWindow, ChartWidget
    │   │   ├── main_window.py    ← Ventana principal (3350 líneas)
    │   │   └── chart_widget.py   ← Widget de gráficos matplotlib
    │   │
    │   └── dialogs/              ← Diálogos modales
    │       ├── __init__.py       ← Exporta todos los dialogs
    │       ├── transaction_dialog.py
    │       ├── payment_history_dialog.py
    │       ├── sale_details_dialog.py
    │       ├── client_dialog.py
    │       ├── service_dialog.py
    │       ├── product_dialog.py
    │       └── help_dialog.py
    │
    ├── exchange.py               ← Tasas de cambio BCV / paralelo
    ├── notifications.py          ← Sistema de recordatorios (APScheduler)
    ├── styles.py                 ← Stylesheets Qt (temas claro/oscuro)
    ├── icons.py                  ← Carga de íconos desde assets/
    └── search.py                 ← Búsqueda global con FTS + rapidfuzz
```

```
Ejecutable/                       ← Carpeta de distribución (generada)
├── VentasPro_Portable.exe        ← Ejecutable portátil (≈120 MB)
├── finanzas_pro.db               ← Base de datos del cliente
└── exchange_cache.json           ← Caché de tasas (opcional)
```

---

## Cómo construir el ejecutable

### Opción A — Usando el script `.bat` (recomendado)

```bat
:: Desde el Explorador: doble clic en reconstruir_ejecutable.bat
:: El script:
::   1. Verifica que PyInstaller esté instalado
::   2. Limpia build/ y dist/ anteriores
::   3. Limpia todos los __pycache__
::   4. Construye con PyInstaller usando portable.spec
::   5. Copia VentasPro_Portable.exe y finanzas_pro.db a ..\Ejecutable\
```

### Opción B — Desde la terminal

```powershell
# Activar el entorno virtual
cd "e:\Impresiones yonathan - copia\version_sistema_ventas"
.\.venv\Scripts\activate

# Instalar / actualizar dependencias
pip install -r requirements.txt
pip install pyinstaller

# Construir
pyinstaller --noconfirm portable.spec

# El exe queda en: dist\VentasPro_Portable.exe
```

---

## Dependencias principales

| Paquete | Uso |
|---|---|
| `PySide6` | Framework Qt 6 — UI completa |
| `matplotlib` | Gráficos del dashboard y reportes |
| `pandas` | Importación/exportación de CSV/Excel |
| `openpyxl` | Lectura/escritura de archivos Excel |
| `rapidfuzz` | Búsqueda difusa en productos y clientes |
| `apscheduler` | Scheduler de notificaciones/recordatorios |
| `win10toast` | Notificaciones nativas de Windows |
| `requests` | Descarga de tasas de cambio (BCV API) |
| `qtawesome` | Íconos FontAwesome en la UI |
| `pyinstaller` | Empaquetado en ejecutable portable |

---

## Reglas importantes del proyecto

1. **La BD no va en el repositorio** — `src/database/finanzas_pro.db` está en `.gitignore`
2. **Ejecutar siempre desde `version_sistema_ventas/`** — los imports `src.*` son relativos a esta raíz
3. **No mezclar la carpeta `Ejecutable/`** con el código fuente — es sólo para distribución
4. **PyInstaller debe correr con el `.venv` activo** para que encuentre todas las dependencias
