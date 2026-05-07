#!/bin/bash
# Instala dependências se necessário e abre o app

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if ! /opt/homebrew/bin/python3.11 -c "import pyhanko" 2>/dev/null; then
    echo "Instalando pyhanko..."
    /opt/homebrew/bin/pip3.11 install pyhanko
fi

/opt/homebrew/bin/python3.11 "$SCRIPT_DIR/app.py"
