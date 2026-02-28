# Bot Discord JP Steam Launcher

Sistema **automático** de ativação via tickets. Usuário abre ticket, envia ID do jogo, bot responde com key + passo a passo.

## Fluxo automático

1. Usuário usa `/ativar` → clica em **Abrir ticket de ativação**
2. Bot cria uma thread (ticket)
3. Usuário envia o **ID do jogo** (ex: `1349630`) ou **nome** (ex: `Need for Speed`)
4. Bot responde automaticamente com:
   - Key do launcher (gerada na hora)
   - Passo a passo do jogo
   - Links de download

## Configuração

1. Crie um bot em https://discord.com/developers/applications
2. Em **Bot** > **Privileged Gateway Intents**: ative **Server Members Intent** (para adicionar admins aos tickets)
3. Em `config.json`:
   ```json
   {
     "discord_bot_token": "SEU_TOKEN",
     "port": 5050,
     "admin_secret": "SUA_SENHA"
   }
   ```
3. Convide o bot (OAuth2 > URL Generator > bot scope)
4. IDs: Servidor `1477391471752773754`, Bot `1477391841488801953`, Categoria de tickets `1477393102246379600`
5. Na categoria de tickets, crie um canal de texto (ex: `criar-ticket`) e ative **Threads privadas** nas configurações do canal

## Comandos

| Comando | Descrição |
|---------|-----------|
| `/ativar` | Abre ticket de ativação (botão) |
| `/pegar-key` | Link para ativação automática |
| `/gerar-key [qty]` | [Admin] Gera keys em lote |
| `/buscar-jogo [nome]` | Busca jogos (52k+ da SteamTools) |
| `/jogos-ativacao` | Lista jogos com ativação configurada |
| `/status` | Status da API |

## Adicionar jogos

Edite `data/games_activation.json`:

```json
{
  "appid": "1349630",
  "name": "Need for Speed Unbound",
  "type": "denuvo_ticket",
  "gera_key": true,
  "steps": ["1. Passo um", "2. Passo dois"],
  "links": {
    "jogo": "https://...",
    "secret_sauce": "https://..."
  }
}
```

Jogos não listados usam o `default` (key + instalar via launcher).

## Rodar na VPS

```bash
cd server
source venv/bin/activate
pip install -r requirements.txt
python app.py &
python run_bot.py
```
