"""
database.py — libsql-backed data layer.

Local dev  : uses a local SQLite file via libsql (no config needed).
Production : set TURSO_DB_URL and TURSO_DB_TOKEN environment variables.
             Turso gives you a free cloud SQLite DB that survives
             Vercel's ephemeral filesystem.
"""

import os
import datetime
import libsql_client

# ── Connection config ─────────────────────────────────────────────────────────

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
_DB_FILE    = os.path.join(BASE_DIR, "study_planner.db")

TURSO_URL   = os.environ.get("TURSO_DB_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_DB_TOKEN", "")

# Vercel doesn't support WebSockets — force HTTP transport by using https://
def _get_turso_url(url):
    """Convert libsql:// to https:// so libsql uses HTTP not WebSocket."""
    if url.startswith("libsql://"):
        return "https://" + url[len("libsql://"):]
    return url

DB_PATH = TURSO_URL if TURSO_URL else _DB_FILE


def get_db():
    if TURSO_URL and TURSO_TOKEN:
        return libsql_client.create_client_sync(
            url=_get_turso_url(TURSO_URL),
            auth_token=TURSO_TOKEN,
        )
    return libsql_client.create_client_sync(url=f"file:{_DB_FILE}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rows_to_dicts(result):
    if not result.rows:
        return []
    cols = result.columns
    return [{col: row[col] for col in cols} for row in result.rows]


def _table_columns(conn, table):
    res = conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in res.rows}


# ── Schema ────────────────────────────────────────────────────────────────────

_CREATE = [
    """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE COLLATE NOCASE,
        email TEXT NOT NULL UNIQUE COLLATE NOCASE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        color TEXT NOT NULL DEFAULT '#6366f1',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(user_id, name)
    )""",
    """CREATE TABLE IF NOT EXISTS topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        deadline TEXT NOT NULL,
        difficulty INTEGER NOT NULL CHECK(difficulty BETWEEN 1 AND 5),
        estimated_hours REAL NOT NULL,
        daily_available_hours REAL NOT NULL DEFAULT 4.0,
        is_completed INTEGER NOT NULL DEFAULT 0,
        notes TEXT NOT NULL DEFAULT '',
        links TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
        date TEXT NOT NULL,
        hours REAL NOT NULL,
        entry_type TEXT NOT NULL DEFAULT 'study',
        generated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS daily_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
        subject_id INTEGER,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        log_date TEXT NOT NULL DEFAULT (date('now')),
        action TEXT NOT NULL DEFAULT 'completed'
    )""",
    """CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        n INTEGER NOT NULL DEFAULT 0,
        easiness REAL NOT NULL DEFAULT 2.5,
        interval_days INTEGER NOT NULL DEFAULT 1,
        next_review TEXT NOT NULL,
        last_quality INTEGER NOT NULL DEFAULT 4,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(topic_id, user_id)
    )""",
]

_MIGRATIONS = [
    ("subjects",   "user_id",              "ALTER TABLE subjects ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1"),
    ("topics",     "notes",                "ALTER TABLE topics ADD COLUMN notes TEXT NOT NULL DEFAULT ''"),
    ("topics",     "links",                "ALTER TABLE topics ADD COLUMN links TEXT NOT NULL DEFAULT '[]'"),
    ("daily_logs", "user_id",              "ALTER TABLE daily_logs ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE"),
    ("users",      "daily_hours_default",  "ALTER TABLE users ADD COLUMN daily_hours_default REAL NOT NULL DEFAULT 4.0"),
    ("users",      "theme",                "ALTER TABLE users ADD COLUMN theme TEXT NOT NULL DEFAULT 'system'"),
    ("users",      "notify_deadline_days", "ALTER TABLE users ADD COLUMN notify_deadline_days INTEGER NOT NULL DEFAULT 3"),
    ("users",      "show_completed",       "ALTER TABLE users ADD COLUMN show_completed INTEGER NOT NULL DEFAULT 1"),
    ("users",      "default_difficulty",   "ALTER TABLE users ADD COLUMN default_difficulty INTEGER NOT NULL DEFAULT 3"),
]


