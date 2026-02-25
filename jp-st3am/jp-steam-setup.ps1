<#
.SYNOPSIS
    JP Steam Setup - Instalador personalizado para plugins Steam (Millennium + LuaTools)
.DESCRIPTION
    Script baseado no LuaToolsSetup, adaptado para o projeto jp-st3am.
    Instala SteamTools, Millennium e o plugin configurado automaticamente.
.NOTES
    Autor: JP | Projeto: jp-st3am
    Requer: PowerShell como Administrador
#>

## ================== SUA CONFIGURAÇÃO ==================
$Config = @{
    NomeProjeto    = "jp-st3am"
    NomePlugin     = "luatools"   # Nome da pasta do plugin em Steam/plugins/
    TituloJanela   = "JP Steam Setup | jp-st3am"
    Versao         = "1.0.0"
    
    # Link do plugin (ZIP) - altere para seu próprio release se tiver
    LinkPlugin     = "https://github.com/madoiscool/ltsteamplugin/releases/latest/download/ltsteamplugin.zip"
    
    # Tempo de espera antes de instalar Millennium (segundos)
    TimerMillenium = 5
    
    # Sua comunidade/Discord (opcional)
    Discord        = ".gg/luatools"
}

## ================ VERIFICAR ADMIN ================
function Testar-Administrador {
    $identidade = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal  = New-Object Security.Principal.WindowsPrincipal($identidade)
    
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Host "ERRO: Execute como Administrador!" -ForegroundColor Red
        Write-Host "Clique com botão direito no PowerShell -> Executar como administrador" -ForegroundColor Yellow
        for ($i = 10; $i -ge 1; $i--) {
            Write-Host "Fechando em $i..." -ForegroundColor DarkGray -NoNewline
            Start-Sleep 1
            Write-Host "`r" -NoNewline
        }
        exit 1
    }
}

Testar-Administrador

## ================== DETECÇÃO STEAM ==================
$steamPath = (Get-ItemProperty "HKLM:\SOFTWARE\WOW6432Node\Valve\Steam" -ErrorAction SilentlyContinue).InstallPath

if (-not $steamPath) {
    Write-Host "Steam nao encontrada no registro. Instale a Steam primeiro." -ForegroundColor Red
    Read-Host "Pressione Enter para sair"
    exit 1
}

$ProgressPreference = 'SilentlyContinue'
$Host.UI.RawUI.WindowTitle = $Config.TituloJanela

## ================== IDIOMA ==================
$Traducoes = @{
    EN = @{
        SteamTools_OK      = "SteamTools already installed"
        SteamTools_Faltando = "SteamTools not found"
        Instalando_ST      = "Installing SteamTools"
        Falha_ST           = "SteamTools installation failed, retrying..."
        Millennium_Faltando = "Millennium not found, installation starts in 5 seconds"
        Millennium_OK      = "Millennium already installed"
        Baixando           = "Downloading"
        Extraindo          = "Extracting"
        Instalado          = "installed"
        PluginAtivado      = "Plugin enabled"
        IniciandoSteam     = "Starting Steam"
        Aguarde            = "Don't close this window yet"
        Concluido          = "Done! You can close this window."
        ExclusaoAntivirus  = "Adding Windows Defender exclusion for Steam folder"
        ExclusaoJaExiste   = "Exclusion already exists"
    }
    BR = @{
        SteamTools_OK      = "SteamTools ja esta instalado"
        SteamTools_Faltando = "SteamTools nao encontrado"
        Instalando_ST      = "Instalando SteamTools"
        Falha_ST           = "Falha ao instalar SteamTools, tentando novamente..."
        Millennium_Faltando = "Millennium nao encontrado, instalacao em 5 segundos"
        Millennium_OK      = "Millennium ja instalado"
        Baixando           = "Baixando"
        Extraindo          = "Extraindo"
        Instalado          = "instalado"
        PluginAtivado      = "Plugin ativado"
        IniciandoSteam     = "Iniciando Steam"
        Aguarde            = "Nao feche esta janela ainda"
        Concluido          = "Pronto! Pode fechar."
        ExclusaoAntivirus  = "Adicionando exclusao do Windows Defender para pasta Steam"
        ExclusaoJaExiste   = "Exclusao ja existe"
    }
}

Write-Host ""
Write-Host "========== $($Config.NomeProjeto) ==========" -ForegroundColor Cyan
Write-Host "  Idioma / Language?" -ForegroundColor White
Write-Host "  [1] English  [2] Portugues (BR)" -ForegroundColor Gray
Write-Host ""

do {
    $escolha = Read-Host "Selecione / Select"
} until ($escolha -in @("1", "2"))

$idioma = if ($escolha -eq "2") { "BR" } else { "EN" }
function T { param($chave) $Traducoes[$idioma][$chave] }

## ================== LOG ==================
function Escrever-Log {
    param([string]$Tipo, [string]$Mensagem)
    $cores = @{ OK = "Green"; INFO = "Cyan"; ERRO = "Red"; AVISO = "Yellow"; LOG = "Magenta" }
    $hora = Get-Date -Format "HH:mm:ss"
    Write-Host "[$hora] " -NoNewline -ForegroundColor DarkGray
    Write-Host "[$Tipo] " -NoNewline -ForegroundColor $cores[$Tipo]
    Write-Host $Mensagem
}

