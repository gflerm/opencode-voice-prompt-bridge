"""SQLite persistence for glossary terms, learned corrections and sessions."""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS corrections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  replacement TEXT NOT NULL,
  count INTEGER NOT NULL DEFAULT 1,
  enabled INTEGER NOT NULL DEFAULT 1,
  context TEXT NOT NULL DEFAULT '',
  last_used TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_corrections_pair ON corrections(source, replacement);

CREATE TABLE IF NOT EXISTS terms (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical TEXT NOT NULL UNIQUE,
  aliases TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT '',
  priority INTEGER NOT NULL DEFAULT 100
);

CREATE TABLE IF NOT EXISTS contexts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  keywords TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  latency_ms INTEGER,
  model TEXT,
  accepted INTEGER
);
"""


@dataclass(frozen=True)
class Correction:
    id: int
    source: str
    replacement: str
    count: int
    enabled: bool
    context: str
    last_used: str


@dataclass(frozen=True)
class Term:
    id: int
    canonical: str
    aliases: str
    category: str
    priority: int


@dataclass(frozen=True)
class Context:
    id: int
    name: str
    keywords: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AdaptationStore:
    """Thread-safe wrapper around the local adaptation database."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _execute(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
            self._conn.commit()
            return rows

    def _correction(self, row: sqlite3.Row) -> Correction:
        return Correction(
            id=row["id"], source=row["source"], replacement=row["replacement"],
            count=row["count"], enabled=bool(row["enabled"]),
            context=row["context"], last_used=row["last_used"],
        )

    def upsert_correction(self, source: str, replacement: str, context: str = "") -> Correction:
        """Create a correction or increment count if the pair already exists."""
        rows = self._execute(
            """
            INSERT INTO corrections(source, replacement, count, enabled, context, last_used)
            VALUES(?, ?, 1, 1, ?, ?)
            ON CONFLICT(source, replacement) DO UPDATE SET
              count = count + 1,
              last_used = excluded.last_used
            RETURNING *
            """,
            (source, replacement, context, _now()),
        )
        return self._correction(rows[0])

    def list_corrections(self, enabled_only: bool = False) -> list[Correction]:
        sql = "SELECT * FROM corrections"
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY count DESC, source COLLATE NOCASE"
        return [self._correction(r) for r in self._execute(sql)]

    def update_correction(self, correction_id: int, source: str, replacement: str, context: str = "") -> None:
        self._execute(
            "UPDATE corrections SET source=?, replacement=?, context=? WHERE id=?",
            (source, replacement, context, correction_id),
        )

    def set_correction_enabled(self, correction_id: int, enabled: bool) -> None:
        self._execute(
            "UPDATE corrections SET enabled=? WHERE id=?",
            (1 if enabled else 0, correction_id),
        )

    def delete_correction(self, correction_id: int) -> None:
        self._execute("DELETE FROM corrections WHERE id=?", (correction_id,))

    def _term(self, row: sqlite3.Row) -> Term:
        return Term(
            id=row["id"], canonical=row["canonical"], aliases=row["aliases"],
            category=row["category"], priority=row["priority"],
        )

    def upsert_term(self, canonical: str, aliases: str, category: str = "", priority: int = 100) -> Term:
        rows = self._execute(
            """
            INSERT INTO terms(canonical, aliases, category, priority)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(canonical) DO UPDATE SET
              aliases=excluded.aliases, category=excluded.category, priority=excluded.priority
            RETURNING *
            """,
            (canonical, aliases, category, priority),
        )
        return self._term(rows[0])

    def list_terms(self) -> list[Term]:
        return [self._term(r) for r in self._execute("SELECT * FROM terms ORDER BY canonical COLLATE NOCASE")]

    def delete_term(self, term_id: int) -> None:
        self._execute("DELETE FROM terms WHERE id=?", (term_id,))

    def _context(self, row: sqlite3.Row) -> Context:
        return Context(id=row["id"], name=row["name"], keywords=row["keywords"])

    def upsert_context(self, name: str, keywords: str) -> Context:
        rows = self._execute(
            """
            INSERT INTO contexts(name, keywords) VALUES(?, ?)
            ON CONFLICT(name) DO UPDATE SET keywords=excluded.keywords
            RETURNING *
            """,
            (name, keywords),
        )
        return self._context(rows[0])

    def list_contexts(self) -> list[Context]:
        return [self._context(r) for r in self._execute("SELECT * FROM contexts ORDER BY name")]

    def delete_context(self, context_id: int) -> None:
        self._execute("DELETE FROM contexts WHERE id=?", (context_id,))

    def record_session(self, latency_ms: int, model: str, accepted: bool) -> None:
        self._execute(
            "INSERT INTO sessions(timestamp, latency_ms, model, accepted) VALUES(?, ?, ?, ?)",
            (_now(), latency_ms, model, 1 if accepted else 0),
        )


SEED_TERMS: list[tuple[str, str, str]] = [
    ("OpenCode", "open code, open coat", "tool"),
    ("OpenCode Whisper", "open code whisper", "project"),
    ("faster-whisper", "foster whisper, faster whisper", "tool"),
    ("CTranslate2", "c translate two", "tool"),
    ("TOML", "tomo", "format"),
    ("SQLite", "sequel light", "tool"),
    ("Tkinter", "t inter", "tool"),
    ("pytest", "pie test", "tool"),
    ("cuDNN", "cu d n n", "gpu"),
    ("ESP-IDF", "esp idf", "embedded"),
    ("ESP32-P4", "esp 32 p 4, esp32 p 4", "embedded"),
    ("MeshCore", "mesh core, micheco", "project"),
    ("Cardputer", "card puter", "hardware"),
    ("RTX 5070", "rtx 50 70", "hardware"),
    ("PyInstaller", "pie installer", "tool"),
    ("PowerShell", "power shell", "tool"),
]


def seed_glossary(store: AdaptationStore) -> int:
    """Populate starter glossary terms once (only when the table is empty)."""
    if store.list_terms():
        return 0
    for canonical, aliases, category in SEED_TERMS:
        store.upsert_term(canonical, aliases, category)
    return len(SEED_TERMS)