def init_db():
    conn = get_db()
    try:
        conn.batch(_CREATE)
        for table, col, sql in _MIGRATIONS:
            if col not in _table_columns(conn, table):
                try:
                    conn.execute(sql)
                except Exception:
                    pass
    finally:
        conn.close()


# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(username, email, password_hash):
    conn = get_db()
    try:
        res = conn.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?,?,?)",
            [username.strip(), email.strip().lower(), password_hash],
        )
        return res.last_insert_rowid
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_db()
    try:
        res = conn.execute("SELECT * FROM users WHERE id=?", [user_id])
        return _rows_to_dicts(res)[0] if res.rows else None
    finally:
        conn.close()


def get_user_by_username(username):
    conn = get_db()
    try:
        res = conn.execute("SELECT * FROM users WHERE username=? COLLATE NOCASE", [username])
        return _rows_to_dicts(res)[0] if res.rows else None
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_db()
    try:
        res = conn.execute("SELECT * FROM users WHERE email=? COLLATE NOCASE", [email])
        return _rows_to_dicts(res)[0] if res.rows else None
    finally:
        conn.close()


def get_preferences(user_id):
    conn = get_db()
    try:
        res = conn.execute(
            "SELECT daily_hours_default,theme,notify_deadline_days,show_completed,default_difficulty FROM users WHERE id=?",
            [user_id],
        )
        return _rows_to_dicts(res)[0] if res.rows else {
            "daily_hours_default": 4.0, "theme": "system",
            "notify_deadline_days": 3, "show_completed": 1, "default_difficulty": 3,
        }
    finally:
        conn.close()


def update_preferences(user_id, daily_hours_default, theme, notify_deadline_days, show_completed, default_difficulty):
    conn = get_db()
    try:
        conn.execute(
            "UPDATE users SET daily_hours_default=?,theme=?,notify_deadline_days=?,show_completed=?,default_difficulty=? WHERE id=?",
            [daily_hours_default, theme, notify_deadline_days, show_completed, default_difficulty, user_id],
        )
    finally:
        conn.close()


def update_account(user_id, username, email):
    conn = get_db()
    try:
        conn.execute("UPDATE users SET username=?,email=? WHERE id=?",
                     [username.strip(), email.strip().lower(), user_id])
        return None
    except Exception as e:
        return str(e)
    finally:
        conn.close()


def update_password(user_id, new_hash):
    conn = get_db()
    try:
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", [new_hash, user_id])
    finally:
        conn.close()


# ── Subjects ──────────────────────────────────────────────────────────────────

def get_all_subjects(user_id):
    conn = get_db()
    try:
        res = conn.execute(
            """SELECT s.*,COUNT(t.id) AS total_topics,
               SUM(CASE WHEN t.is_completed=1 THEN 1 ELSE 0 END) AS completed_topics
               FROM subjects s LEFT JOIN topics t ON t.subject_id=s.id
               WHERE s.user_id=? GROUP BY s.id ORDER BY s.name""",
            [user_id],
        )
        return _rows_to_dicts(res)
    finally:
        conn.close()


def add_subject(user_id, name, color="#6366f1"):
    conn = get_db()
    try:
        res = conn.execute(
            "INSERT INTO subjects (user_id,name,color) VALUES (?,?,?)", [user_id, name, color]
        )
        return res.last_insert_rowid
    finally:
        conn.close()


def delete_subject(subject_id, user_id):
    conn = get_db()
    try:
        conn.execute("DELETE FROM subjects WHERE id=? AND user_id=?", [subject_id, user_id])
    finally:
        conn.close()


# ── Topics ────────────────────────────────────────────────────────────────────

def get_topics_by_subject(subject_id, user_id):
    conn = get_db()
    try:
        res = conn.execute(
            """SELECT t.* FROM topics t JOIN subjects s ON s.id=t.subject_id
               WHERE t.subject_id=? AND s.user_id=? ORDER BY t.deadline,t.difficulty DESC""",
            [subject_id, user_id],
        )
        return _rows_to_dicts(res)
    finally:
        conn.close()


def get_all_topics(user_id):
    conn = get_db()
    try:
        res = conn.execute(
            """SELECT t.*,s.name AS subject_name,s.color AS subject_color
               FROM topics t JOIN subjects s ON s.id=t.subject_id
               WHERE s.user_id=? ORDER BY t.deadline,t.difficulty DESC""",
            [user_id],
        )
        return _rows_to_dicts(res)
    finally:
        conn.close()


