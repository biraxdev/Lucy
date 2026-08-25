#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/../.."

echo "=========================================="
echo "  Lucy C2 — Portable USB Launcher"
echo "=========================================="
echo ""

if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "[ERREUR] Python 3 n'est pas installe."
    echo "Installe Python 3.11+ depuis python.org et relance ce script."
    exit 1
fi

echo "[INFO] Lancement du mode portable (sans Docker)..."
echo ""
python3 tools/portable/launcher.py || python tools/portable/launcher.py
