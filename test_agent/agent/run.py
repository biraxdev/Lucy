#!/usr/bin/env python3
"""Lucy agent quick-mode launcher.
No PyInstaller needed — just pip install -r requirements.txt && python run.py
"""
import os
import sys

# Ensure the agent directory is on the path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import psutil
    import websocket
    from cryptography.hazmat.primitives import serialization
except ImportError:
    print("Missing dependencies. Run: pip install -r requirements.txt")
    sys.exit(1)

from main import main

if __name__ == "__main__":
    main()