def add_topic(subject_id, name, deadline, difficulty, estimated_hours, daily_hours):
    conn = get_db()
    try:
        res = conn.execute(
            "INSERT INTO topics (subject_id,name,deadline,difficulty,estimated_hours,daily_available_hours) VALUES (?,?,?,?,?,?)",
            [subject_id, name, deadline, difficulty, estimated_hours, daily_hours],
        )
        return res.last_insert_rowid
    finally:
        conn.close()


def toggle_topic_complete(topic_id, user_id):
    conn = get_db()
    try:
        conn.execute(
            "UPDATE topics SET is_completed=CASE WHEN is_completed=1 THEN 0 ELSE 1 END WHERE id=? AND subject_id IN (SELECT id FROM subjects WHERE user_id=?)",
            [topic_id, user_id],
        )
    finally:
        conn.close()


def update_topic_notes_links(topic_id, notes, links_json, user_id):
    conn = get_db()
    try:
        conn.execute(
            "UPDATE topics SET notes=?,links=? WHERE id=? AND subject_id IN (SELECT id FROM subjects WHERE user_id=?)",
            [notes, links_json, topic_id, user_id],
        )
    finally:
        conn.close()


def delete_topic(topic_id, user_id):
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM topics WHERE id=? AND subject_id IN (SELECT id FROM subjects WHERE user_id=?)",
            [topic_id, user_id],
        )
    finally:
        conn.close()


# ── Daily Logs & Streak ───────────────────────────────────────────────────────

def log_topic_completion(topic_id, subject_id, user_id):
    conn = get_db()
    try:
        today = datetime.date.today().isoformat()
        res = conn.execute(
            "SELECT 1 FROM daily_logs WHERE topic_id=? AND log_date=? AND action='completed'",
            [topic_id, today],
        )
        if not res.rows:
            conn.execute(
                "INSERT INTO daily_logs (topic_id,subject_id,user_id,log_date,action) VALUES (?,?,?,?,?)",
                [topic_id, subject_id, user_id, today, "completed"],
            )
    finally:
        conn.close()


def get_streak(user_id):
    conn = get_db()
    try:
        res = conn.execute(
            "SELECT DISTINCT log_date FROM daily_logs WHERE action='completed' AND user_id=? ORDER BY log_date DESC",
            [user_id],
        )
        dates = [datetime.date.fromisoformat(row[0]) for row in res.rows]
    finally:
        conn.close()

    if not dates:
        return {"current": 0, "best": 0, "today_logged": False}

    today = datetime.date.today()
    today_logged = dates[0] == today
    current = 0
    check = today if today_logged else today - datetime.timedelta(days=1)
    for d in dates:
        if d == check:
            current += 1
            check -= datetime.timedelta(days=1)
        elif d < check:
            break

    best = run = 1
    for i in range(1, len(dates)):
        if (dates[i - 1] - dates[i]).days == 1:
            run += 1
            best = max(best, run)
        else:
            run = 1
    best = max(best, current)
    return {"current": current, "best": best, "today_logged": today_logged}


def get_weekly_report(user_id):
    conn = get_db()
    try:
        today = datetime.date.today()
        week_ago = (today - datetime.timedelta(days=6)).isoformat()
        res = conn.execute(
            """SELECT dl.log_date,COUNT(dl.id) AS completions,GROUP_CONCAT(t.name,'||') AS topic_names
               FROM daily_logs dl JOIN topics t ON t.id=dl.topic_id
               WHERE dl.log_date>=? AND dl.action='completed' AND dl.user_id=?
               GROUP BY dl.log_date ORDER BY dl.log_date""",
            [week_ago, user_id],
        )
        rows = _rows_to_dicts(res)
    finally:
        conn.close()

    daily = {r["log_date"]: {"completions": r["completions"], "topics": r["topic_names"] or ""} for r in rows}
    return {
        "daily": daily,
        "total_completions": sum(v["completions"] for v in daily.values()),
        "active_days": len(daily),
        "best_day": max(daily.items(), key=lambda x: x[1]["completions"])[0] if daily else None,
        "week_start": week_ago,
        "week_end": today.isoformat(),
    }


