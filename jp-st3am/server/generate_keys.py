# -*- coding: utf-8 -*-
"""Gera keys para o JP Steam Launcher. Uso: python generate_keys.py [quantidade]"""

import os
import sys
import requests

ADMIN_SECRET = os.environ.get("JP_ADMIN_SECRET", "altere-isso-em-producao")
SERVER_URL = os.environ.get("JP_LICENSE_URL", "http://localhost:5000")


def main():
    qty = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    url = f"{SERVER_URL.rstrip('/')}/api/admin/generate"
    try:
        r = requests.post(url, json={"quantity": qty}, headers={"Authorization": f"Bearer {ADMIN_SECRET}"}, timeout=10)
        r.raise_for_status()
        data = r.json()
        keys = data.get("keys", [])
        print(f"\n=== {len(keys)} keys geradas ===\n")
        for k in keys:
            print(k)
        print()
    except requests.exceptions.ConnectionError:
        print("Erro: Não foi possível conectar ao servidor. Certifique-se de que está rodando.")
        print(f"  URL: {SERVER_URL}")
        sys.exit(1)
    except Exception as e:
        print(f"Erro: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
