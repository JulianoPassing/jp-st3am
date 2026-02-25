<#
.SYNOPSIS
    JP Steam Launcher - Adiciona jogos à biblioteca Steam pelo App ID
.DESCRIPTION
    Launcher que instala jogos via SteamTools usando o App ID.
    Em vez de usar o LuaTools como plugin na Steam, este script:
    1. Recebe o App ID do jogo
    2. Baixa manifest + lua dos repositórios da comunidade
    3. Coloca os arquivos nas pastas do SteamTools
    4. Reinicia a Steam
    5. O jogo aparece na biblioteca para download
.NOTES
    Requer: SteamTools instalado, Steam fechada, PowerShell como Admin
    Fontes: ManifestHub, TwentyTwo Cloud (LuaMani providers)
#>

## ================== CONFIG ==================
$Config = @{
    TituloJanela = "JP Steam Launcher | jp-st3am"
    Versao       = "1.0.0"
    
    # Fontes para baixar manifest + lua (ordem de tentativa)
    Fontes = @(
        @{
            Nome = "TwentyTwo Cloud"
            Url  = "http://masss.pythonanywhere.com/storage?auth=IEOIJE54esfsipoE56GE4&appid={0}"
            Tipo = "zip"  # Retorna ZIP completo
        },
        @{
            Nome = "LuaMani/ManifestHub"
            Url  = "https://raw.githubusercontent.com/SteamAutoCracks/ManifestHub/main/{0}.lua"
            Tipo = "lua"  # Fallback: apenas .lua (manifest pode faltar)
        }
    )
}

## ================ VERIFICAR ADMIN ================
$identidade = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal  = New-Object Security.Principal.WindowsPrincipal($identidade)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERRO: Execute como Administrador!" -ForegroundColor Red
    Read-Host "Pressione Enter para sair"
    exit 1
}

## ================== DETECÇÃO STEAM ==================
$steamPath = (Get-ItemProperty "HKLM:\SOFTWARE\WOW6432Node\Valve\Steam" -ErrorAction SilentlyContinue).InstallPath
if (-not $steamPath) {
    Write-Host "Steam nao encontrada. Instale a Steam primeiro." -ForegroundColor Red
    Read-Host "Pressione Enter para sair"
    exit 1
}

$Host.UI.RawUI.WindowTitle = $Config.TituloJanela
$ProgressPreference = 'SilentlyContinue'

## Pastas SteamTools (SteamTools = xinput1_4.dll no Steam)
$pastaStPlugIn   = Join-Path $steamPath "config\stplug-in"
$pastaDepotCache = Join-Path $steamPath "config\depotcache"
if (-not (Test-Path $pastaDepotCache)) {
    $pastaDepotCache = Join-Path $steamPath "depotcache"
}

## Verificar SteamTools
$steamToolsPath = Join-Path $steamPath "xinput1_4.dll"
if (-not (Test-Path $steamToolsPath)) {
    Write-Host ""
    Write-Host "SteamTools nao encontrado!" -ForegroundColor Red
    Write-Host "Instale primeiro com: irm steam.run | iex" -ForegroundColor Yellow
    Write-Host "Ou execute o jp-steam-setup.ps1 para instalar tudo." -ForegroundColor Yellow
    Read-Host "`nPressione Enter para sair"
    exit 1
}

## ================== FUNÇÕES ==================
function Escrever-Log {
    param([string]$Tipo, [string]$Msg)
    $cores = @{ OK = "Green"; INFO = "Cyan"; ERRO = "Red"; AVISO = "Yellow" }
    $hora = Get-Date -Format "HH:mm:ss"
    Write-Host "[$hora] " -NoNewline -ForegroundColor DarkGray
    Write-Host "[$Tipo] " -NoNewline -ForegroundColor $cores[$Tipo]
    Write-Host $Msg
}

function Fechar-Steam {
    $proc = Get-Process steam -ErrorAction SilentlyContinue
    if ($proc) {
        Escrever-Log "INFO" "Fechando Steam..."
        $proc | Stop-Process -Force
        Start-Sleep 2
    }
}