# ── Analytics ─────────────────────────────────────────────────────────────────

def get_analytics_data(user_id):
    conn = get_db()
    try:
        by_subject = _rows_to_dicts(conn.execute(
            "SELECT s.name,s.color,COUNT(t.id) AS total,SUM(t.is_completed) AS done FROM subjects s LEFT JOIN topics t ON t.subject_id=s.id WHERE s.user_id=? GROUP BY s.id ORDER BY s.name",
            [user_id]))
        diff_dist = _rows_to_dicts(conn.execute(
            "SELECT t.difficulty,COUNT(*) AS cnt FROM topics t JOIN subjects s ON s.id=t.subject_id WHERE s.user_id=? GROUP BY t.difficulty ORDER BY t.difficulty",
            [user_id]))
        thirty_ago = (datetime.date.today() - datetime.timedelta(days=29)).isoformat()
        daily_completions = _rows_to_dicts(conn.execute(
            "SELECT log_date,COUNT(*) AS cnt FROM daily_logs WHERE action='completed' AND user_id=? AND log_date>=? GROUP BY log_date ORDER BY log_date",
            [user_id, thirty_ago]))
        hours_by_subject = _rows_to_dicts(conn.execute(
            "SELECT s.name,s.color,ROUND(SUM(sc.hours),1) AS total_hours FROM schedule sc JOIN topics t ON t.id=sc.topic_id JOIN subjects s ON s.id=t.subject_id WHERE sc.entry_type='study' AND s.user_id=? GROUP BY s.id ORDER BY total_hours DESC",
            [user_id]))
        tot = conn.execute(
            "SELECT SUM(t.is_completed) AS done,COUNT(*)-SUM(t.is_completed) AS pending FROM topics t JOIN subjects s ON s.id=t.subject_id WHERE s.user_id=?",
            [user_id])
        totals = _rows_to_dicts(tot)[0] if tot.rows else {"done": 0, "pending": 0}
        hard_pending = _rows_to_dicts(conn.execute(
            "SELECT t.name,t.difficulty,t.deadline FROM topics t JOIN subjects s ON s.id=t.subject_id WHERE t.is_completed=0 AND s.user_id=? ORDER BY t.difficulty DESC,t.deadline LIMIT 8",
            [user_id]))
    finally:
        conn.close()
    return {"by_subject": by_subject, "diff_dist": diff_dist,
            "daily_completions": daily_completions, "hours_by_subject": hours_by_subject,
            "totals": totals, "hard_pending": hard_pending}


# ── Schedule ──────────────────────────────────────────────────────────────────

def save_schedule(entries, user_id):
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM schedule WHERE topic_id IN (SELECT t.id FROM topics t JOIN subjects s ON s.id=t.subject_id WHERE s.user_id=?)",
            [user_id])
        stmts = [
            libsql_client.Statement(
                "INSERT INTO schedule (topic_id,date,hours,entry_type) VALUES (?,?,?,?)",
                [e["topic_id"], e["date"], e["hours"], e["entry_type"]])
            for e in entries
        ]
        if stmts:
            conn.batch(stmts)
    finally:
        conn.close()


def get_schedule(user_id):
    conn = get_db()
    try:
        res = conn.execute(
            """SELECT sc.*,t.name AS topic_name,t.difficulty,t.deadline,t.is_completed,
               s.name AS subject_name,s.color AS subject_color
               FROM schedule sc JOIN topics t ON t.id=sc.topic_id JOIN subjects s ON s.id=t.subject_id
               WHERE s.user_id=? ORDER BY sc.date,sc.entry_type DESC""",
            [user_id])
        return _rows_to_dicts(res)
    finally:
        conn.close()


# ── Dashboard ─────────────────────────────────────────────────────────────────

