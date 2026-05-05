@echo off
echo Generando Ejecutable Portatil...
pyinstaller --noconfirm --onedir --windowed --name "SistemaVentas" --add-data "assets;assets" main_ventas.py
echo Generando archivo ZIP...
python -m zipfile -c "dist\SistemaVentas_Portable.zip" "dist\SistemaVentas"
echo ============================================================
echo Construcción y compresión finalizada!. Puede encontrar el ZIP en 'dist/SistemaVentas_Portable.zip'
echo ============================================================
pause
