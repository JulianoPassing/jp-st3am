@echo off
chcp 65001 >nul
echo ========================================
echo   JP Steam Launcher - Build EXE
echo   JP. Sistemas
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] Instalando dependencias...
pip install customtkinter pyinstaller requests --quiet

echo [2/3] Baixando logo e gerando icone...
pip install Pillow --quiet
python fetch_logo.py
python create_icon.py

echo [3/3] Compilando EXE...
if exist "icon.ico" (
    if exist "logo_site.png" (
        if exist "..\jp-steam-setup.ps1" (
            pyinstaller --noconfirm --onefile --windowed --name "JP-Steam-Launcher" --icon=icon.ico --add-data "icon.ico;." --add-data "logo_site.png;." --add-data "..\jp-steam-setup.ps1;." launcher.py
        ) else (
            pyinstaller --noconfirm --onefile --windowed --name "JP-Steam-Launcher" --icon=icon.ico --add-data "icon.ico;." --add-data "logo_site.png;." launcher.py
        )
    ) else (
        pyinstaller --noconfirm --onefile --windowed --name "JP-Steam-Launcher" --icon=icon.ico --add-data "icon.ico;." launcher.py
    )
) else (
    pyinstaller --noconfirm --onefile --windowed --name "JP-Steam-Launcher" launcher.py
)

if exist "dist\JP-Steam-Launcher.exe" (
    echo.
    echo ========================================
    echo   SUCESSO!
    echo   Executavel: dist\JP-Steam-Launcher.exe
    echo ========================================
    explorer dist
) else (
    echo.
    echo ERRO na compilacao. Verifique os logs acima.
    pause
)
