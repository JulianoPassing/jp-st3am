@echo off
if "%~1"=="" (
    start "JP Steam - Remover build" cmd /k "%~f0" run
    exit /b
)
chcp 65001 >nul
cd /d "%~dp0"
title Remover build do Git - JP Steam Launcher

echo.
echo === Remover build do Git ===
echo.
echo Procurando Git...
set GIT=
where git >nul 2>&1 && set GIT=git
if "%GIT%"=="" if exist "C:\Program Files\Git\cmd\git.exe" set GIT="C:\Program Files\Git\cmd\git.exe"
if "%GIT%"=="" if exist "C:\Program Files\Git\bin\git.exe" set GIT="C:\Program Files\Git\bin\git.exe"
if "%GIT%"=="" if exist "C:\Program Files (x86)\Git\bin\git.exe" set GIT="C:\Program Files (x86)\Git\bin\git.exe"
if "%GIT%"=="" if exist "%LOCALAPPDATA%\Programs\Git\bin\git.exe" set GIT="%LOCALAPPDATA%\Programs\Git\bin\git.exe"

if "%GIT%"=="" (
    echo.
    echo Git nao encontrado!
    echo.
    echo Opcao 1: Instale o Git em https://git-scm.com/download/win
    echo Opcao 2: Use o Cursor - Source Control ^(Ctrl+Shift+G^)
    echo Opcao 3: Exclua manualmente launcher\dist e launcher\build
    echo.
    goto :fim
)

echo Git encontrado.
echo.
echo Removendo launcher/dist do controle do Git...
%GIT% rm -r --cached launcher/dist 2>nul
echo Removendo launcher/build...
%GIT% rm -r --cached launcher/build 2>nul
echo Removendo .spec...
%GIT% rm --cached "launcher/JP-Steam-Launcher.spec" 2>nul
echo.
echo Adicionando .gitignore...
%GIT% add .gitignore
echo.
echo Pronto! Faca commit e push pelo Cursor ^(Ctrl+Shift+G^)
echo.
:fim
echo.
echo Pressione qualquer tecla para fechar...
pause
