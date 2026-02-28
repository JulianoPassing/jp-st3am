# Comandos para rodar na VPS

Guia passo a passo para subir a API e o bot na VPS.

---

## 1. Conectar na VPS

```bash
ssh seu_usuario@191.252.100.71
```

(Substitua `seu_usuario` pelo seu usuário SSH.)

---

## 2. Ir até a pasta do projeto

```bash
cd ~/jp-st3am/jp-st3am/server
```

Se ainda não tiver o projeto:

```bash
cd ~
git clone https://github.com/SEU_USUARIO/jp-st3am.git
cd jp-st3am/jp-st3am/server
```

---

## 3. Configurar o config.json

```bash
cp config.exemplo.json config.json
nano config.json
```

Preencha com seus dados:

```json
{
  "port": 5050,
  "admin_secret": "SUA_SENHA_FORTE",
  "license_server": "http://191.252.100.71:5050",
  "discord_bot_token": "TOKEN_DO_SEU_BOT",
  "ticket_category_id": 1477393102246379600
}
```

Salve: `Ctrl+O`, Enter, `Ctrl+X`.

---

## 4. Criar ambiente virtual e instalar dependências

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Se der erro em `venv`:

```bash
sudo apt update
sudo apt install python3-venv python3-full -y
```

---

## 5. Rodar a API (servidor Flask)

**Teste (terminal aberto):**

```bash
source venv/bin/activate
python app.py
```

Deve aparecer: `Running on http://0.0.0.0:5050`. Pare com `Ctrl+C`.

**Produção (em background):**

```bash
nohup venv/bin/python app.py > server.log 2>&1 &
```

Verificar se está rodando:

```bash
curl http://localhost:5050/health
```

Resposta esperada: `{"status":"ok"}`

---

## 6. Rodar o Bot Discord

**Teste (terminal aberto):**

```bash
source venv/bin/activate
python run_bot.py
```

Deve aparecer: `Bot conectado como ...`. Pare com `Ctrl+C`.

**Produção (em background):**

```bash
nohup venv/bin/python run_bot.py > bot.log 2>&1 &
```

---

## 7. Rodar tudo de uma vez (API + Bot)

```bash
cd ~/jp-st3am/jp-st3am/server
source venv/bin/activate

# API em background
nohup venv/bin/python app.py > server.log 2>&1 &
echo "API iniciada"

# Aguardar 2 segundos
sleep 2

# Bot em background
nohup venv/bin/python run_bot.py > bot.log 2>&1 &
echo "Bot iniciado"
```

---

## 8. Verificar se está rodando

```bash
# Processos Python
ps aux | grep python

# Logs da API
tail -f server.log

# Logs do Bot
tail -f bot.log
```

---

## 9. Parar os processos

```bash
# Encontrar PIDs
ps aux | grep "app.py"
ps aux | grep "run_bot.py"

# Matar (substitua PID pelo número)
kill PID
```

Ou matar todos:

```bash
pkill -f "python app.py"
pkill -f "python run_bot.py"
```

---

## 10. Atualizar o projeto (git pull)

```bash
cd ~/jp-st3am
git pull origin main
cd jp-st3am/server
pip install -r requirements.txt
# Reinicie API e Bot (pare e rode de novo)
```

---

## Resumo rápido

| Ação | Comando |
|------|---------|
| Subir API | `nohup venv/bin/python app.py > server.log 2>&1 &` |
| Subir Bot | `nohup venv/bin/python run_bot.py > bot.log 2>&1 &` |
| Ver log API | `tail -f server.log` |
| Ver log Bot | `tail -f bot.log` |
| Testar API | `curl http://localhost:5050/health` |
