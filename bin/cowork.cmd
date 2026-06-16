@echo off
REM Lanzador de cowork para Windows. Ejecuta el script con el Python del sistema
REM conservando la carpeta actual (el proyecto se identifica por donde estes).
python "%~dp0..\cowork.py" %*
