@echo off
chcp 65001 >nul
title JP Steam Launcher - Ativar Key

echo.
echo ========================================
echo   JP Steam Launcher - Ativar Key
echo ========================================
echo.
echo 1 key = 1 PC. A key sera vinculada a este computador.
echo.

set /p KEY="Digite sua key (XXXX-XXXX-XXXX): "

if "%KEY%"=="" (
    echo Key nao informada.
    pause
    exit /b 1
)

echo.
echo Ativando...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; " ^
  "try { " ^
  "  $uuid = (Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID; " ^
  "  if (-not $uuid -or $uuid -eq 'FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF') { " ^
  "    $mac = [System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces() | " ^
  "      Where-Object { $_.OperationalStatus -eq 'Up' } | Select-Object -First 1; " ^
  "    $fallback = $mac.GetPhysicalAddress().ToString() + '-' + $env:COMPUTERNAME; " ^
  "    $bytes = [System.Text.Encoding]::UTF8.GetBytes($fallback); " ^
  "  } else { " ^
  "    $bytes = [System.Text.Encoding]::UTF8.GetBytes($uuid); " ^
  "  }; " ^
  "  $sha = [System.Security.Cryptography.SHA256]::Create(); " ^
  "  $hash = $sha.ComputeHash($bytes); " ^
  "  $hwid = ($hash | ForEach-Object { $_.ToString('x2') }) -join ''; " ^
  "  $hwid = $hwid.Substring(0, 32); " ^
  "  $body = @{ key='%KEY%'; hardware_id=$hwid } | ConvertTo-Json; " ^
  "  $resp = Invoke-RestMethod -Uri 'http://191.252.100.71:5050/api/validate' -Method POST -Body $body -ContentType 'application/json' -TimeoutSec 10; " ^
  "  if ($resp.valid -eq $true) { " ^
  "    $dir = Join-Path $env:APPDATA 'JP-Steam-Launcher'; " ^
  "    if (!(Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }; " ^
  "    @{ key='%KEY%' } | ConvertTo-Json | Out-File (Join-Path $dir 'license.json') -Encoding utf8; " ^
  "    Write-Host ''; " ^
  "    Write-Host '========================================'; " ^
  "    Write-Host '  SUCESSO! Key ativada: %KEY%'; " ^
  "    Write-Host '  Agora abra o JP-Steam-Launcher.exe'; " ^
  "    Write-Host '========================================'; " ^
  "  } else { " ^
  "    Write-Host ''; " ^
  "    Write-Host ('  ERRO: ' + $resp.message); " ^
  "  } " ^
  "} catch { " ^
  "  Write-Host ''; " ^
  "  Write-Host ('  ERRO: ' + $_.Exception.Message); " ^
  "}"

echo.
pause
