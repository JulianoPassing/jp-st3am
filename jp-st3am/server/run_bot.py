# -*- coding: utf-8 -*-
"""Inicia o bot Discord. Rode junto ao app.py na VPS."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.bot import main

if __name__ == "__main__":
    main()
