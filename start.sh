#!/usr/bin/env bash
# start.sh — ikas AI SEO Agent başlatıcı
#
# Kullanım:
#   ./start.sh          → Production: frontend build et + backend başlat (http://localhost:8000)
#   ./start.sh dev      → Dev: backend (8000) + Vite dev server (5173) paralel başlat
#   ./start.sh build    → Sadece frontend build et, başlatma
#   ./start.sh backend  → Sadece backend başlat (önceden build edilmiş frontend gerekir)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$ROOT/web"
DIST_DIR="$WEB_DIR/dist"

# ── Renkler ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[ikas-seo]${NC} $*"; }
info() { echo -e "${BLUE}[ikas-seo]${NC} $*"; }
warn() { echo -e "${YELLOW}[ikas-seo]${NC} $*"; }

# ── Bağımlılık kontrolleri ───────────────────────────────────────────────────
check_python() {
    if ! command -v python &>/dev/null && ! command -v python3 &>/dev/null; then
        echo "HATA: Python bulunamadı." >&2; exit 1
    fi
    PYTHON=$(command -v python3 || command -v python)
}

check_node() {
    if ! command -v npm &>/dev/null; then
        echo "HATA: npm bulunamadı. Node.js yükleyin." >&2; exit 1
    fi
}

check_python_deps() {
    if ! "$PYTHON" -c "import fastapi, uvicorn" 2>/dev/null; then
        warn "Python bağımlılıkları eksik, yükleniyor..."
        "$PYTHON" -m pip install -r "$ROOT/requirements.txt" -q
    fi
}

check_node_deps() {
    if [ ! -d "$WEB_DIR/node_modules" ]; then
        warn "npm bağımlılıkları eksik, yükleniyor..."
        npm install --prefix "$WEB_DIR" --silent
    fi
}

# ── Frontend build ───────────────────────────────────────────────────────────
build_frontend() {
    log "Frontend build ediliyor..."
    check_node
    check_node_deps
    npm run build --prefix "$WEB_DIR" --silent
    log "Frontend hazır → $DIST_DIR"
}

# ── Production modu ──────────────────────────────────────────────────────────
start_production() {
    check_python
    check_python_deps

    if [ ! -d "$DIST_DIR" ]; then
        build_frontend
    else
        info "Mevcut frontend build kullanılıyor ($DIST_DIR)"
        info "Güncel build için: ./start.sh build && ./start.sh backend"
    fi

    log "Backend başlatılıyor → http://localhost:8000"
    echo ""
    echo -e "  ${GREEN}▶${NC}  Arayüz : http://localhost:8000"
    echo -e "  ${GREEN}▶${NC}  API    : http://localhost:8000/api"
    echo -e "  ${GREEN}▶${NC}  Docs   : http://localhost:8000/docs"
    echo ""
    cd "$ROOT"
    exec "$PYTHON" -m uvicorn api.main:app --host 0.0.0.0 --port 8000
}

# ── Development modu ─────────────────────────────────────────────────────────
start_dev() {
    check_python
    check_python_deps
    check_node
    check_node_deps

    log "Development modu başlatılıyor..."
    echo ""
    echo -e "  ${GREEN}▶${NC}  Backend  : http://localhost:8000  (hot-reload)"
    echo -e "  ${GREEN}▶${NC}  Frontend : http://localhost:5173  (Vite HMR)"
    echo -e "  ${GREEN}▶${NC}  API Docs : http://localhost:8000/docs"
    echo ""
    echo "  Durdurmak için: Ctrl+C"
    echo ""

    # Temizlik fonksiyonu
    cleanup() {
        log "Durduruluyor..."
        kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
        wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
        log "Tüm processler durduruldu."
    }
    trap cleanup SIGINT SIGTERM

    # Backend
    cd "$ROOT"
    "$PYTHON" -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload \
        --reload-dir "$ROOT/api" --reload-dir "$ROOT/core" --reload-dir "$ROOT/config" \
        2>&1 | sed 's/^/[backend] /' &
    BACKEND_PID=$!

    # Frontend dev server
    npm run dev --prefix "$WEB_DIR" 2>&1 | sed 's/^/[frontend] /' &
    FRONTEND_PID=$!

    # Herhangi biri çıkarsa diğerini de durdur
    wait "$BACKEND_PID" "$FRONTEND_PID"
}

# ── Sadece build ─────────────────────────────────────────────────────────────
build_only() {
    build_frontend
    log "Build tamamlandı. Başlatmak için: ./start.sh backend"
}

# ── Sadece backend ───────────────────────────────────────────────────────────
start_backend() {
    check_python
    check_python_deps
    log "Backend başlatılıyor → http://localhost:8000"
    cd "$ROOT"
    exec "$PYTHON" -m uvicorn api.main:app --host 0.0.0.0 --port 8000
}

# ── Ana akış ─────────────────────────────────────────────────────────────────
MODE="${1:-prod}"

case "$MODE" in
    dev|development)  start_dev ;;
    build)            build_only ;;
    backend)          start_backend ;;
    prod|production|"") start_production ;;
    *)
        echo "Kullanım: ./start.sh [prod|dev|build|backend]"
        exit 1
        ;;
esac
