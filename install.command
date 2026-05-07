#!/bin/bash
# PDF Signer — Instalador
# Duplo clique para instalar.

set -e
cd "$(dirname "$0")"
INSTALL_SRC="$(pwd)"

echo "============================================"
echo "  Instalador — PDF Signer"
echo "============================================"
echo ""

# ── 1. Homebrew ──────────────────────────────────
if ! command -v brew &>/dev/null; then
    echo "▸ Instalando Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add brew to PATH for Apple Silicon
    eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true
    eval "$(/usr/local/bin/brew shellenv)" 2>/dev/null || true
else
    echo "✓ Homebrew já instalado."
fi

# Detect brew prefix
BREW_PREFIX="$(brew --prefix)"

# ── 2. Python 3.11 ───────────────────────────────
if ! "$BREW_PREFIX/bin/python3.11" --version &>/dev/null; then
    echo "▸ Instalando Python 3.11..."
    brew install python@3.11
else
    echo "✓ Python 3.11 já instalado."
fi

PYTHON="$BREW_PREFIX/bin/python3.11"
PIP="$BREW_PREFIX/bin/pip3.11"

# ── 3. Tkinter ───────────────────────────────────
if ! "$PYTHON" -c "import tkinter" &>/dev/null; then
    echo "▸ Instalando python-tk@3.11..."
    brew install python-tk@3.11
else
    echo "✓ Tkinter já instalado."
fi

# ── 4. Dependências Python ───────────────────────
echo "▸ Instalando dependências Python..."
"$PIP" install --quiet pyhanko pymupdf pillow reportlab

echo "✓ Dependências instaladas."

# ── 5. Criar PDF Signer.app ──────────────────────
APP_NAME="PDF Signer"
APP_DEST="/Applications/${APP_NAME}.app"

echo ""
echo "▸ Criando ${APP_NAME}.app em /Applications..."

# Limpa versão anterior
rm -rf "$APP_DEST"

# Estrutura do .app
mkdir -p "$APP_DEST/Contents/MacOS"
mkdir -p "$APP_DEST/Contents/Resources"

# Copia app.py para dentro do bundle
cp "$INSTALL_SRC/app.py" "$APP_DEST/Contents/Resources/app.py"

# Script de lançamento
cat > "$APP_DEST/Contents/MacOS/PDF Signer" <<LAUNCHER
#!/bin/bash
PYTHON="$PYTHON"
APP_PY="\$(dirname "\$0")/../Resources/app.py"
"\$PYTHON" "\$APP_PY"
LAUNCHER
chmod +x "$APP_DEST/Contents/MacOS/PDF Signer"

# Info.plist
cat > "$APP_DEST/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>PDF Signer</string>
    <key>CFBundleIdentifier</key>
    <string>com.pdfsigner.app</string>
    <key>CFBundleName</key>
    <string>PDF Signer</string>
    <key>CFBundleDisplayName</key>
    <string>PDF Signer</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSRequiresAquaSystemAppearance</key>
    <false/>
</dict>
</plist>
PLIST

# ── 6. Atalho no Dock (opcional) ─────────────────
echo "▸ Adicionando ao Dock..."
defaults write com.apple.dock persistent-apps -array-add \
    "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>${APP_DEST}</string><key>_CFURLStringType</key><integer>0</integer></dict></dict></dict>" \
    2>/dev/null && killall Dock 2>/dev/null || true

echo ""
echo "============================================"
echo "  ✓ Instalação concluída!"
echo ""
echo "  Abra pelo Launchpad ou Finder → Aplicativos"
echo "  Nome: PDF Signer"
echo "============================================"
echo ""
read -p "Pressione Enter para fechar..."
