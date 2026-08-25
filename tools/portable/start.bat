@echo off
chcp 65001 >nul
title Lucy C2 — Portable Launcher
cd /d "%~dp0..\.."

echo ==========================================
echo   Lucy C2 — Portable USB Launcher
echo ==========================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Python non trouve. Le launcher va telecharger Python embarque au premier lancement.
)

echo [INFO] Lancement du mode portable (sans Docker)...
echo.
python tools\portable\launcher.py

if %errorlevel% neq 0 (
    echo.
    echo [ERREUR] Le lancement a echoue. Verifie la connexion internet pour le premier demarrage.
    pause
    exit /b 1
)
