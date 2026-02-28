#!/bin/bash
# Inicia API + Bot na VPS. Use: ./run_all.sh
# Ou rode separado: python app.py & python run_bot.py

cd "$(dirname "$0")"
source venv/bin/activate 2>/dev/null || true

# API em background
nohup python app.py > server.log 2>&1 &
API_PID=$!
echo "API iniciada (PID $API_PID)"

sleep 2

# Bot em foreground (ou use nohup para background)
python run_bot.py
# Para rodar bot em background: nohup python run_bot.py > bot.log 2>&1 &
