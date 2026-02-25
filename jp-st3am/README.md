# JP Steam Setup (jp-st3am)

Projeto com três modos de uso:

1. **jp-steam-setup.ps1** – Instala SteamTools + Millennium + LuaTools (plugin na Steam)
2. **jp-steam-launcher.ps1** – Launcher em PowerShell (adiciona jogos por App ID)
3. **launcher/JP-Steam-Launcher.exe** – **Launcher gráfico** com identidade [JP. Sistemas](https://jp-sistemas.com/)

---

## Launcher EXE (interface gráfica JP. Sistemas)

Interface gráfica com cores e identidade visual do [jp-sistemas.com](https://jp-sistemas.com/).

### Gerar o EXE

```batch
cd launcher
build.bat
```

O executável será criado em `launcher/dist/JP-Steam-Launcher.exe`.

### Executar sem compilar

```batch
cd launcher
pip install customtkinter
python launcher.py
```

**Requisitos:** SteamTools instalado, executar como Administrador (o app pede elevação automaticamente).

---

## jp-steam-launcher.ps1 (Launcher PowerShell)

Adiciona jogos à biblioteca Steam usando o App ID, sem precisar do LuaTools como plugin.

### Fluxo

1. Você digita o **App ID** do jogo (ex: 730 = CS2, 271590 = GTA V)
2. O launcher baixa manifest + lua dos repositórios da comunidade
3. Coloca os arquivos em `Steam\config\stplug-in` e `Steam\config\depotcache`
4. Reinicia a Steam
5. O jogo aparece na biblioteca para download

### Como usar

```powershell
# PowerShell como Administrador
.\jp-steam-launcher.ps1
```

**Requisitos:** SteamTools já instalado (`irm steam.run | iex` ou use o jp-steam-setup.ps1 primeiro)

**Onde achar o App ID:** [steamdb.info](https://steamdb.info) ou na URL da loja (`store.steampowered.com/app/XXXXX`)

---

## jp-steam-setup.ps1 (Instalador completo)

Instalador personalizado para plugins Steam, baseado no [LuaToolsSetup](https://github.com/ookami42/ookami42.github.io).  
Instala **SteamTools**, **Millennium** e o plugin configurado em um único comando.

### O que faz

1. Verifica se está rodando como **Administrador**
2. Detecta o caminho da Steam no seu PC
3. Adiciona exclusão no Windows Defender para evitar bloqueios
4. Fecha a Steam (se estiver aberta)
5. Instala **SteamTools** (se não estiver instalado)
6. Instala **Millennium** (se não estiver instalado)
7. Baixa e instala o plugin configurado (ex: LuaTools)
8. Ativa o plugin no `config.json`
9. Inicia a Steam

### Como usar

1. Abra o **PowerShell como Administrador**  
   (Clique com botão direito → "Executar como administrador")

2. Execute o script:

```powershell
# Se estiver na pasta do projeto:
.\jp-steam-setup.ps1

# Ou execute direto da web (quando publicar):
# irm "https://seu-site.github.io/jp-steam-setup.ps1" | iex
```

### Personalização

Edite o bloco **SUA CONFIGURAÇÃO** no início do script:

| Variável      | Descrição                          | Exemplo |
|---------------|------------------------------------|---------|
| `NomeProjeto` | Nome do seu projeto                | `"jp-st3am"` |
| `NomePlugin`  | Nome da pasta do plugin            | `"luatools"` |
| `TituloJanela`| Título da janela do PowerShell     | `"JP Steam Setup"` |
| `Versao`      | Versão do instalador               | `"1.0.0"` |
| `LinkPlugin`  | URL do ZIP do plugin               | GitHub releases |
| `TimerMillenium` | Segundos antes de instalar Millennium | `5` |
| `Discord`     | Link da sua comunidade (opcional)  | `".gg/luatools"` |

### Usar seu próprio plugin

1. Crie releases no GitHub com um arquivo `.zip` do seu plugin
2. Altere `LinkPlugin` para a URL do release
3. Altere `NomePlugin` para o nome da pasta que o ZIP extrai

---

## Estrutura baseada em

- [LuaToolsSetup](https://github.com/ookami42/ookami42.github.io) (Ookami)
- [luatoolsinstaller](https://github.com/YuKi-dev1/luatoolsinstaller) (YUKI)
- Script original: CLEM
- [Millennium](https://github.com/SteamClientHomebrew/Millennium) - framework de plugins Steam
- [LuaMani](https://github.com/GOAT42069/LuaMani) / [ManifestHub](https://github.com/SteamAutoCracks/ManifestHub) - fontes de manifest + lua para o launcher

---

## Requisitos

- Windows 10/11
- Steam instalada
- PowerShell (já vem no Windows)

---

**jp-st3am** – seu instalador, suas regras.
