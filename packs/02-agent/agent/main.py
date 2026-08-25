"""
Entry point for PyInstaller standalone agent binary.
Imports configuration baked in at build time and starts the agent.
"""
from agent import main

if __name__ == "__main__":
    main()
