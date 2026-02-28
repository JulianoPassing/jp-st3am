# -*- coding: utf-8 -*-
"""
JP Steam Launcher - Bot Discord
Sistema automático de ativação via tickets.
Usuário abre ticket, envia ID do jogo, bot responde com key + passo a passo.
"""

import os
import sys
import json
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, Select, View

from .config import (
    DISCORD_GUILD_ID,
    get_ticket_category_id,
    get_support_role_id,
    get_bot_token,
    get_api_url,
    get_admin_secret,
    SERVER_DIR,
)

GAMELIST_URL = "https://raw.githubusercontent.com/SteamTools-Team/GameList/main/games.json"
STEAMAPPSLIST_URL = "https://raw.githubusercontent.com/PaulCombal/SteamAppsListDumps/master/game_list.json"
GAMES_CACHE_PATH = os.path.join(SERVER_DIR, "data", "games_cache.json")
STEAMAPPSLIST_CACHE_PATH = os.path.join(SERVER_DIR, "data", "steamappslist_cache.json")
ACTIVATION_CONFIG_PATH = os.path.join(SERVER_DIR, "data", "games_activation.json")
CATALOG_PATH = os.path.join(SERVER_DIR, "data", "games_catalog.json")
BANNER_URL = "https://i.imgur.com/HqiZILA.jpeg"

# Threads de ativação (thread_id). Também identificamos por nome "ativacao-"
activation_threads = set()


def _api_request(method, path, data=None, admin=False):
    url = f"{get_api_url().rstrip('/')}{path}"
    req_data = None
    headers = {"Content-Type": "application/json"}
    if admin:
        headers["Authorization"] = f"Bearer {get_admin_secret()}"
    if data:
        req_data = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=req_data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": str(e.code)}
    except Exception as e:
        return {"error": str(e)}


def _load_activation_config():
    if os.path.exists(ACTIVATION_CONFIG_PATH):
        try:
            with open(ACTIVATION_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"games": [], "default": {"gera_key": True, "steps": [], "links": {}}}


def _load_catalog():
    """Catálogo do usuário: Steam, EA, Ubisoft - jogos para ativação."""
    if os.path.exists(CATALOG_PATH):
        try:
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"steam": [], "ea": [], "ubisoft": []}


