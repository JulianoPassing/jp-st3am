@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Iniciando servidor de licenças...
set JP_ADMIN_SECRET=altere-isso
pip install -r requirements.txt -q
python app.py
