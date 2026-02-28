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
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

from .config import (
    DISCORD_GUILD_ID,
    get_ticket_category_id,
    get_bot_token,
    get_api_url,
    get_admin_secret,
    SERVER_DIR,
)

GAMELIST_URL = "https://raw.githubusercontent.com/SteamTools-Team/GameList/main/games.json"
GAMES_CACHE_PATH = os.path.join(SERVER_DIR, "data", "games_cache.json")
ACTIVATION_CONFIG_PATH = os.path.join(SERVER_DIR, "data", "games_activation.json")
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


def _fetch_gamelist():
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


def _get_activation_games_list():
    """Retorna lista de jogos disponíveis (ordem alfabética) para exibir no embed."""
    cfg = _load_activation_config()
    games = cfg.get("games", [])
    games = sorted(games, key=lambda g: (g.get("name") or "?").upper())
    return [(g.get("name", "?"), g.get("appid", "")) for g in games]


def _find_game_by_id_or_name(query):
    """Busca jogo em games_activation primeiro, depois no gamelist."""
    q = (query or "").strip()
    if not q:
        return None, None

    cfg = _load_activation_config()
    for g in cfg.get("games", []):
        if q == str(g.get("appid", "")) or q.lower() in (g.get("name", "") or "").lower():
            return g, cfg.get("default", {})

    games = _fetch_gamelist()
    if not isinstance(games, list):
        games = games.get("games", []) if isinstance(games, dict) else []
    q_lower = q.lower()
    for g in games:
        if q == str(g.get("appid", "")) or q_lower in (g.get("name", "") or "").lower():
            default = cfg.get("default", {})
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
    links = game.get("links", default.get("links", {}))

    key = _generate_launcher_key() if send_key else None

    embed = discord.Embed(
        title=f"Ativação: {game.get('name', '?')}",
        description=f"**App ID:** {game.get('appid', '?')}\n**Tipo:** {game.get('type', 'steam')}",
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

    embed.set_footer(text="Para jogos Denuvo: envie o arquivo .txt do ticket aqui e aguarde o token.")
    return embed


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
        for ch in category.channels:
            if isinstance(ch, discord.TextChannel):
                ticket_channel = ch
                break

        if not ticket_channel:
            await interaction.followup.send(
                "Nenhum canal de texto na categoria de tickets. Crie um canal na categoria.",
                ephemeral=True,
            )
            return

        thread_name = f"ativacao-{user.display_name[:20]}-{datetime.now().strftime('%H%M')}"
        try:
            thread = await ticket_channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.private_thread,
                reason="Ticket de ativação",
            )
        except discord.Forbidden as e:
            await interaction.followup.send(
                f"Sem permissão para criar thread privada. Verifique se o canal permite threads privadas. ({e})",
                ephemeral=True,
            )
            return
        except Exception as e:
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

        games_list = _get_activation_games_list()
        if games_list:
            lines = [f"• **{name}** — `{appid}`" for name, appid in games_list]
            games_text = "\n".join(lines)
        else:
            games_text = "_Nenhum jogo configurado._"

        embed_inicial = discord.Embed(
            title="Ticket de Ativação — JP Steam Launcher",
            description=(
                "**Envie o ID ou o nome do jogo** que deseja ativar.\n\n"
                "O bot responderá automaticamente com:\n"
                "• Passo a passo de instalação\n"
                "• Links para download\n"
                "• Instruções específicas do jogo\n\n"
                "**Jogos disponíveis:**"
            ),
            color=0x6366f1,
        )
        embed_inicial.add_field(
            name="📋 Lista",
            value=games_text[:1024] + ("..." if len(games_text) > 1024 else ""),
            inline=False,
        )
        embed_inicial.set_image(url=BANNER_URL)
        embed_inicial.set_footer(text="Aguardando sua mensagem...")

        await thread.send(content=f"{user.mention}", embed=embed_inicial)
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
                title="Ticket recebido",
                description=(
                    "Arquivo de ticket Denuvo recebido.\n\n"
                    "Um administrador irá processar e enviar o token aqui.\n"
                    "Aguarde a resposta neste chat."
                ),
                color=0x2563eb,
            )
            embed.set_footer(text="Envie o token gerado para o usuário quando estiver pronto.")
            await message.channel.send(embed=embed)
            await bot.process_commands(message)
            return

        query = message.content.strip()
        if not query or len(query) > 200:
            await message.channel.send("Envie um ID (ex: 1349630), nome do jogo, ou o arquivo .txt do ticket.")
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
        await message.channel.send(embed=embed)

    await bot.process_commands(message)


def _build_ativar_embed():
    """Monta embed profissional para /ativar com banner e lista de jogos."""
    games_list = _get_activation_games_list()
    if games_list:
        lines = [f"• **{name}** `ID: {appid}`" for name, appid in games_list]
        games_text = "\n".join(lines)
    else:
        games_text = "_Nenhum jogo configurado nas fontes._"

    embed = discord.Embed(
        title="JP Steam Launcher — Ativação de Jogos",
        description=(
            "Clique no botão abaixo para abrir um **ticket privado** de ativação.\n\n"
            "No ticket, envie o **ID ou nome do jogo** e receba automaticamente:\n"
            "• Passo a passo de instalação\n"
            "• Links para download (Secret Sauce, arquivos do jogo)\n"
            "• Instruções específicas para cada jogo\n\n"
            "**Jogos disponíveis nas fontes:**"
        ),
        color=0x6366f1,
    )
    embed.add_field(
        name="📋 Lista de jogos",
        value=games_text[:1024] + ("..." if len(games_text) > 1024 else ""),
        inline=False,
    )
    embed.set_image(url=BANNER_URL)
    embed.set_footer(text="Use o ID numérico ou nome do jogo no ticket")
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