Escrever-Log "INFO" "$($Config.NomeProjeto) v$($Config.Versao)"

## ================== EXCLUSÃO ANTIVÍRUS ==================
$pastaSteam = "C:\Program Files (x86)\Steam"
try {
    $exclusoes = @((Get-MpPreference).ExclusionPath)
    if ($exclusoes -contains $pastaSteam) {
        Escrever-Log "INFO" (T "ExclusaoJaExiste")
    } else {
        Add-MpPreference -ExclusionPath $pastaSteam -ErrorAction Stop
        Escrever-Log "LOG" (T "ExclusaoAntivirus")
    }
} catch {
    Escrever-Log "ERRO" "Nao foi possivel configurar antivirus: $($_.Exception.Message)"
}

## ================== FECHAR STEAM ==================
Get-Process steam -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 2

## ================== STEAMTOOLS ==================
$caminhoSteamTools = Join-Path $steamPath "xinput1_4.dll"

if (Test-Path $caminhoSteamTools) {
    Escrever-Log "OK" (T "SteamTools_OK")
} else {
    $scriptSteam = Invoke-RestMethod "https://steam.run"
    $scriptFiltrado = ($scriptSteam -split "`n" | Where-Object {
        $_ -notmatch "steam\.exe|Start-Sleep|Write-Host|cls|exit"
    }) -join "`n"

    for ($tentativa = 1; $tentativa -le 5; $tentativa++) {
        Escrever-Log "AVISO" (T "Instalando_ST")
        Invoke-Expression $scriptFiltrado *> $null

        if (Test-Path $caminhoSteamTools) { break }
        Escrever-Log "ERRO" (T "Falha_ST")
        Start-Sleep 2
    }
}

## ================== MILLENNIUM ==================
$precisaMillennium = $false
foreach ($arquivo in @("millennium.dll", "python311.dll")) {
    if (-not (Test-Path (Join-Path $steamPath $arquivo))) {
        try {
            Set-MpPreference -DisableRealtimeMonitoring $true -ErrorAction Stop
        } catch { }

        Escrever-Log "LOG" (T "Millennium_Faltando")
        for ($i = $Config.TimerMillenium; $i -gt 0; $i--) {
            Write-Host " $i " -NoNewline -ForegroundColor Magenta
            Start-Sleep 1
        }
        Write-Host ""

        Invoke-Expression "& { $(Invoke-RestMethod 'https://clemdotla.github.io/millennium-installer-ps1/millennium.ps1') } -NoLog -DontStart -SteamPath '$steamPath'"
        $precisaMillennium = $true
        break
    }
}

if ($precisaMillennium) {
    try { Set-MpPreference -DisableRealtimeMonitoring $false -ErrorAction Stop } catch { }
} else {
    Escrever-Log "OK" (T "Millennium_OK")
}

## ================== INSTALAR PLUGIN ==================
$pastaPlugins = Join-Path $steamPath "plugins"
if (-not (Test-Path $pastaPlugins)) {
    New-Item $pastaPlugins -ItemType Directory | Out-Null
}

$pastaPlugin = Join-Path $pastaPlugins $Config.NomePlugin
$arquivoZip = Join-Path $env:TEMP "$($Config.NomePlugin).zip"

Escrever-Log "LOG" "$(T 'Baixando') $($Config.NomePlugin)..."
Invoke-WebRequest $Config.LinkPlugin -OutFile $arquivoZip -UseBasicParsing | Out-Null

Escrever-Log "LOG" "$(T 'Extraindo') $($Config.NomePlugin)..."
Expand-Archive $arquivoZip $pastaPlugin -Force
Remove-Item $arquivoZip -Force -ErrorAction SilentlyContinue

$nomeExibicao = $Config.NomePlugin.Substring(0,1).ToUpper() + $Config.NomePlugin.Substring(1).ToLower()
Escrever-Log "OK" "$nomeExibicao $(T 'Instalado')"

## ================== ATIVAR PLUGIN ==================
$configPath = Join-Path $steamPath "ext/config.json"

if (-not (Test-Path $configPath)) {
    New-Item -Path (Split-Path $configPath) -ItemType Directory -Force | Out-Null
    $config = [PSCustomObject]@{ plugins = @{ enabledPlugins = @($Config.NomePlugin) } }
} else {
    $config = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $config.plugins) { $config | Add-Member plugins ([PSCustomObject]@{}) -Force }
    if (-not $config.plugins.enabledPlugins) { $config.plugins.enabledPlugins = @() }
    if ($config.plugins.enabledPlugins -notcontains $Config.NomePlugin) {
        $config.plugins.enabledPlugins += $Config.NomePlugin
    }
}

$config | ConvertTo-Json -Depth 10 | Set-Content $configPath -Encoding UTF8
Escrever-Log "OK" (T "PluginAtivado")

## ================== INICIAR STEAM ==================
Start-Process (Join-Path $steamPath "steam.exe") "-clearbeta"
Escrever-Log "INFO" (T "IniciandoSteam")
Escrever-Log "OK" (T "Concluido")

Write-Host ""
Read-Host "Pressione Enter para fechar"
