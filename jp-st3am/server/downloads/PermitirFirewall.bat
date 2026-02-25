@echo off
chcp 65001 >nul
title JP Steam Launcher - Permitir no Firewall

:: Verifica se está rodando como administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Solicitando permissao de administrador...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo.
echo ========================================
echo   JP Steam Launcher - Permitir Firewall
echo ========================================
echo.

set "EXE=%~dp0JP-Steam-Launcher.exe"
if not exist "%EXE%" (
    echo ERRO: JP-Steam-Launcher.exe nao encontrado.
    echo Coloque este .bat na mesma pasta do launcher.
    echo.
    pause
    exit /b 1
)

echo Removendo regra antiga (se existir)...
netsh advfirewall firewall delete rule name="JP-Steam-Launcher" >nul 2>&1

echo Adicionando regra no firewall...
netsh advfirewall firewall add rule name="JP-Steam-Launcher" dir=out action=allow program="%EXE%"

if %errorLevel% equ 0 (
    echo.
    echo ========================================
    echo   SUCESSO! Firewall configurado.
    echo   Agora voce pode abrir o launcher.
    echo ========================================
) else (
    echo.
    echo ERRO ao configurar o firewall.
)

echo.
pause
