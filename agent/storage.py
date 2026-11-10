import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def initialize_database(database_path: Path) -> None:
    """Create the database and analysis table if needed."""
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                cache_key TEXT PRIMARY KEY,
                source_url TEXT NOT NULL,
                analysis_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.commit()


def create_cache_key(
    source_url: str,
    article_text: str,
    instructions: str,
    provider: str,
    model: str,
) -> str:
    """Identify the inputs used to produce an analysis."""
    inputs = {
        "source_url": source_url,
        "article_text": article_text,
        "instructions": instructions,
        "provider": provider,
        "model": model,
        "analysis_version": 1,
    }

    serialized = json.dumps(
        inputs,
        sort_keys=True,
        ensure_ascii=False,
    )

    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def load_analysis(
    database_path: Path,
    cache_key: str,
) -> dict | None:
    """Return a saved analysis, or None if it is not available."""
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            """
            SELECT analysis_json
            FROM analyses
            WHERE cache_key = ?
            """,
            (cache_key,),
        ).fetchone()

    if row is None:
        return None

    return json.loads(row[0])


def save_analysis(
    database_path: Path,
    cache_key: str,
    source_url: str,
    analysis: dict,
) -> None:
    """Save an analysis without replacing an existing entry."""
    serialized = json.dumps(analysis, ensure_ascii=False)
    created_at = datetime.now(timezone.utc).isoformat()

    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO analyses (
                cache_key,
                source_url,
                analysis_json,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (cache_key, source_url, serialized, created_at),
        )
        connection.commit()