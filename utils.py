import time
import re
from datetime import datetime

# ---------------------------
# تنسيق النصوص لتجنب مشاكل Markdown
# ---------------------------
def escape_markdown(text: str) -> str:
    """
    تهرب الأحرف الخاصة بالـ Markdown لتجنب أخطاء TeleBot
    """
    escape_chars = r"_*[]()~`>#+-=|{}.!:"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

# ---------------------------
# تحويل الثواني إلى ساعة:دقيقة:ثانية
# ---------------------------
def format_seconds(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

# ---------------------------
# عداد انتظار متدرج (اختياري للاختبارات)
# ---------------------------
def countdown(bot, chat_id, seconds: int, message_id: int):
    """
    يحدث رسالة عداد الانتظار كل ثانية
    """
    for i in range(seconds, 0, -1):
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                  text=f"⏳ جاري التنزيل... {i}s")
            time.sleep(1)
        except:
            break

# ---------------------------
# اختصارات الوقت UTC
# ---------------------------
def now_utc_iso() -> str:
    return datetime.utcnow().isoformat()

# ---------------------------
# تحقق من رابط صالح
# ---------------------------
def is_valid_url(url: str) -> bool:
    pattern = re.compile(r'^(https?|ftp)://[^\s/$.?#].[^\s]*$', re.IGNORECASE)
    return re.match(pattern, url) is not None

# ---------------------------
# تقسيم قائمة إلى دفعات صغيرة
# ---------------------------
def chunk_list(lst: list, chunk_size: int) -> list:
    """يعيد قائمة من القوائم الصغيرة بحجم chunk_size"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]
