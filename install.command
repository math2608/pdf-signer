#!/bin/bash
# PDF Signer — Instalador Completo
# Duplo clique para instalar.

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Cores ─────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $1"; }
info() { echo -e "${YELLOW}▸${NC} $1"; }
err()  { echo -e "${RED}✗ Erro:${NC} $1"; exit 1; }
sep()  { echo -e "\n${BOLD}── $1 ──────────────────────────────${NC}"; }

clear
echo ""
echo -e "${BOLD}============================================${NC}"
echo -e "${BOLD}        Instalador — PDF Signer             ${NC}"
echo -e "${BOLD}============================================${NC}"
echo ""
echo "Este instalador irá configurar tudo automaticamente."
echo "Pode ser necessário digitar sua senha de administrador."
echo ""
read -p "Pressione Enter para continuar (Ctrl+C para cancelar)..."
echo ""

# ── 1. Xcode Command Line Tools ───────────────────
sep "Passo 1: Ferramentas do Sistema"
if xcode-select -p &>/dev/null; then
    ok "Xcode Command Line Tools já instalado."
else
    info "Instalando Xcode Command Line Tools..."
    echo "    → Uma janela vai abrir pedindo para instalar. Clique em 'Instalar'."
    echo "    → Aguarde a instalação terminar e pressione Enter aqui."
    xcode-select --install 2>/dev/null || true
    read -p "    Pressione Enter após a instalação do Xcode CLT terminar..."
    xcode-select -p &>/dev/null || err "Xcode CLT não foi instalado. Tente novamente."
    ok "Xcode Command Line Tools instalado."
fi

# ── 2. Homebrew ───────────────────────────────────
sep "Passo 2: Homebrew (gerenciador de pacotes)"

# Detecta arquitetura (Apple Silicon vs Intel)
if [[ "$(uname -m)" == "arm64" ]]; then
    BREW_PATH="/opt/homebrew/bin/brew"
else
    BREW_PATH="/usr/local/bin/brew"
fi

if command -v brew &>/dev/null || [ -f "$BREW_PATH" ]; then
    ok "Homebrew já instalado."
    eval "$("$BREW_PATH" shellenv)" 2>/dev/null || true
else
    info "Instalando Homebrew (requer senha de administrador)..."
    /bin/bash -c \
        "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$("$BREW_PATH" shellenv)"
    ok "Homebrew instalado."
fi

BREW="$(command -v brew)"
BREW_PREFIX="$("$BREW" --prefix)"
export PATH="$BREW_PREFIX/bin:$PATH"

# ── 3. Python 3.11 ───────────────────────────────
sep "Passo 3: Python 3.11"
PYTHON="$BREW_PREFIX/bin/python3.11"

if "$PYTHON" --version &>/dev/null; then
    ok "Python 3.11 já instalado. ($("$PYTHON" --version))"
else
    info "Instalando Python 3.11..."
    "$BREW" install python@3.11
    ok "Python 3.11 instalado."
fi

# ── 4. Tkinter ────────────────────────────────────
sep "Passo 4: Interface gráfica (Tkinter)"
if "$PYTHON" -c "import tkinter" &>/dev/null; then
    ok "Tkinter já instalado."
else
    info "Instalando python-tk@3.11..."
    "$BREW" install python-tk@3.11
    ok "Tkinter instalado."
fi

# ── 5. Dependências Python ────────────────────────
sep "Passo 5: Bibliotecas Python"
PIP="$BREW_PREFIX/bin/pip3.11"

PACKAGES=("pyhanko" "pymupdf" "pillow" "reportlab")
for pkg in "${PACKAGES[@]}"; do
    if "$PYTHON" -c "import ${pkg//-/_}" &>/dev/null 2>&1 || \
       "$PYTHON" -c "import ${pkg}" &>/dev/null 2>&1; then
        ok "$pkg já instalado."
    else
        info "Instalando $pkg..."
        "$PIP" install --quiet "$pkg"
        ok "$pkg instalado."
    fi
done

# ── 6. Criar PDF Signer.app ───────────────────────
sep "Passo 6: Criando o aplicativo"

APP_DEST="/Applications/PDF Signer.app"
rm -rf "$APP_DEST"
mkdir -p "$APP_DEST/Contents/MacOS"
mkdir -p "$APP_DEST/Contents/Resources"

cp "$SCRIPT_DIR/app.py" "$APP_DEST/Contents/Resources/app.py"

# Script de lançamento (embute o caminho do Python no momento da instalação)
cat > "$APP_DEST/Contents/MacOS/PDF Signer" <<LAUNCHER
#!/bin/bash
"${PYTHON}" "\$(dirname "\$0")/../Resources/app.py"
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

ok "PDF Signer.app criado em /Applications."

# ── 7. Adicionar ao Dock ──────────────────────────
info "Adicionando ao Dock..."
defaults write com.apple.dock persistent-apps -array-add \
    "<dict><key>tile-data</key><dict><key>file-data</key><dict>\
<key>_CFURLString</key><string>${APP_DEST}</string>\
<key>_CFURLStringType</key><integer>0</integer>\
</dict></dict></dict>" 2>/dev/null && killall Dock 2>/dev/null || true
ok "Atalho adicionado ao Dock."

# ── Concluído ─────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}============================================${NC}"
echo -e "${BOLD}${GREEN}   ✓  Instalação concluída com sucesso!     ${NC}"
echo -e "${BOLD}${GREEN}============================================${NC}"
echo ""
echo "  → Abra pelo Dock, Launchpad ou Finder → Aplicativos"
echo "  → Nome do app: PDF Signer"
echo ""

# Abre o app imediatamente
read -p "Deseja abrir o PDF Signer agora? (S/n): " open_now
if [[ "$open_now" != "n" && "$open_now" != "N" ]]; then
    open "$APP_DEST"
fi

echo ""
read -p "Pressione Enter para fechar..."
