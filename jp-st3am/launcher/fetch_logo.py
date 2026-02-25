# -*- coding: utf-8 -*-
# Baixa o logo do site jp-sistemas.com (Imgur)
import urllib.request
import os

# URLs do logo JP Sistemas (extraídas do site jp-sistemas.com)
URLS = [
    ("https://i.imgur.com/6N82fk2.png", "logo_site.png"),   # Logo principal (swoosh azul)
    ("https://i.imgur.com/TwZLW6a.png", "logo_site_2.png"), # Alternativo
]

os.chdir(os.path.dirname(os.path.abspath(__file__)))
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

for url, fname in URLS:
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
        with open(fname, "wb") as f:
            f.write(data)
        print(f"Baixado: {fname}")
    except Exception as e:
        print(f"Erro {fname}: {e}")
