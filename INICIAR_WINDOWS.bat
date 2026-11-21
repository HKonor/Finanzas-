@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -m venv .venv
  if errorlevel 1 goto error
)
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
if errorlevel 1 goto error
if not exist .env copy .env.example .env >nul
python manage.py migrate
if errorlevel 1 goto error
python manage.py cargar_categorias
if errorlevel 1 goto error
echo.
echo Configura ADMIN_PASSWORD en .env y ejecuta: python manage.py crear_admin
echo Abre http://127.0.0.1:8000/login/
python manage.py runserver
exit /b 0
:error
echo No se pudo iniciar. Revisa el error anterior.
pause
exit /b 1