def get_dashboard_stats(user_id):
    conn = get_db()
    try:
        stats = {}
        stats["total_subjects"] = conn.execute(
            "SELECT COUNT(*) FROM subjects WHERE user_id=?", [user_id]).rows[0][0]
        stats["total_topics"] = conn.execute(
            "SELECT COUNT(*) FROM topics t JOIN subjects s ON s.id=t.subject_id WHERE s.user_id=?",
            [user_id]).rows[0][0]
        stats["completed_topics"] = conn.execute(
            "SELECT COUNT(*) FROM topics t JOIN subjects s ON s.id=t.subject_id WHERE s.user_id=? AND t.is_completed=1",
            [user_id]).rows[0][0]
        stats["pending_topics"] = stats["total_topics"] - stats["completed_topics"]
        stats["upcoming_deadlines"] = _rows_to_dicts(conn.execute(
            """SELECT DISTINCT t.deadline,t.name AS topic_name,s.name AS subject_name,s.color,t.difficulty
               FROM topics t JOIN subjects s ON s.id=t.subject_id
               WHERE s.user_id=? AND t.is_completed=0
                 AND t.deadline>=date('now') AND t.deadline<=date('now','+14 days')
               ORDER BY t.deadline LIMIT 5""",
            [user_id]))
    finally:
        conn.close()
    return stats


# ── Spaced Repetition (SM-2) ──────────────────────────────────────────────────

def upsert_review(topic_id, user_id, n, easiness, interval_days, next_review, quality):
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO reviews (topic_id,user_id,n,easiness,interval_days,next_review,last_quality,updated_at)
               VALUES (?,?,?,?,?,?,?,datetime('now'))
               ON CONFLICT(topic_id,user_id) DO UPDATE SET
               n=excluded.n,easiness=excluded.easiness,interval_days=excluded.interval_days,
               next_review=excluded.next_review,last_quality=excluded.last_quality,updated_at=datetime('now')""",
            [topic_id, user_id, n, easiness, interval_days, next_review.isoformat(), quality])
    finally:
        conn.close()


def get_review(topic_id, user_id):
    conn = get_db()
    try:
        res = conn.execute("SELECT * FROM reviews WHERE topic_id=? AND user_id=?", [topic_id, user_id])
        return _rows_to_dicts(res)[0] if res.rows else None
    finally:
        conn.close()


def get_due_reviews(user_id):
    conn = get_db()
    try:
        today = datetime.date.today().isoformat()
        res = conn.execute(
            """SELECT r.*,t.name AS topic_name,t.difficulty,t.deadline,t.estimated_hours,
               t.daily_available_hours,s.name AS subject_name,s.color AS subject_color,
               t.subject_id,t.is_completed
               FROM reviews r JOIN topics t ON t.id=r.topic_id JOIN subjects s ON s.id=t.subject_id
               WHERE r.user_id=? AND r.next_review<=? ORDER BY r.next_review,t.difficulty DESC""",
            [user_id, today])
        return _rows_to_dicts(res)
    finally:
        conn.close()


def get_all_reviews(user_id):
    conn = get_db()
    try:
        res = conn.execute(
            """SELECT r.*,t.name AS topic_name,t.difficulty,s.name AS subject_name
               FROM reviews r JOIN topics t ON t.id=r.topic_id JOIN subjects s ON s.id=t.subject_id
               WHERE r.user_id=? ORDER BY r.next_review""",
            [user_id])
        return _rows_to_dicts(res)
    finally:
        conn.close()


# ── Schedule move ─────────────────────────────────────────────────────────────

def move_schedule_entry(entry_id, new_date, user_id):
    conn = get_db()
    try:
        conn.execute(
            "UPDATE schedule SET date=? WHERE id=? AND topic_id IN (SELECT t.id FROM topics t JOIN subjects s ON s.id=t.subject_id WHERE s.user_id=?)",
            [new_date, entry_id, user_id])
    finally:
        conn.close()


# ── Stale schedule check ──────────────────────────────────────────────────────

def has_stale_schedule(user_id):
    conn = get_db()
    try:
        today = datetime.date.today().isoformat()
        res = conn.execute(
            """SELECT 1 FROM schedule sc JOIN topics t ON t.id=sc.topic_id
               JOIN subjects s ON s.id=t.subject_id
               WHERE s.user_id=? AND sc.date<? AND t.is_completed=0 LIMIT 1""",
            [user_id, today])
        return len(res.rows) > 0
    finally:
        conn.close()
