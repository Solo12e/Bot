# -*- coding: utf-8 -*-
"""
auth.py
نظام إدارة الوصول والاشتراكات والمالك لبوت مَكتبة MR. classic
المهام:
- إنشاء رموز وصول قابلة للتخصيص (صلاحية زمنية)
- تفعيل/تعطيل/قوائم الرموز
- تسجيل المستخدمين وإدارة الحظر
- تتبع النشاط البسيط
- واجهة دوال يمكن استدعاؤها من main.py أو واجهة إدارية داخل البوت
"""

import sqlite3
from datetime import datetime, timedelta
import secrets
from typing import Tuple, Optional, List, Dict
from config import OWNER_ID  # تأكد أن OWNER_ID معرف في config.py

DB_PATH = "bot.db"  # تأكد أن هذا المسار متوافق مع config.py أو استبدله عند الاستيراد

# ---------------------------
# تهيئة قاعدة البيانات
# ---------------------------
def init_auth_db(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    # جدول رموز الوصول
    cur.execute("""
    CREATE TABLE IF NOT EXISTS access_codes (
        code TEXT PRIMARY KEY,
        created_at TEXT,
        expires_at TEXT,
        active INTEGER DEFAULT 1,
        assigned_user_id INTEGER
    )
    """)
    # جدول المستخدمين
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        allowed INTEGER DEFAULT 0,
        banned INTEGER DEFAULT 0,
        created_at TEXT,
        last_seen TEXT
    )
    """)
    # جدول نشاطات خفيفة
    cur.execute("""
    CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        ts TEXT
    )
    """)
    conn.commit()
    conn.close()

# ---------------------------
# دالة تحقق المستخدم
# ---------------------------
def is_user_allowed(user_id: int, db_path: str = DB_PATH) -> bool:
    # السماح التلقائي للمالك
    if user_id == OWNER_ID:
        return True
    # باقي التحقق الاعتيادي للمستخدمين
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT allowed FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return bool(row and row[0] == 1)

def is_user_banned(user_id: int, db_path: str = DB_PATH) -> bool:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT banned FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return bool(row and row[0] == 1)

# ---------------------------
# إدارة الرموز (Access Codes)
# ---------------------------
def create_access_code(days_valid: int = 7, db_path: str = DB_PATH) -> Tuple[str, str]:
    code = secrets.token_hex(6)
    created = datetime.utcnow()
    expires = created + timedelta(days=days_valid)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO access_codes (code, created_at, expires_at, active) VALUES (?, ?, ?, ?)",
        (code, created.isoformat(), expires.isoformat(), 1)
    )
    conn.commit()
    conn.close()
    return code, expires.isoformat()

def deactivate_access_code(code: str, db_path: str = DB_PATH) -> bool:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("UPDATE access_codes SET active=0 WHERE code=?", (code,))
    changed = cur.rowcount > 0
    conn.commit()
    conn.close()
    return changed

def extend_access_code(code: str, extra_days: int, db_path: str = DB_PATH) -> bool:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT expires_at FROM access_codes WHERE code=?", (code,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False
    current_expires = datetime.fromisoformat(row[0])
    new_expires = current_expires + timedelta(days=extra_days)
    cur.execute("UPDATE access_codes SET expires_at=?, active=1 WHERE code=?", (new_expires.isoformat(), code))
    conn.commit()
    conn.close()
    return True

def list_access_codes(db_path: str = DB_PATH) -> List[Dict]:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT code, created_at, expires_at, active, assigned_user_id FROM access_codes ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    keys = ["code", "created_at", "expires_at", "active", "assigned_user_id"]
    return [dict(zip(keys, r)) for r in rows]

def validate_and_assign_code(code: str, user_id: int, db_path: str = DB_PATH) -> Tuple[bool, str]:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT code, expires_at, active FROM access_codes WHERE code=?", (code,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, "الرمز غير موجود."
    _, expires_at, active = row
    if active != 1:
        conn.close()
        return False, "الرمز مُعطّل."
    if datetime.fromisoformat(expires_at) < datetime.utcnow():
        conn.close()
        return False, "انتهت صلاحية الرمز."
    cur.execute("UPDATE access_codes SET assigned_user_id=? WHERE code=?", (user_id, code))
    conn.commit()
    conn.close()
    return True, "تم تفعيل الرمز وربطه بحسابك."

# ---------------------------
# إدارة المستخدمين
# ---------------------------
def upsert_user(user_id: int, username: Optional[str] = None,
                first_name: Optional[str] = None, last_name: Optional[str] = None,
                db_path: str = DB_PATH) -> None:
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (user_id, username, first_name, last_name, created_at, last_seen)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name,
            last_name=excluded.last_name,
            last_seen=excluded.last_seen
    """, (user_id, username or "", first_name or "", last_name or "", now, now))
    conn.commit()
    conn.close()

def set_user_allowed(user_id: int, allowed: bool, db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("UPDATE users SET allowed=? WHERE user_id=?", (1 if allowed else 0, user_id))
    conn.commit()
    conn.close()

def ban_user(user_id: int, db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("UPDATE users SET banned=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def unban_user(user_id: int, db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("UPDATE users SET banned=0 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def get_user_info(user_id: int, db_path: str = DB_PATH) -> Optional[Dict]:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, first_name, last_name, allowed, banned, created_at, last_seen FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    keys = ["user_id", "username", "first_name", "last_name", "allowed", "banned", "created_at", "last_seen"]
    return dict(zip(keys, row))

def list_users(limit: int = 100, db_path: str = DB_PATH) -> List[Dict]:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, first_name, last_name, allowed, banned, created_at, last_seen FROM users ORDER BY last_seen DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    keys = ["user_id", "username", "first_name", "last_name", "allowed", "banned", "created_at", "last_seen"]
    return [dict(zip(keys, r)) for r in rows]

# ---------------------------
# نشاط المستخدم (سجل بسيط)
# ---------------------------
def log_activity(user_id: int, action: str, db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("INSERT INTO activity_log (user_id, action, ts) VALUES (?, ?, ?)", (user_id, action, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def get_activity_logs(limit: int = 200, db_path: str = DB_PATH) -> List[Dict]:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT id, user_id, action, ts FROM activity_log ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    keys = ["id", "user_id", "action", "ts"]
    return [dict(zip(keys, r)) for r in rows]

# ---------------------------
# أدوات مساعدة صغيرة
# ---------------------------
def assign_code_to_user(code: str, user_id: int, db_path: str = DB_PATH) -> bool:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("UPDATE access_codes SET assigned_user_id=? WHERE code=?", (user_id, code))
    ok = cur.rowcount > 0
    conn.commit()
    conn.close()
    return ok

# ---------------------------
# تهيئة سريعة عند الاستيراد
# ---------------------------
try:
    init_auth_db(DB_PATH)
except Exception:
    pass

# ---------------------------
# نهاية الملف
# --------------------------
# ---------------------------
