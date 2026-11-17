"""SQLite storage for SpamShield: users, labeled SMS dataset, prediction history.

On first run it creates the tables, seeds one admin + one demo user, and
imports the labeled messages from data.csv (only when the dataset is empty).
"""

import csv
import os
import sqlite3

from . import auth

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "spamshield.db")
DATA_CSV = os.path.join(BASE_DIR, "data.csv")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL CHECK (label IN ('ham', 'spam')),
            text TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'seed',
            added_by INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT NOT NULL,
            label TEXT NOT NULL,
            spam_probability REAL NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    conn.commit()

    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            ("Admin", "admin@spamshield.edu.pk", auth.hash_password("admin123"), "admin"),
        )
        conn.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            ("Demo User", "demo@spamshield.edu.pk", auth.hash_password("demo123"), "user"),
        )
        conn.commit()

    if conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0:
        rows = []
        if os.path.exists(DATA_CSV):
            with open(DATA_CSV, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    label = (row.get("label") or "").strip().lower()
                    text = (row.get("message") or "").strip()
                    if label in ("ham", "spam") and text:
                        rows.append((label, text, "seed"))
        conn.executemany(
            "INSERT INTO messages (label, text, source) VALUES (?, ?, ?)", rows
        )
        conn.commit()
    conn.close()


# ---------------- users ----------------

def get_user_by_email(email):
    conn = _connect()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id):
    conn = _connect()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_user(name, email, password_hash, role="user"):
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
        (name, email, password_hash, role),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id


def public_user(user):
    return {"id": user["id"], "name": user["name"], "email": user["email"],
            "role": user["role"]}


# ---------------- dataset ----------------

def list_messages(label=None, search=None, limit=200, offset=0):
    query = "SELECT * FROM messages"
    clauses, params = [], []
    if label in ("ham", "spam"):
        clauses.append("label = ?")
        params.append(label)
    if search:
        clauses.append("text LIKE ?")
        params.append(f"%{search}%")
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY id LIMIT ? OFFSET ?"
    params += [limit, offset]
    conn = _connect()
    rows = [dict(r) for r in conn.execute(query, params)]
    total = conn.execute(
        "SELECT COUNT(*) FROM messages" + (" WHERE " + " AND ".join(clauses) if clauses else ""),
        params[:-2],
    ).fetchone()[0]
    conn.close()
    return rows, total


def dataset_counts():
    conn = _connect()
    total = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    spam = conn.execute("SELECT COUNT(*) FROM messages WHERE label='spam'").fetchone()[0]
    ham = conn.execute("SELECT COUNT(*) FROM messages WHERE label='ham'").fetchone()[0]
    conn.close()
    return {"total": total, "spam": spam, "ham": ham}


def all_labeled():
    conn = _connect()
    rows = conn.execute("SELECT text, label FROM messages ORDER BY id").fetchall()
    conn.close()
    return [r["text"] for r in rows], [r["label"] for r in rows]


def add_message(label, text, source="user", added_by=None):
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO messages (label, text, source, added_by) VALUES (?, ?, ?, ?)",
        (label, text, source, added_by),
    )
    conn.commit()
    msg_id = cur.lastrowid
    conn.close()
    return msg_id


def delete_message(msg_id):
    conn = _connect()
    cur = conn.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()
    return cur.rowcount


# ---------------- predictions ----------------

def add_prediction(user_id, text, label, spam_probability):
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO predictions (user_id, text, label, spam_probability)"
        " VALUES (?, ?, ?, ?)",
        (user_id, text, label, spam_probability),
    )
    conn.commit()
    pred_id = cur.lastrowid
    conn.close()
    return pred_id


def user_history(user_id, limit=100):
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM predictions WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def prediction_stats(user_id=None):
    conn = _connect()
    where = "WHERE user_id = ?" if user_id is not None else ""
    params = (user_id,) if user_id is not None else ()
    total = conn.execute(
        f"SELECT COUNT(*) FROM predictions {where}", params
    ).fetchone()[0]
    spam = conn.execute(
        f"SELECT COUNT(*) FROM predictions {where} {'AND' if where else 'WHERE'} label='spam'",
        params,
    ).fetchone()[0]
    conn.close()
    return {"total": total, "spam": spam, "ham": total - spam}