function Adicionar-JogoPorAppId {
    param([string]$AppId)
    
    $AppId = $AppId.Trim()
    if ([string]::IsNullOrWhiteSpace($AppId) -or $AppId -notmatch '^\d+$') {
        Escrever-Log "ERRO" "App ID invalido. Use apenas numeros (ex: 730 para CS2, 271590 para GTA V)"
        return $false
    }

    Escrever-Log "INFO" "Buscando arquivos para App ID: $AppId"
    
    # Criar pastas se nao existirem
    if (-not (Test-Path $pastaStPlugIn))   { New-Item $pastaStPlugIn -ItemType Directory -Force | Out-Null }
    if (-not (Test-Path $pastaDepotCache)) { New-Item $pastaDepotCache -ItemType Directory -Force | Out-Null }

    $tempDir = Join-Path $env:TEMP "jp-launcher-$AppId"
    if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
    New-Item $tempDir -ItemType Directory | Out-Null

    $sucesso = $false

    foreach ($fonte in $Config.Fontes) {
        $url = $fonte.Url -f $AppId
        Escrever-Log "INFO" "Tentando: $($fonte.Nome)..."
        
        try {
            if ($fonte.Tipo -eq "zip") {
                $zipPath = Join-Path $tempDir "game.zip"
                Invoke-WebRequest -Uri $url -OutFile $zipPath -UseBasicParsing -TimeoutSec 15 -ErrorAction Stop
                
                if ((Get-Item $zipPath).Length -lt 100) {
                    Escrever-Log "AVISO" "Resposta vazia ou invalida"
                    continue
                }
                
                Expand-Archive $zipPath $tempDir -Force
                Remove-Item $zipPath -Force
                
                # Copiar .lua para stplug-in
                Get-ChildItem $tempDir -Filter "*.lua" -Recurse | ForEach-Object {
                    Copy-Item $_.FullName $pastaStPlugIn -Force
                    Escrever-Log "OK" "Lua copiado: $($_.Name)"
                }
                # Copiar .manifest para depotcache
                Get-ChildItem $tempDir -Filter "*.manifest" -Recurse | ForEach-Object {
                    Copy-Item $_.FullName $pastaDepotCache -Force
                    Escrever-Log "OK" "Manifest copiado: $($_.Name)"
                }
                # Copiar .vdf (keys) se existir
                $configSteam = Join-Path $steamPath "config"
                Get-ChildItem $tempDir -Filter "*.vdf" -Recurse | ForEach-Object {
                    Copy-Item $_.FullName $configSteam -Force
                    Escrever-Log "OK" "Key copiado: $($_.Name)"
                }
                $sucesso = $true
                break
            }
            elseif ($fonte.Tipo -eq "lua") {
                $luaContent = Invoke-RestMethod -Uri $url -TimeoutSec 10 -ErrorAction Stop
                if ($luaContent -and $luaContent.Length -gt 50 -and $luaContent -notmatch "404") {
                    $luaPath = Join-Path $pastaStPlugIn "$AppId.lua"
                    $luaContent | Set-Content $luaPath -Encoding UTF8
                    Escrever-Log "OK" "Lua salvo: $AppId.lua"
                    $sucesso = $true
                    break
                }
            }
        }
        catch {
            Escrever-Log "AVISO" "Falha: $($_.Exception.Message)"
        }
    }

    Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    return $sucesso
}

## ================== MAIN ==================
Clear-Host
Write-Host ""
Write-Host "  ========================================" -ForegroundColor Cyan
Write-Host "       JP STEAM LAUNCHER - jp-st3am" -ForegroundColor White
Write-Host "       Adiciona jogos por App ID" -ForegroundColor Gray
Write-Host "  ========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  App ID: numero do jogo na Steam" -ForegroundColor DarkGray
Write-Host "  Exemplo: 730 (CS2), 271590 (GTA V), 105600 (Terraria)" -ForegroundColor DarkGray
Write-Host "  Encontre em: steamdb.info ou na URL da loja" -ForegroundColor DarkGray
Write-Host ""

$appId = Read-Host "  Digite o App ID do jogo"

if ([string]::IsNullOrWhiteSpace($appId)) {
    Write-Host "Cancelado." -ForegroundColor Yellow
    Read-Host "Pressione Enter para sair"
    exit 0
}

Fechar-Steam

if (Adicionar-JogoPorAppId -AppId $appId) {
    Escrever-Log "OK" "Jogo adicionado! Reiniciando Steam..."
    Start-Process (Join-Path $steamPath "steam.exe") "-clearbeta"
    Write-Host ""
    Escrever-Log "OK" "Pronto! O jogo deve aparecer na biblioteca."
    Escrever-Log "INFO" "Se nao aparecer, verifique se o manifest existe no ManifestHub."
} else {
    Escrever-Log "ERRO" "Nao foi possivel encontrar os arquivos para este jogo."
    Escrever-Log "INFO" "Tente: steamtools.site, luamani.vercel.app ou manifestlua.blog"
}

Write-Host ""
Read-Host "Pressione Enter para fechar"
