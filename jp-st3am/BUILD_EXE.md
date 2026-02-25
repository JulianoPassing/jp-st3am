# Como gerar o EXE

## Opção 1: GitHub Actions (recomendado)

O EXE é gerado automaticamente no GitHub. **Link de download permanente.**

### Passo a passo

1. Faça push do código para o repositório.
2. Crie uma **tag** (ex: `v1.0`):
   - No GitHub: Releases → Create a new release → escolha tag `v1.0`
   - Ou no terminal: `git tag v1.0` e `git push origin v1.0`
3. O workflow roda e cria um **Release** com o EXE para download.
4. Link: `https://github.com/SEU-USUARIO/jp-st3am/releases`

### Build manual (sem tag)

1. No GitHub: **Actions** → **Build JP Steam Launcher** → **Run workflow**
2. Ao terminar, baixe o EXE em **Artifacts**.

---

## Opção 2: No seu PC (build.bat)

```bash
cd launcher
build.bat
```

O EXE será gerado em `launcher/dist/JP-Steam-Launcher.exe`.
