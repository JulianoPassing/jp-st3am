# Fontes de Jogos para Ativação

Pesquisa de fontes que listam jogos com ativação, cracks, Denuvo, DRM, etc.

## Fontes em uso

### 1. SteamTools GameList (principal)
- **URL:** https://raw.githubusercontent.com/SteamTools-Team/GameList/main/games.json
- **Formato:** JSON array com `appid`, `name`, `type`, `tags`, `nsfw`, `drm`
- **Jogos:** ~50k+
- **Vantagem:** Campo `drm: true` indica jogos com proteção (prioridade no menu)
- **Atualização:** Diária

### 2. SteamAppsListDumps (PaulCombal)
- **URL:** https://raw.githubusercontent.com/PaulCombal/SteamAppsListDumps/master/game_list.json
- **Formato:** `applist.apps` com `appid`, `name`
- **Vantagem:** Apenas jogos (type=game), sem DLC
- **Atualização:** Manual

### 3. games_activation.json (local)
- **Arquivo:** `data/games_activation.json`
- **Prioridade:** Máxima — jogos com instruções customizadas (Denuvo ticket, bypass, etc.)

---

## Fontes pesquisadas (não integradas)

### CrackWatch API
- **URL:** https://api.crackwatch.com/api/games
- **Dados:** Status de crack, DRM (Denuvo, SecuROM, VMProtect)
- **Problema:** API instável (502), formato usa `slug` em vez de appid Steam

### RAWG API
- **URL:** https://api.rawg.io/apidocs
- **Dados:** 500k+ jogos, coleção Denuvo
- **Problema:** Requer API key, limite de requisições

### Steam API GetAppList
- **URL:** https://api.steampowered.com/ISteamApps/GetAppList/v0001/
- **Problema:** Endpoint retorna 404 (descontinuado?)

### SteamList/SteamDRM
- **URL:** https://github.com/SteamList/SteamDRM
- **Dados:** Lista de DRM de terceiros no Steam
- **Problema:** Projeto em PHP, sem JSON público

### PCGamingWiki
- **URL:** https://www.pcgamingwiki.com/wiki/The_Big_List_of_3rd_Party_DRM_on_Steam
- **Dados:** Lista comunitária de DRM
- **Problema:** Wiki HTML, não estruturado para API

### CrackRelease / UVList
- **Sites:** crackrelease.com, uvlist.net
- **Dados:** Listas Denuvo (cracked/uncracked)
- **Problema:** Sem API/JSON público

---

## Ordem de prioridade no menu

1. **games_activation.json** — instruções customizadas
2. **SteamTools com drm:true** — jogos com proteção
3. **SteamTools restante** — demais jogos
4. **SteamAppsListDumps** — complemento (jogos não presentes nas outras fontes)
