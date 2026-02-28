# -*- coding: utf-8 -*-
"""
JP Steam Launcher - API de licenciamento
Roda na VPS. Valida keys por Hardware ID (1 key = 1 PC)
"""

import os
import re
import json
import uuid
import sqlite3
import zipfile
import io
import hashlib
import urllib.request
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "keys.db")
DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "downloads")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def _load_config():
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    return cfg


def get_port():
    return int(os.environ.get("PORT") or _load_config().get("port", 5050))


ADMIN_SECRET = os.environ.get("JP_ADMIN_SECRET") or _load_config().get("admin_secret", "altere-isso-em-producao")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            key TEXT PRIMARY KEY,
            hardware_id TEXT,
            activated_at TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization") or request.args.get("secret")
        if auth and auth.replace("Bearer ", "") == ADMIN_SECRET:
            return f(*args, **kwargs)
        return jsonify({"error": "Não autorizado"}), 401
    return decorated


def valid_key_format(key):
    """Formato: XXXX-XXXX-XXXX (12 chars + 2 hífens)"""
    return bool(re.match(r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$", key.upper().replace(" ", "")))


def normalize_key(key):
    return key.upper().replace(" ", "").replace("-", "")[:12]
    # Retorna XXXXXXXXXXXX para lookup (armazenamos com hífens)


@app.route("/api/validate", methods=["POST"])
def validate():
    """Valida key + hardware_id. 1 key = 1 PC."""
    try:
        data = request.get_json() or {}
        key = (data.get("key") or "").strip().upper()
        hardware_id = (data.get("hardware_id") or "").strip()

        if not key or not hardware_id:
            return jsonify({"valid": False, "message": "Key e Hardware ID obrigatórios"}), 400

        # Normalizar key para formato XXXX-XXXX-XXXX
        key_clean = key.replace(" ", "").replace("-", "")
        if len(key_clean) == 12:
            key = f"{key_clean[:4]}-{key_clean[4:8]}-{key_clean[8:12]}"

        conn = get_db()
        row = conn.execute(
            "SELECT key, hardware_id, activated_at FROM keys WHERE key = ?",
            (key,)
        ).fetchone()
        conn.close()

        if not row:
            return jsonify({"valid": False, "message": "Key inválida"})

        stored_hw = row["hardware_id"]
        if not stored_hw:
            # Key existe mas não ativada - ativar agora
            conn = get_db()
            conn.execute(
                "UPDATE keys SET hardware_id = ?, activated_at = ? WHERE key = ?",
                (hardware_id, datetime.utcnow().isoformat(), key)
            )
            conn.commit()
            conn.close()
            return jsonify({"valid": True, "message": "Key ativada com sucesso"})

        if stored_hw != hardware_id:
            return jsonify({"valid": False, "message": "Esta key já está em uso em outro PC"})

        return jsonify({"valid": True, "message": "OK"})

    except Exception as e:
        return jsonify({"valid": False, "message": str(e)}), 500


@app.route("/api/admin/generate", methods=["POST"])
@require_admin
def generate_keys():
    """Gera novas keys. Body: {"quantity": 5}"""
    try:
        data = request.get_json() or {}
        qty = min(int(data.get("quantity", 1)), 100)
        keys = []
        conn = get_db()
        for _ in range(qty):
            raw = uuid.uuid4().hex[:12].upper()
            key = f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}"
            try:
                conn.execute(
                    "INSERT INTO keys (key, created_at) VALUES (?, ?)",
                    (key, datetime.utcnow().isoformat())
                )
                keys.append(key)
            except sqlite3.IntegrityError:
                continue
        conn.commit()
        conn.close()
        return jsonify({"keys": keys, "count": len(keys)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/list", methods=["GET"])
@require_admin
def list_keys():
    """Lista todas as keys."""
    conn = get_db()
    rows = conn.execute(
        "SELECT key, hardware_id, activated_at, created_at FROM keys ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return jsonify({
        "keys": [
            {
                "key": r["key"],
                "hardware_id": r["hardware_id"] or "-",
                "activated_at": r["activated_at"] or "-",
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    })


@app.route("/api/admin/revoke", methods=["POST"])
@require_admin
def revoke_key():
    """Revoga uma key (remove o hardware_id para permitir reativação)."""
    data = request.get_json() or {}
    key = (data.get("key") or "").strip().upper()
    if not key:
        return jsonify({"error": "Key obrigatória"}), 400
    key_clean = key.replace(" ", "").replace("-", "")
    if len(key_clean) == 12:
        key = f"{key_clean[:4]}-{key_clean[4:8]}-{key_clean[8:12]}"
    conn = get_db()
    conn.execute(
        "UPDATE keys SET hardware_id = NULL, activated_at = NULL WHERE key = ?",
        (key,)
    )
    conn.commit()
    affected = conn.total_changes
    conn.close()
    return jsonify({"ok": True, "revoked": affected > 0})


@app.route("/download/launcher")
def download_launcher():
    """Serve o EXE do launcher para download."""
    exe_path = os.path.join(DOWNLOAD_DIR, "JP-Steam-Launcher.exe")
    if not os.path.exists(exe_path):
        return jsonify({"error": "Launcher não disponível. Faça upload do EXE em server/downloads/"}), 404
    return send_file(exe_path, as_attachment=True, download_name="JP-Steam-Launcher.exe")


@app.route("/download/permitir-firewall")
def download_permitir_firewall():
    """Serve o .bat para permitir o launcher no firewall."""
    bat_path = os.path.join(DOWNLOAD_DIR, "PermitirFirewall.bat")
    if not os.path.exists(bat_path):
        return jsonify({"error": "PermitirFirewall.bat não encontrado em server/downloads/"}), 404
    return send_file(bat_path, as_attachment=True, download_name="PermitirFirewall.bat")


@app.route("/download/launcher-completo")
def download_launcher_completo():
    """Serve ZIP com launcher + scripts auxiliares."""
    exe_path = os.path.join(DOWNLOAD_DIR, "JP-Steam-Launcher.exe")
    if not os.path.exists(exe_path):
        return jsonify({"error": "Launcher não disponível. Faça upload do EXE em server/downloads/"}), 404
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(exe_path, "JP-Steam-Launcher.exe")
        for bat in ["AtivarKey.bat", "PermitirFirewall.bat"]:
            p = os.path.join(DOWNLOAD_DIR, bat)
            if os.path.exists(p):
                z.write(p, bat)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="JP-Steam-Launcher.zip",
                    mimetype="application/zip")


@app.route("/api/launcher/version")
def launcher_version():
    """Retorna hash SHA256 do EXE atual para auto-update."""
    exe_path = os.path.join(DOWNLOAD_DIR, "JP-Steam-Launcher.exe")
    if not os.path.exists(exe_path):
        return jsonify({"error": "Launcher não disponível"}), 404
    sha = hashlib.sha256()
    with open(exe_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return jsonify({
        "hash": sha.hexdigest(),
        "size": os.path.getsize(exe_path),
        "download_url": f"{request.host_url}download/launcher",
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# === PAINEL E API DE JOGOS ===
GAMELIST_URL = "https://raw.githubusercontent.com/SteamTools-Team/GameList/main/games.json"
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
GAMES_CACHE_PATH = os.path.join(DATA_DIR, "games_cache.json")
ACTIVATION_CONFIG_PATH = os.path.join(DATA_DIR, "games_activation.json")


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_activation_config():
    _ensure_data_dir()
    if os.path.exists(ACTIVATION_CONFIG_PATH):
        try:
            with open(ACTIVATION_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"games": [], "sources": {}}


def _fetch_gamelist():
    _ensure_data_dir()
    if os.path.exists(GAMES_CACHE_PATH):
        try:
            mtime = os.path.getmtime(GAMES_CACHE_PATH)
            if (datetime.now().timestamp() - mtime) < 3600:
                with open(GAMES_CACHE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
    try:
        req = urllib.request.Request(GAMELIST_URL, headers={"User-Agent": "JP-Steam/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        with open(GAMES_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data
    except Exception:
        if os.path.exists(GAMES_CACHE_PATH):
            with open(GAMES_CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return []


@app.route("/api/games/search")
def api_games_search():
    """Busca jogos. Query: ?q=nome&limit=50"""
    q = (request.args.get("q") or "").lower().strip()
    limit = min(int(request.args.get("limit", 50)), 100)
    games = _fetch_gamelist()
    if not isinstance(games, list):
        games = games.get("games", []) if isinstance(games, dict) else []
    if q:
        games = [g for g in games if q in (g.get("name") or "").lower() or q in str(g.get("appid", ""))][:limit]
    else:
        games = games[:limit]
    return jsonify({"games": games, "total": len(games)})


@app.route("/api/games/activation")
def api_games_activation():
    """Lista jogos que precisam de ativação especial."""
    return jsonify(_load_activation_config())


@app.route("/api/admin/sync-gamelist", methods=["POST"])
@require_admin
def api_sync_gamelist():
    """Força sync da lista de jogos do SteamTools."""
    try:
        data = _fetch_gamelist()
        total = len(data) if isinstance(data, list) else 0
        return jsonify({"ok": True, "count": total})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/panel")
def panel():
    """Painel web com jogos e opções."""
    activation = _load_activation_config()
    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JP Steam Launcher - Painel</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: system-ui, sans-serif; background: #1a1a1a; color: #fff; min-height: 100vh; padding: 24px; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        h1 {{ color: #2563eb; margin-bottom: 24px; font-size: 1.5rem; }}
        .card {{ background: #252525; border-radius: 8px; padding: 20px; margin-bottom: 16px; border: 1px solid #333; }}
        .card h2 {{ font-size: 1rem; margin-bottom: 12px; color: #b0b0b0; }}
        a {{ color: #2563eb; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .btn {{ display: inline-block; background: #2563eb; color: #fff; padding: 10px 20px; border-radius: 6px; margin-top: 8px; }}
        .btn:hover {{ background: #1d4ed8; }}
        ul {{ list-style: none; }}
        li {{ padding: 6px 0; border-bottom: 1px solid #333; }}
        li:last-child {{ border: none; }}
        .meta {{ font-size: 0.85rem; color: #888; margin-top: 4px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>JP Steam Launcher - Painel</h1>
        
        <div class="card">
            <h2>Download</h2>
            <a href="/download/launcher-completo" class="btn">Baixar Launcher (ZIP)</a>
        </div>
        
        <div class="card">
            <h2>Jogos com ativação especial</h2>
            <ul>
                {"".join(f'<li><strong>{g.get("name", "?")}</strong> (ID: {g.get("appid", "")}) - {g.get("type", "?")}<span class="meta">{g.get("instructions", "")}</span></li>' for g in activation.get("games", [])) or "<li>Nenhum jogo configurado. Edite data/games_activation.json</li>"}
            </ul>
            <p class="meta" style="margin-top:12px">Config: data/games_activation.json</p>
        </div>
        
        <div class="card">
            <h2>API</h2>
            <ul>
                <li><a href="/api/games/search">/api/games/search?q=nome</a> - Buscar jogos</li>
                <li><a href="/api/games/activation">/api/games/activation</a> - Jogos com ativação</li>
                <li><a href="/health">/health</a> - Status</li>
            </ul>
        </div>
    </div>
</body>
</html>
"""


if __name__ == "__main__":
    init_db()
    port = get_port()
    print(f"Servidor de licenças rodando em http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port)
