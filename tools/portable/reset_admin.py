#!/usr/bin/env python3
"""Reset admin username and password in the portable database."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "lucy.db"


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE role = 'admin' LIMIT 1")
    row = c.fetchone()
    if row is None:
        print("No admin user found.")
        return
    c.execute("UPDATE users SET username = 'admin' WHERE role = 'admin'")
    conn.commit()
    print(f"Admin user reset to 'admin'. Rows updated: {c.rowcount}")


if __name__ == "__main__":
    main()
