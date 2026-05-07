#!/bin/bash
# PDF Signer — Desinstalador

echo "============================================"
echo "  Desinstalador — PDF Signer"
echo "============================================"
echo ""
read -p "Tem certeza que deseja remover o PDF Signer? (s/N): " confirm
if [[ "$confirm" != "s" && "$confirm" != "S" ]]; then
    echo "Cancelado."
    exit 0
fi

APP="/Applications/PDF Signer.app"
CONFIG="$HOME/.pdf_signer_prefs.json"

[ -d "$APP" ]    && rm -rf "$APP"    && echo "✓ App removido."
[ -f "$CONFIG" ] && rm "$CONFIG"     && echo "✓ Configurações removidas."

# Remove do Dock
osascript -e 'tell application "System Events" to delete every login item whose name is "PDF Signer"' 2>/dev/null || true

echo ""
echo "✓ PDF Signer removido com sucesso."
read -p "Pressione Enter para fechar..."
