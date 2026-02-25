# -*- coding: utf-8 -*-
"""Cria keys diretamente no banco (útil para setup inicial). Uso: python seed_keys.py [quantidade]"""

import os
import sys
import uuid
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "keys.db")


def main():
    qty = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            key TEXT PRIMARY KEY,
            hardware_id TEXT,
            activated_at TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    keys = []
    for _ in range(qty):
        raw = uuid.uuid4().hex[:12].upper()
        key = f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}"
        try:
            conn.execute(
                "INSERT INTO keys (key, created_at) VALUES (?, ?)",
                (key, datetime.utcnow().isoformat())
            )
            keys.append(key)
        except sqlite3.IntegrityError:
            continue
    conn.commit()
    conn.close()
    print(f"\n=== {len(keys)} keys criadas ===\n")
    for k in keys:
        print(k)
    print()


if __name__ == "__main__":
    main()
