# -*- coding: utf-8 -*-
"""Configuração do bot Discord JP Steam Launcher."""

import os
import json

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.dirname(BOT_DIR)
CONFIG_PATH = os.path.join(SERVER_DIR, "config.json")

# IDs do Discord
DISCORD_GUILD_ID = 1477391471752773754
DISCORD_BOT_ID = 1477391841488801953


def get_ticket_category_id():
    return int(_load().get("ticket_category_id", 1477393102246379600))


def get_support_role_id():
    """ID do cargo para marcar quando 'Não deu'."""
    return int(_load().get("support_role_id", 1477397336572559461))

# Carregar config
def _load():
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    return cfg

def get_bot_token():
    t = os.environ.get("DISCORD_BOT_TOKEN") or _load().get("discord_bot_token", "")
    return (t or "").strip()

def get_api_url():
    return os.environ.get("JP_LICENSE_URL") or _load().get("license_server", "http://localhost:5050")

def get_admin_secret():
    return os.environ.get("JP_ADMIN_SECRET") or _load().get("admin_secret", "altere-isso-em-producao")