def _fetch_gamelist():
    """SteamTools GameList - tem campo drm para priorizar jogos com proteção."""
    if os.path.exists(GAMES_CACHE_PATH):
        try:
            mtime = os.path.getmtime(GAMES_CACHE_PATH)
            if (datetime.now().timestamp() - mtime) < 3600:
                with open(GAMES_CACHE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
    try:
        req = urllib.request.Request(GAMELIST_URL, headers={"User-Agent": "JP-Steam-Bot/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        os.makedirs(os.path.dirname(GAMES_CACHE_PATH), exist_ok=True)
        with open(GAMES_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data
    except Exception:
        if os.path.exists(GAMES_CACHE_PATH):
            with open(GAMES_CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return []


def _fetch_steamappslist():
    """SteamAppsListDumps (PaulCombal) - apenas jogos, sem DLC."""
    if os.path.exists(STEAMAPPSLIST_CACHE_PATH):
        try:
            mtime = os.path.getmtime(STEAMAPPSLIST_CACHE_PATH)
            if (datetime.now().timestamp() - mtime) < 86400:
                with open(STEAMAPPSLIST_CACHE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
    try:
        req = urllib.request.Request(STEAMAPPSLIST_URL, headers={"User-Agent": "JP-Steam-Bot/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        os.makedirs(os.path.dirname(STEAMAPPSLIST_CACHE_PATH), exist_ok=True)
        with open(STEAMAPPSLIST_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data
    except Exception:
        if os.path.exists(STEAMAPPSLIST_CACHE_PATH):
            with open(STEAMAPPSLIST_CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return []


def _get_activation_games_list():
    """Retorna lista de jogos disponíveis (ordem alfabética) para exibir no embed."""
    cfg = _load_activation_config()
    games = cfg.get("games", [])
    games = sorted(games, key=lambda g: (g.get("name") or "?").upper())
    return [(g.get("name", "?"), g.get("appid", "")) for g in games]


def _get_all_games_from_sources():
    """Catálogo do usuário (Steam, EA, Ubisoft) - APENAS jogos para ativação."""
    catalog = _load_catalog()
    seen = set()
    result = []

    for platform in ("steam", "ea", "ubisoft"):
        for g in catalog.get(platform, []):
            name = g.get("name") or "?"
            appid = str(g.get("appid", "")).strip()
            key = appid if appid else name
            if key and key not in seen:
                seen.add(key)
                # value para o Select: appid se tiver, senão name (busca por nome)
                result.append((name, appid if appid else name))

    if result:
        return sorted(result, key=lambda x: (x[0] or "?").upper())

    # Fallback: games_activation se catálogo vazio
    cfg = _load_activation_config()
    for g in cfg.get("games", []):
        appid = str(g.get("appid", ""))
        if appid:
            result.append((g.get("name", "?"), appid))
    return sorted(result, key=lambda x: (x[0] or "?").upper())


def _get_games_by_platform():
    """Retorna jogos agrupados por plataforma: {platform: [(name, appid), ...]}."""
    catalog = _load_catalog()
    result = {"steam": [], "ea": [], "ubisoft": []}

    for platform in ("steam", "ea", "ubisoft"):
        for g in catalog.get(platform, []):
            name = g.get("name") or "?"
            appid = str(g.get("appid", "")).strip()
            result[platform].append((name, appid if appid else name))

    for platform in result:
        result[platform] = sorted(result[platform], key=lambda x: (x[0] or "?").upper())

    if not any(result.values()):
        cfg = _load_activation_config()
        for g in cfg.get("games", []):
            appid = str(g.get("appid", ""))
            if appid:
                result["steam"].append((g.get("name", "?"), appid))
        result["steam"] = sorted(result["steam"], key=lambda x: (x[0] or "?").upper())

    return result


def _get_template_for_platform(platform):
    """Retorna template de ativação por plataforma (steam/ea/ubisoft)."""
    cfg = _load_activation_config()
    templates = cfg.get("activation_templates", {})
    default = cfg.get("default", {})
    if platform == "ea":
        t = templates.get("ea_showcase", {})
        return {"type": t.get("type", "ea_bypass"), "steps": t.get("steps", default.get("steps", [])), "links": t.get("links", default.get("links", {}))}
    if platform == "ubisoft":
        t = templates.get("ubisoft", {})
        return {"type": t.get("type", "bypass"), "steps": t.get("steps", default.get("steps", [])), "links": t.get("links", default.get("links", {}))}
    t = templates.get("steam_launcher", {})
    return {"type": t.get("type", "steam"), "steps": t.get("steps", default.get("steps", [])), "links": t.get("links", default.get("links", {}))}


def _find_game_by_id_or_name(query):
    """Busca jogo: games_activation > catálogo+template > gamelist > steamapps."""
    q = (query or "").strip()
    if not q:
        return None, None

    cfg = _load_activation_config()
    default = cfg.get("default", {})

    # 1. games_activation (instruções customizadas)
    for g in cfg.get("games", []):
        if q == str(g.get("appid", "")) or q.lower() in (g.get("name", "") or "").lower():
            return g, default

    # 2. Catálogo - usa template por plataforma (instruções de ativação)
    catalog = _load_catalog()
    q_lower = q.lower()
    for platform in ("steam", "ea", "ubisoft"):
        for item in catalog.get(platform, []):
            name = item.get("name", "")
            appid = str(item.get("appid", "")).strip()
            if q == appid or (name and q_lower in name.lower()):
                template = _get_template_for_platform(platform)
                tpl = template if isinstance(template, dict) else {}
                return {
                    "appid": appid or "",
                    "name": name or "?",
                    "type": tpl.get("type", "steam"),
                    "gera_key": False,
                    "steps": tpl.get("steps", default.get("steps", [])),
                    "links": tpl.get("links", default.get("links", {})),
                }, default

    # 3. Gamelist / SteamAppsList (fallback - instruções genéricas)
    games = _fetch_gamelist()
    if not isinstance(games, list):
        games = games.get("games", []) if isinstance(games, dict) else []
    for g in games:
        if q == str(g.get("appid", "")) or q_lower in (g.get("name", "") or "").lower():
            return {
                "appid": str(g.get("appid", "")),
                "name": g.get("name", "?"),
                "type": "steam",
                "gera_key": default.get("gera_key", True),
                "steps": default.get("steps", []),
                "links": default.get("links", {}),
            }, default

    steamapps = _fetch_steamappslist()
    apps = steamapps.get("applist", {}).get("apps", []) if isinstance(steamapps, dict) else []
    for g in apps:
        if q == str(g.get("appid", "")) or q_lower in (g.get("name", "") or "").lower():
            return {
                "appid": str(g.get("appid", "")),
                "name": g.get("name", "?"),
                "type": "steam",
                "gera_key": default.get("gera_key", True),
                "steps": default.get("steps", []),
                "links": default.get("links", {}),
            }, default

    return None, None


def _generate_launcher_key():
    """Gera 1 key via API."""
    result = _api_request("POST", "/api/admin/generate", {"quantity": 1}, admin=True)
    if "error" in result:
        return None
    keys = result.get("keys", [])
    return keys[0] if keys else None


def _build_activation_response(game, default, api_base):
    """Monta embed com ativação do jogo: steps e links (sem key do launcher)."""
    cfg = _load_activation_config()
    send_key = cfg.get("send_launcher_key", False) or game.get("gera_key", False) or default.get("gera_key", False)

    steps = game.get("steps", default.get("steps", []))
    links = dict(game.get("links", default.get("links", {})))

    # Inclui links das ferramentas conforme o tipo de jogo
    game_type = game.get("type", "")
    ferramentas = cfg.get("ferramentas", {})
    if ferramentas:
        if game_type in ("denuvo_ticket", "ea_bypass"):
            if "anadius_emu" not in links and "anadius_origin_emu" in ferramentas:
                links["anadius_emu"] = ferramentas["anadius_origin_emu"]
            if "origin_helper" not in links and "anadius_origin_helper" in ferramentas:
                links["origin_helper"] = ferramentas["anadius_origin_helper"]
        elif game_type == "bypass" and "goldberg_emu" not in links and "goldberg_emu" in ferramentas:
            links["goldberg_emu"] = ferramentas["goldberg_emu"]

    key = _generate_launcher_key() if send_key else None

    embed = discord.Embed(
        title=f"🎮 {game.get('name', '?')}",
        description=f"**App ID:** `{game.get('appid', '?')}` • **Tipo:** {game.get('type', 'steam').replace('_', ' ').title()}",
        color=0x10b981,
    )

    if steps:
        embed.add_field(
            name="📋 Passo a passo",
            value="\n".join(steps),
            inline=False,
        )

    link_lines = []
    label_display = {
        "launcher": "Launcher",
        "jogo": "Arquivos do jogo",
        "anadius_emu": "Origin Emulator (Anadius)",
        "origin_helper": "Origin Helper (gerar token)",
        "anadius_dlc_unlockers": "DLC Unlockers (Sims/EA)",
        "goldberg_emu": "Goldberg Steam Emulator",
        "secret_sauce": "Secret Sauce",
        "secret_sauce_2": "Secret Sauce (alt)",
    }
    for label, url in links.items():
        if url.startswith("/"):
            url = f"{api_base.rstrip('/')}{url}"
        lbl = label_display.get(label, label.replace("_", " ").title())
        link_lines.append(f"**{lbl}:** {url}")
    if link_lines:
        embed.add_field(name="🔗 Links", value="\n".join(link_lines), inline=False)

    if key:
        embed.add_field(
            name="🔑 Key do Launcher (opcional)",
            value=f"```\n{key}\n```\nUse se precisar do launcher.",
            inline=False,
        )

    game_type = game.get("type", "")
    footer = "Para jogos Denuvo: envie o arquivo .txt do ticket aqui e aguarde o token."
    if game_type == "denuvo_ticket":
        footer += " Gerar token: Origin Helper (link acima) - Violentmonkey + EA.com com conta do jogo."
    embed.set_footer(text=footer)
    return embed


GAMES_PER_PAGE = 125  # 5 selects x 25 opções
MAX_PAGES = 8         # 8 páginas = 1000 jogos no menu
PLATFORM_LABELS = {"steam": "Steam", "ea": "EA", "ubisoft": "Ubisoft"}


class FeedbackAtivacaoView(View):
    """Botões Deu certo / Não deu após instruções de ativação."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Deu certo", style=discord.ButtonStyle.success, custom_id="feedback_ok")
    async def deu_certo(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        ch = interaction.channel
        if isinstance(ch, discord.Thread):
            try:
                await ch.edit(archived=True)
                await interaction.followup.send("Ticket encerrado com sucesso.", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send("Sem permissão para arquivar.", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"Erro: {e}", ephemeral=True)
        else:
            await interaction.followup.send("Use no ticket de ativação.", ephemeral=True)

    @discord.ui.button(label="Não deu", style=discord.ButtonStyle.danger, custom_id="feedback_fail")
    async def nao_deu(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        ch = interaction.channel
        if isinstance(ch, discord.Thread):
            role_id = get_support_role_id()
            try:
                await ch.send(content=f"<@&{role_id}> O usuário relatou que **não deu certo** com a ativação.")
                await interaction.followup.send("Suporte foi notificado.", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"Erro: {e}", ephemeral=True)
        else:
            await interaction.followup.send("Use no ticket de ativação.", ephemeral=True)


class CombinedTicketView(View):
    """View única com todos os selects (Steam, EA, Ubisoft) — até 5 selects na mesma mensagem."""

    def __init__(self, games_by_platform):
        super().__init__(timeout=None)
        selects_added = 0
        for platform in ("steam", "ea", "ubisoft"):
            if selects_added >= 5:
                break
            jogos = games_by_platform.get(platform, [])
            if not jogos:
                continue
            chunk_size = 25
            chunks = [jogos[i:i + chunk_size] for i in range(0, len(jogos), chunk_size)][:5 - selects_added]
            label_platform = PLATFORM_LABELS.get(platform, platform.title())
            for idx, chunk in enumerate(chunks):
                if selects_added >= 5:
                    break
                options = []
                for name, val in chunk:
                    value = str(val)[:100] if val else ""
                    if not value or not (name or "?").strip():
                        continue
                    label = (name or "?")[:100]
                    desc = f"ID: {val}" if val and val.isdigit() else ""
                    options.append(discord.SelectOption(label=label, value=value, description=desc[:100] if desc else None))
                if not options:
                    options = [discord.SelectOption(label="Nenhum jogo", value="0")]
                custom_id = f"jogos_select_{platform}_{idx}"
                start = idx * 25 + 1
                end = idx * 25 + len(options)
                placeholder = f"{label_platform} — {start}-{end}" if len(chunks) > 1 else f"{label_platform} — escolher..."
                select = Select(custom_id=custom_id, placeholder=placeholder[:150], options=options)
                select.callback = self._on_select
                self.add_item(select)
                selects_added += 1

    async def _on_select(self, interaction: discord.Interaction, select: Select = None):
        try:
            value = (select.values[0] if select and select.values else None) or (interaction.data or {}).get("values", [None])[0]
            if not value or value == "0":
                await interaction.response.send_message("Nenhum jogo selecionado. Digite o ID/nome.", ephemeral=True)
                return
            await interaction.response.defer()
            game, default = _find_game_by_id_or_name(value)
            if not game:
                await interaction.followup.send(f"Jogo não encontrado: `{value}`. Tente novamente.", ephemeral=False)
                return
            api_base = get_api_url().rstrip("/")
            embed = _build_activation_response(game, default, api_base)
            await interaction.followup.send(embed=embed, view=FeedbackAtivacaoView())
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"Erro: {e}", ephemeral=True)
                else:
                    await interaction.followup.send("Erro ao processar. Tente digitar o ID.", ephemeral=False)
            except Exception:
                pass


class PlatformJogosSelectView(View):
    """Menu Select por plataforma (Steam, EA, Ubisoft). Usado em mensagens separadas."""

    def __init__(self, platform, jogos=None):
        super().__init__(timeout=None)
        self.platform = platform
        games_list = jogos if jogos is not None else []
        chunk_size = 25
        chunks = [games_list[i:i + chunk_size] for i in range(0, len(games_list), chunk_size)][:5]
        if not chunks:
            chunks = [[]]

        label_platform = PLATFORM_LABELS.get(platform, platform.title())
        for idx, chunk in enumerate(chunks):
            options = []
            for name, val in chunk:
                value = str(val)[:100] if val else ""
                if not value or not (name or "?").strip():
                    continue
                label = (name or "?")[:100]
                desc = f"ID: {val}" if val and val.isdigit() else ""
                options.append(discord.SelectOption(label=label, value=value, description=desc[:100] if desc else None))
            if not options:
                options = [discord.SelectOption(label="Nenhum jogo", value="0")]
            custom_id = f"jogos_select_{platform}_{idx}"
            start = idx * 25 + 1
            end = idx * 25 + len(options)
            placeholder = f"{label_platform} — {start}-{end}" if len(chunks) > 1 else f"{label_platform} — escolher..."
            select = Select(
                custom_id=custom_id,
                placeholder=placeholder[:150],
                options=options,
            )
            select.callback = self._on_select
            self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction, select: Select = None):
        try:
            value = None
            if select and select.values:
                value = select.values[0]
            elif interaction.data and interaction.data.get("values"):
                value = interaction.data["values"][0]
            if not value or value == "0":
                await interaction.response.send_message(
                    "Nenhum jogo selecionado. Use o menu ou digite o ID/nome.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer()
            game, default = _find_game_by_id_or_name(value)
            if not game:
                await interaction.followup.send(
                    f"Jogo não encontrado: `{value}`. Tente novamente ou digite o ID/nome.",
                    ephemeral=False,
                )
                return

            api_base = get_api_url().rstrip("/")
            embed = _build_activation_response(game, default, api_base)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"Erro ao processar seleção. ({e})",
                        ephemeral=True,
                    )
                else:
                    await interaction.followup.send(
                        f"Erro ao processar. Tente digitar o ID do jogo.",
                        ephemeral=False,
                    )
            except Exception:
                pass


class JogosSelectView(View):
    """Menu Select clicável - uma página (até 125 jogos em 5 selects). Legado para tickets antigos."""

    def __init__(self, jogos=None, page=0):
        super().__init__(timeout=None)
        games_list = jogos if jogos is not None else _get_all_games_from_sources()
        if not games_list:
            games_list = _get_activation_games_list()

        start_idx = page * GAMES_PER_PAGE
        page_games = games_list[start_idx:start_idx + GAMES_PER_PAGE]

        chunk_size = 25
        chunks = [page_games[i:i + chunk_size] for i in range(0, len(page_games), chunk_size)][:5]
        if not chunks and page < MAX_PAGES:
            chunks = [[]]

        for idx, chunk in enumerate(chunks):
            options = []
            for name, val in chunk:
                value = str(val)[:100] if val else ""
                if not value or not (name or "?").strip():
                    continue
                label = (name or "?")[:100]
                desc = f"ID: {val}" if val and val.isdigit() else ""
                options.append(discord.SelectOption(label=label, value=value, description=desc[:100] if desc else None))
            if not options:
                options = [discord.SelectOption(label="Nenhum jogo configurado", value="0")]
            base = page * 5
            custom_id = "jogos_select_ativacao" if (page == 0 and idx == 0) else f"jogos_select_ativacao_{base + idx}"
            start = start_idx + idx * 25 + 1
            end = start_idx + idx * 25 + len(options)
            placeholder = "Clique para escolher um jogo..." if (page == 0 and idx == 0) else f"Jogos {start}-{end}..."
            select = Select(
                custom_id=custom_id,
                placeholder=placeholder[:150],
                options=options,
            )
            select.callback = self._on_select
            self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction, select: Select = None):
        try:
            # Valores podem vir em select.values ou interaction.data (depende da versão do discord.py)
            value = None
            if select and select.values:
                value = select.values[0]
            elif interaction.data and interaction.data.get("values"):
                value = interaction.data["values"][0]
            if not value or value == "0":
                await interaction.response.send_message(
                    "Nenhum jogo selecionado. Use o menu ou digite o ID/nome.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer()

            game, default = _find_game_by_id_or_name(value)
            if not game:
                await interaction.followup.send(
                    f"Jogo não encontrado: `{value}`. Tente novamente ou digite o ID/nome.",
                    ephemeral=False,
                )
                return

            api_base = get_api_url().rstrip("/")
            embed = _build_activation_response(game, default, api_base)
            await interaction.followup.send(embed=embed, view=FeedbackAtivacaoView())
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"Erro ao processar seleção. Tente digitar o ID do jogo. ({e})",
                        ephemeral=True,
                    )
                else:
                    data = interaction.data or {}
                    val = (select.values[0] if select and select.values else None) or (data.get("values") or ["?"])[0]
                    await interaction.followup.send(
                        f"Erro ao processar. Tente digitar o ID do jogo: `{val}`",
                        ephemeral=False,
                    )
            except Exception:
                pass


class AbrirTicketView(View):
    """Botão para abrir ticket de ativação."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Abrir ticket de ativação",
        style=discord.ButtonStyle.primary,
        custom_id="ativar_ticket_btn",
    )
    async def abrir_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)

        user = interaction.user
        guild = interaction.guild

        if not guild:
            await interaction.followup.send("Erro: servidor não encontrado.", ephemeral=True)
            return

        category = guild.get_channel(get_ticket_category_id())
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send(
                "Categoria de tickets não configurada. Contate um administrador.",
                ephemeral=True,
            )
            return

        ticket_channel = None
        is_forum = False
        ForumChannel = getattr(discord, "ForumChannel", None)
        for ch in category.channels:
            if ForumChannel and isinstance(ch, ForumChannel):
                ticket_channel = ch
                is_forum = True
                break
            if isinstance(ch, discord.TextChannel):
                ticket_channel = ch
                break

        if not ticket_channel:
            await interaction.followup.send(
                "Nenhum canal de texto ou fórum na categoria de tickets. Crie um canal na categoria.",
                ephemeral=True,
            )
            return

        games_by_platform = _get_games_by_platform()
        total_jogos = sum(len(g) for g in games_by_platform.values())
        embed_inicial = discord.Embed(
            title="🎮 Ticket de Ativação",
            description=(
                "Bem-vindo ao **JP Steam Launcher**. Selecione um jogo pelo menu ou digite o **ID/nome**.\n\n"
                "**O que você recebe:**\n"
                "▸ Passo a passo completo de instalação\n"
                "▸ Links diretos (Origin Emulator, Anadius, etc.)\n"
                "▸ Instruções específicas por jogo\n\n"
                "**Comando:** Digite `ferramentas` para ver todos os links de ativação.\n\n"
                f"**{total_jogos} jogos** disponíveis em Steam, EA e Ubisoft."
            ),
            color=0x1e3a5f,
        )
        embed_inicial.set_image(url=BANNER_URL)
        embed_inicial.set_footer(text="JP Steam Launcher • Use o menu ou digite o ID/nome do jogo")
        embed_inicial.timestamp = datetime.now(timezone.utc)

        view = CombinedTicketView(games_by_platform)
        content = f"{user.mention}"

        thread_name = f"ativacao-{user.display_name[:20]}-{datetime.now().strftime('%H%M')}"
        try:
            if is_forum:
                thread = await ticket_channel.create_thread(
                    name=thread_name,
                    content=content,
                    embed=embed_inicial,
                    view=view if view.children else None,
                )
            else:
                thread = await ticket_channel.create_thread(
                    name=thread_name,
                    type=discord.ChannelType.private_thread,
                    reason="Ticket de ativação",
                )
                if view.children:
                    await thread.send(content=content, embed=embed_inicial, view=view)
                else:
                    await thread.send(content=content, embed=embed_inicial)
        except discord.Forbidden as e:
            await interaction.followup.send(
                f"Sem permissão para criar ticket. ({e})",
                ephemeral=True,
            )
            return
        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                f"Erro ao criar ticket: {e}",
                ephemeral=True,
            )
            return

        activation_threads.add(thread.id)
        try:
            await thread.add_user(user)
        except discord.Forbidden:
            pass
        for member in guild.members:
            if member.bot:
                continue
            if member.guild_permissions.administrator:
                try:
                    await thread.add_user(member)
                except (discord.Forbidden, discord.HTTPException):
                    pass
        await interaction.followup.send(
            f"Ticket privado criado: {thread.mention}\nEnvie o ID ou nome do jogo lá.",
            ephemeral=True,
        )


class JPSteamBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        guild = discord.Object(id=DISCORD_GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        self.add_view(AbrirTicketView())
        self.add_view(FeedbackAtivacaoView())
        games_by_platform = _get_games_by_platform()
        self.add_view(CombinedTicketView(games_by_platform))
        for platform in ("steam", "ea", "ubisoft"):
            self.add_view(PlatformJogosSelectView(platform=platform, jogos=games_by_platform.get(platform, [])))
        for page in range(MAX_PAGES):
            self.add_view(JogosSelectView(page=page))  # Legado: tickets antigos
        print(f"Comandos sincronizados no servidor {DISCORD_GUILD_ID}")

    async def on_ready(self):
        print(f"Bot conectado como {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Ativações automáticas",
            )
        )


bot = JPSteamBot()


@bot.event
async def on_message(message):
    if message.author.bot:
        await bot.process_commands(message)
        return

    is_activation_thread = (
        isinstance(message.channel, discord.Thread)
        and (
            message.channel.id in activation_threads
            or (message.channel.name or "").startswith("ativacao-")
        )
    )
    if is_activation_thread:
        txt_attach = next((a for a in (message.attachments or []) if a.filename.lower().endswith(".txt")), None)
        if txt_attach:
            await message.channel.typing()
            embed = discord.Embed(
                title="📄 Ticket Denuvo Recebido",
                description=(
                    "Arquivo `.txt` recebido com sucesso.\n\n"
                    "Um administrador irá processar e enviar o **token** aqui.\n"
                    "Aguarde a resposta neste chat."
                ),
                color=0x2563eb,
            )
            embed.set_footer(text="JP Steam Launcher • Token será enviado por um administrador")
            await message.channel.send(embed=embed)
            await bot.process_commands(message)
            return

        query = message.content.strip()
        if not query or len(query) > 200:
            await message.channel.send("Envie um ID (ex: 1349630), nome do jogo, ou o arquivo .txt do ticket.")
            return

        # Resposta rápida: ferramentas/links
        q_lower = query.lower()
        if q_lower in ("ferramentas", "links", "anadius", "tools"):
            cfg = _load_activation_config()
            ferramentas = cfg.get("ferramentas", {})
            if not ferramentas:
                await message.channel.send("Nenhuma ferramenta configurada.")
                return
            lines = []
            labels = {
                "anadius_origin_emu": "Origin Emulator (Anadius)",
                "anadius_origin_helper": "Origin Helper (gerar token Denuvo)",
                "anadius_dlc_unlockers": "DLC Unlockers (Sims/EA)",
                "goldberg_emu": "Goldberg Steam Emulator",
            }
            for k, url in ferramentas.items():
                lbl = labels.get(k, k.replace("_", " ").title())
                lines.append(f"**{lbl}:** {url}")
            embed = discord.Embed(
                title="🔧 Ferramentas de Ativação",
                description="Links diretos — use conforme o tipo de jogo.\n\n" + "\n".join(lines),
                color=0x1e3a5f,
            )
            embed.set_footer(text="Origin Helper: Violentmonkey + EA.com com conta do jogo para gerar token")
            await message.channel.send(embed=embed)
            return

        await message.channel.typing()
        game, default = _find_game_by_id_or_name(query)

        if not game:
            cfg = _load_activation_config()
            games_preview = ", ".join(
                f"{g.get('name')} ({g.get('appid')})"
                for g in cfg.get("games", [])[:5]
            )
            await message.channel.send(
                f"Jogo não encontrado: `{query[:50]}`\n\n"
                f"Jogos configurados: {games_preview or 'nenhum'}\n"
                f"Use o ID numérico ou nome exato."
            )
            return

        api_base = get_api_url().rstrip("/")
        embed = _build_activation_response(game, default, api_base)
        await message.channel.send(embed=embed, view=FeedbackAtivacaoView())

    await bot.process_commands(message)


def _build_ativar_embed():
    """Monta embed profissional para /ativar com banner e lista de jogos por plataforma."""
    games_by_platform = _get_games_by_platform()
    total = sum(len(g) for g in games_by_platform.values())

    if not total:
        games_list = _get_activation_games_list()
        total = len(games_list)
        games_by_platform = {"steam": games_list} if games_list else {}

    fields = []
    for platform in ("steam", "ea", "ubisoft"):
        jogos = games_by_platform.get(platform, [])
        if not jogos:
            continue
        label = PLATFORM_LABELS.get(platform, platform.title())
        preview = [f"• **{name}** `{appid}`" for name, appid in jogos[:5]]
        text = "\n".join(preview)
        if len(jogos) > 5:
            text += f"\n_... +{len(jogos) - 5} jogos_"
        fields.append((f"🎮 {label} ({len(jogos)})", text))

    embed = discord.Embed(
        title="JP Steam Launcher — Ativação de Jogos",
        description=(
            "Abra um **ticket privado** para receber instruções de ativação.\n\n"
            "**No ticket você pode:**\n"
            "▸ Escolher por plataforma (Steam, EA, Ubisoft)\n"
            "▸ Receber passo a passo + links automáticos\n"
            "▸ Digitar o ID ou nome do jogo\n\n"
            f"**{total} jogos** disponíveis"
        ),
        color=0x1e3a5f,
    )
    if fields:
        for name, value in fields:
            embed.add_field(name=name, value=value[:1024] + ("..." if len(value) > 1024 else ""), inline=True)
    else:
        embed.add_field(name="📋 Jogos", value="_Nenhum jogo configurado._", inline=False)
    embed.set_image(url=BANNER_URL)
    embed.set_footer(text="JP Steam Launcher • Clique no botão para abrir o ticket")
    embed.timestamp = datetime.now(timezone.utc)
    return embed


@bot.tree.command(name="ativar", description="Abre ticket para ativação automática de jogos")
async def ativar(interaction: discord.Interaction):
    """Mostra botão para abrir ticket de ativação."""
    await interaction.response.send_message(
        embed=_build_ativar_embed(),
        view=AbrirTicketView(),
        ephemeral=False,
    )


@bot.tree.command(name="pegar-key", description="Solicita uma key do JP Steam Launcher")
async def pegar_key(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(
        title="JP Steam Launcher - Key",
        description="Use `/ativar` e abra um ticket. Envie o ID do jogo para receber a key automaticamente.",
        color=0x2563eb,
    )
    embed.add_field(
        name="Ativação automática",
        value="Clique em **Abrir ticket de ativação** e envie o ID do jogo.",
        inline=False,
    )
    embed.add_field(
        name="Download",
        value=f"[Baixar Launcher]({get_api_url().rstrip('/')}/download/launcher-completo)",
        inline=False,
    )
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="gerar-key", description="[Admin] Gera keys do launcher")
@app_commands.describe(quantidade="Quantidade de keys (1-50)")
@app_commands.default_permissions(administrator=True)
async def gerar_key(interaction: discord.Interaction, quantidade: int = 1):
    await interaction.response.defer(ephemeral=True)
    if quantidade < 1 or quantidade > 50:
        await interaction.followup.send("Quantidade deve ser entre 1 e 50.", ephemeral=True)
        return
    result = _api_request("POST", "/api/admin/generate", {"quantity": quantidade}, admin=True)
    if "error" in result:
        await interaction.followup.send(f"Erro: {result.get('error')}", ephemeral=True)
        return
    keys = result.get("keys", [])
    if not keys:
        await interaction.followup.send("Nenhuma key gerada.", ephemeral=True)
        return
    try:
        dm = await interaction.user.create_dm()
        await dm.send(
            embed=discord.Embed(
                title=f"{len(keys)} keys geradas",
                description=f"```\n{chr(10).join(keys)}\n```",
                color=0x10b981,
            )
        )
        await interaction.followup.send(
            f"**{len(keys)}** keys enviadas no seu DM.",
            ephemeral=True,
        )
    except discord.Forbidden:
        await interaction.followup.send(
            f"**{len(keys)}** keys:\n```\n{chr(10).join(keys[:5])}\n```"
            + (f"\n... e mais {len(keys)-5}" if len(keys) > 5 else ""),
            ephemeral=True,
        )


@bot.tree.command(name="buscar-jogo", description="Busca jogos disponíveis")
@app_commands.describe(nome="Nome do jogo ou App ID")
async def buscar_jogo(interaction: discord.Interaction, nome: str = ""):
    await interaction.response.defer(ephemeral=True)
    games = _fetch_gamelist()
    if not isinstance(games, list):
        games = games.get("games", []) if isinstance(games, dict) else []
    q = (nome or "").lower().strip()
    if q:
        games = [g for g in games if q in (g.get("name") or "").lower() or q in str(g.get("appid", ""))][:15]
    else:
        games = games[:15]
    if not games:
        await interaction.followup.send("Nenhum jogo encontrado.", ephemeral=True)
        return
    lines = [f"• **{g.get('name','?')[:40]}** `ID: {g.get('appid','?')}`" for g in games]
    embed = discord.Embed(
        title="Jogos disponíveis",
        description="\n".join(lines),
        color=0x2563eb,
    )
    embed.set_footer(text="Use /ativar e envie o ID no ticket para ativar.")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="jogos-ativacao", description="Lista jogos com ativação configurada")
async def jogos_ativacao(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    cfg = _load_activation_config()
    games = cfg.get("games", [])
    if not games:
        await interaction.followup.send(
            "Nenhum jogo configurado em data/games_activation.json",
            ephemeral=True,
        )
        return
    lines = [f"• **{g.get('name','?')}** `ID: {g.get('appid','')}` - {g.get('type','?')}" for g in games]
    embed = discord.Embed(
        title="Jogos com ativação automática",
        description="\n".join(lines),
        color=0x2563eb,
    )
    embed.set_footer(text="Use /ativar e envie o ID no ticket.")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="status", description="Status do servidor")
async def status_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        req = urllib.request.Request(
            f"{get_api_url().rstrip('/')}/health",
            headers={"User-Agent": "JP-Steam-Bot/1.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            json.loads(r.read().decode())
        embed = discord.Embed(
            title="Status",
            description="Servidor e bot online.",
            color=0x10b981,
        )
    except Exception as e:
        embed = discord.Embed(
            title="Status",
            description="Servidor offline.",
            color=0xef4444,
        )
        embed.add_field(name="Erro", value=str(e), inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)


def main():
    token = get_bot_token()
    if not token:
        print("Erro: discord_bot_token é obrigatório em config.json")
        sys.exit(1)
    bot.run(token)


if __name__ == "__main__":
    main()
