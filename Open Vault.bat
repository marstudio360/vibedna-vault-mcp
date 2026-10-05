@echo off
REM Doble click y se abre tu vault. Busca el python del entorno del propio paquete y,
REM si no esta, el del sistema: un comprador no tiene por que saber cual es cual.
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "vault_ui.py"
) else (
  start "" pythonw "vault_ui.py"
)
