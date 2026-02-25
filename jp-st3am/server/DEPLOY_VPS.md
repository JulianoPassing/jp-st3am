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
geany config.json
```

Altere a senha:
```json
{
  "port": 5050,
  "admin_secret": "SUA_SENHA_FORTE_AQUI_123"
}
```
Salve (Ctrl+S) e feche.

### 1.4 Criar ambiente virtual e instalar dependências

Em VPS com Debian/Ubuntu (PEP 668), use um venv para evitar o erro `externally-managed-environment`:

```bash
# Criar ambiente virtual
python3 -m venv venv

# Ativar o venv (Linux/macOS)
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
```

> **Nota:** Se `python3 -m venv` falhar, instale: `sudo apt install python3-venv python3-full`

### 1.5 Rodar o servidor

**Importante:** Mantenha o venv ativado (`source venv/bin/activate`) antes de rodar.

**Opção A – Em primeiro plano (para testar):**
```bash
python app.py
```
Deve aparecer: `Running on http://0.0.0.0:5050`

**Opção B – Em background (produção):**
```bash
nohup venv/bin/python app.py > server.log 2>&1 &
```
(Usa o Python do venv diretamente, sem precisar ativar.)

**Opção C – Com PM2 (se tiver instalado):**
```bash
pm2 start app.py --name jp-license --interpreter ./venv/bin/python
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
├── downloads/       # JP-Steam-Launcher.exe + PermitirFirewall.bat
├── generate_keys.py # Gera keys via API
├── seed_keys.py     # Gerar keys direto no banco
├── keys.db          # Banco criado automaticamente
└── DEPLOY_VPS.md    # Este arquivo
```

---

## 3. Gerar launcher no Windows e subir para a VPS

O EXE **só pode ser gerado no Windows** (PyInstaller não faz cross-compile para Linux).

### 3.1 No seu PC Windows

```powershell
cd jp-st3am\launcher
.\build.bat
```

O EXE será criado em `launcher\dist\JP-Steam-Launcher.exe`.

### 3.2 Enviar para a VPS (SCP)

No PowerShell ou CMD do Windows (na pasta do projeto):

```powershell
scp launcher\dist\JP-Steam-Launcher.exe juliano@191.252.100.71:~/Desktop/jp-st3am/jp-st3am/server/downloads/
```

Ou use FileZilla/WinSCP: envie o arquivo para `~/Desktop/jp-st3am/jp-st3am/server/downloads/`.

### 3.3 Criar a pasta downloads na VPS (se não existir)

```bash
mkdir -p ~/Desktop/jp-st3am/jp-st3am/server/downloads
```

### 3.4 Link de download

**Recomendado – tudo em um ZIP:**
http://191.252.100.71:5050/download/launcher-completo

Baixa um ZIP com **JP-Steam-Launcher.exe** + **PermitirFirewall.bat** juntos.

**Instruções para o usuário:**
1. Baixar o ZIP e extrair
2. Executar **PermitirFirewall.bat** primeiro (duplo clique e aprovar o UAC)
3. Depois abrir o **JP-Steam-Launcher.exe**

**Links individuais (se precisar):**
- Launcher: http://191.252.100.71:5050/download/launcher
- Permitir Firewall: http://191.252.100.71:5050/download/permitir-firewall

---

## 4. Gerar keys no servidor

```bash
cd server
source venv/bin/activate   # se usar venv

# Criar keys direto no banco (sem servidor rodando)
python seed_keys.py 20

# OU criar via API (com servidor rodando)
export JP_ADMIN_SECRET="SUA_SENHA"
export JP_LICENSE_URL="http://localhost:5050"
python generate_keys.py 20
```

---

## 5. Configurar o launcher

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

## 6. Testar

```bash
# Health check
curl http://191.252.100.71:5050/health

# Deve retornar: {"status":"ok"}
```

---

## 7. Rodar independente do jp.sistemas

O servidor está em `jp-st3am/server/` e não depende do jp.sistemas. Pode:

- Ficar em qualquer pasta (ex: `/home/user/jp-st3am/server/`)
- Rodar em outro processo
- Usar outro IP/porta

O jp.sistemas continua funcionando normalmente.
