#!/bin/bash
cd "$(dirname "$0")"

# Sprawdź czy jesteśmy w venv, jeśli nie, to uruchom przez venv
if [ -x ".venv/bin/python" ]; then
    ./.venv/bin/python main.py
elif [ -x "venv/bin/python" ]; then
    ./venv/bin/python main.py
else
    python3 main.py
fi
