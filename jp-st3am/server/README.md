# JP Steam Launcher - Servidor de Licenças

API para validar keys do launcher. **1 key = 1 PC** (vinculada ao Hardware ID).

## Deploy na VPS

### 1. Copiar pasta `server` para a VPS

### 2. Instalar dependências
```bash
cd server
pip install -r requirements.txt
```

### 3. Configurar variáveis
```bash
# Linux
export JP_ADMIN_SECRET="sua-senha-secreta-forte"
export PORT=5000
```

### 4. Rodar
```bash
python app.py
```

Ou com gunicorn (produção):
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Gerar keys

**Opção A – Com servidor rodando (API):**
```bash
export JP_ADMIN_SECRET="sua-senha"
export JP_LICENSE_URL="http://sua-vps:5000"
python generate_keys.py 10
```

**Opção B – Sem servidor (direto no banco):**
```bash
python seed_keys.py 10
```

Ou via curl:
```bash
curl -X POST "http://seu-servidor:5000/api/admin/generate" \
  -H "Authorization: Bearer sua-senha-secreta" \
  -H "Content-Type: application/json" \
  -d '{"quantity": 10}'
```

## Configurar o launcher

**Opção 1:** Edite `launcher.py` antes de buildar – altere o retorno padrão em `_get_license_url()` para sua URL.

**Opção 2:** Crie `config.json` na pasta do EXE ou em `%APPDATA%\JP-Steam-Launcher\`:
```json
{"license_server": "https://sua-vps.com:5000"}
```

**Opção 3:** Variável de ambiente: `JP_LICENSE_URL=https://sua-vps.com:5000`
