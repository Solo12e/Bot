import requests
import os
import time
from telebot import types

# ---------------------------
# تحميل ملف من رابط وإرساله للمستخدم
# ---------------------------
def download_and_send(bot, chat_id, url: str, filename: str = None):
    """
    يقوم بتنزيل الملف من الرابط وإرساله عبر البوت
    """
    if not filename:
        filename = url.split("/")[-1].split("?")[0]

    # رسالة انتظار
    waiting_msg = bot.send_message(chat_id, "⏳ *جارٍ تنزيل الملف، يرجى الانتظار...*")

    try:
        # تنزيل الملف تدريجيًا لتجنب استهلاك الذاكرة الكبير
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024*1024):  # 1 ميجا لكل مرة
                    if chunk:
                        f.write(chunk)
        # بعد التحميل، إزالة رسالة الانتظار
        bot.delete_message(chat_id, waiting_msg.message_id)

        # إرسال الملف للمستخدم
        with open(filename, "rb") as f:
            bot.send_document(chat_id, f, caption=f"📄 *تم تنزيل الملف بنجاح:*\n`{filename}`")

    except Exception as e:
        bot.delete_message(chat_id, waiting_msg.message_id)
        bot.send_message(chat_id, f"❌ حدث خطأ أثناء التنزيل: {e}")
    finally:
        # حذف الملف من السيرفر بعد الإرسال
        if os.path.exists(filename):
            os.remove(filename)

# ---------------------------
# تحميل ملف صغير فقط (اختياري)
# ---------------------------
def download_small_file(url: str, filename: str):
    """
    تنزيل ملف صغير جدًا بسرعة
    """
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        with open(filename, "wb") as f:
            f.write(r.content)
        return True
    except Exception as e:
        print("Download error:", e)
        return False
