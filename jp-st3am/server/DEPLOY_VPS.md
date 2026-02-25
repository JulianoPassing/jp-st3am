# Deploy do servidor de licenças na VPS

## Sua VPS
- **Host:** vps59663.publiccloud.com.br
- **IP:** 191.252.100.71
- **Porta:** 5050 (configurável em `config.json`)

---

## 1. O que fazer na VPS

### 1.1 Conectar e ir até a pasta do projeto
```bash
cd /caminho/onde/voce/clonou/jp-st3am
# ou, se já tem o repo:
git pull origin main
```

### 1.2 Entrar na pasta do servidor
```bash
cd server
```

### 1.3 Configurar o servidor
```bash
# Se não existir config.json, copie o exemplo:
cp config.exemplo.json config.json
nano config.json
```

Altere a senha:
```json
{
  "port": 5050,
  "admin_secret": "SUA_SENHA_FORTE_AQUI_123"
}
```
Salve (Ctrl+O, Enter, Ctrl+X).

### 1.4 Instalar dependências
```bash
pip install -r requirements.txt
# ou, se usar Python 3:
pip3 install -r requirements.txt
```

### 1.5 Rodar o servidor

**Opção A – Em primeiro plano (para testar):**
```bash
python app.py
# ou python3 app.py
```
Deve aparecer: `Running on http://0.0.0.0:5050`

**Opção B – Em background (produção):**
```bash
nohup python app.py > server.log 2>&1 &
```

**Opção C – Com PM2 (se tiver instalado):**
```bash
pm2 start app.py --name jp-license --interpreter python3
pm2 save
pm2 startup
```

### 1.6 Liberar a porta no firewall (se houver)
```bash
# UFW (Ubuntu)
sudo ufw allow 5050
sudo ufw reload

# Ou firewall-cmd (CentOS)
sudo firewall-cmd --add-port=5050/tcp --permanent
sudo firewall-cmd --reload
```

---

## 2. O que está na pasta `server/`

```
server/
├── app.py           # API principal
├── config.json      # Porta e senha admin (EDITAR)
├── requirements.txt
├── generate_keys.py # Gera keys via API
├── seed_keys.py     # Gerar keys direto no banco
├── keys.db          # Banco criado automaticamente
└── DEPLOY_VPS.md    # Este arquivo
```

---

## 3. Gerar keys no servidor

```bash
cd server

# Criar keys direto no banco (sem servidor rodando)
python seed_keys.py 20

# OU criar via API (com servidor rodando)
export JP_ADMIN_SECRET="SUA_SENHA"
export JP_LICENSE_URL="http://localhost:5050"
python generate_keys.py 20
```

---

## 4. Configurar o launcher

Crie `config.json` na pasta do EXE ou em `%APPDATA%\JP-Steam-Launcher\`:

```json
{
  "license_server": "http://191.252.100.71:5050"
}
```

Ou use o domínio:
```json
{
  "license_server": "http://vps59663.publiccloud.com.br:5050"
}
```

---

## 5. Testar

```bash
# Health check
curl http://191.252.100.71:5050/health

# Deve retornar: {"status":"ok"}
```

---

## 6. Rodar independente do jp.sistemas

O servidor está em `jp-st3am/server/` e não depende do jp.sistemas. Pode:

- Ficar em qualquer pasta (ex: `/home/user/jp-st3am/server/`)
- Rodar em outro processo
- Usar outro IP/porta

O jp.sistemas continua funcionando normalmente.
