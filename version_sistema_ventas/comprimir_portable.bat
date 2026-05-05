@echo off
echo Generando archivo ZIP del Portable...
python -m zipfile -c "dist\SistemaVentas_Portable.zip" "dist\SistemaVentas"
echo ============================================================
echo Compresión finalizada!. Puede encontrar el ZIP en 'dist\SistemaVentas_Portable.zip'
echo ============================================================
pause
