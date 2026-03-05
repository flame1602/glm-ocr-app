"""
GLM-OCR App — SQLite Job History & Statistics
"""
import sqlite3
import time
from contextlib import contextmanager
from config import DB_PATH


def init_db():
    """Create tables if not exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                pages INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                source TEXT DEFAULT 'upload',
                time_convert REAL DEFAULT 0,
                time_ocr REAL DEFAULT 0,
                avg_per_page REAL DEFAULT 0,
                output_file TEXT DEFAULT '',
                error_msg TEXT DEFAULT '',
                created_at REAL DEFAULT 0,
                completed_at REAL DEFAULT 0
            )
        """)
        conn.commit()


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def add_job(filename, source="upload"):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO jobs (filename, source, status, created_at) VALUES (?, ?, 'pending', ?)",
            (filename, source, time.time())
        )
        conn.commit()
        return cur.lastrowid


def update_job(job_id, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [job_id]
    with get_db() as conn:
        conn.execute(f"UPDATE jobs SET {sets} WHERE id=?", vals)
        conn.commit()


def complete_job(job_id, pages, time_convert, time_ocr, output_file):
    avg = time_ocr / max(pages, 1)
    with get_db() as conn:
        conn.execute(
            """UPDATE jobs SET status='ok', pages=?, time_convert=?, time_ocr=?,
               avg_per_page=?, output_file=?, completed_at=? WHERE id=?""",
            (pages, round(time_convert, 2), round(time_ocr, 2), round(avg, 2),
             output_file, time.time(), job_id)
        )
        conn.commit()


def fail_job(job_id, error_msg):
    with get_db() as conn:
        conn.execute(
            "UPDATE jobs SET status='error', error_msg=?, completed_at=? WHERE id=?",
            (str(error_msg)[:500], time.time(), job_id)
        )
        conn.commit()


def get_recent_jobs(limit=50):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_stats():
    with get_db() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) as total_jobs,
                SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END) as success_jobs,
                SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) as error_jobs,
                SUM(CASE WHEN status='ok' THEN pages ELSE 0 END) as total_pages,
                SUM(CASE WHEN status='ok' THEN time_ocr ELSE 0 END) as total_ocr_time,
                AVG(CASE WHEN status='ok' THEN avg_per_page END) as avg_time_per_page
            FROM jobs
        """).fetchone()
        return dict(row) if row else {}


def get_daily_stats(days=30):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                DATE(created_at, 'unixepoch', 'localtime') as day,
                COUNT(*) as jobs,
                SUM(CASE WHEN status='ok' THEN pages ELSE 0 END) as pages
            FROM jobs
            WHERE created_at > ?
            GROUP BY day ORDER BY day
        """, (time.time() - days * 86400,)).fetchall()
        return [dict(r) for r in rows]
