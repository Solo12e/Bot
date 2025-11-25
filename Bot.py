import telebot
from telebot import types
import requests
import google.generativeai as genai
import sqlite3
import os
import time
import json
import threading
import random
import string
from datetime import datetime, timedelta

# --- التكوين والإعدادات ---
BOT_TOKEN = "8452773152:AAEJyOt0N5OxLZ9lBzTaLefKF4_wVu8_oSg"
OWNER_ID = 8088087792
GEMINI_API_KEY = "AIzaSyDD-ZHKeqXI2ZlMMb1NNFJUSrECTw5YqBQ"

# إعداد Gemini
genai.configure(api_key=GEMINI_API_KEY)
# ملاحظة: نستخدم موديل يدعم JSON mode لنتائج دقيقة
generation_config = {
    "temperature": 0.1,
    "response_mime_type": "application/json",
}
model = genai.GenerativeModel("gemini-2.0-flash", generation_config=generation_config)

bot = telebot.TeleBot(BOT_TOKEN)

# رؤوس طلبات المتصفح لتجنب الحظر البسيط
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# --- قاعدة البيانات (SQLite) ---
DB_NAME = "mr_classic.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # جدول المستخدمين
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, username TEXT, access_key TEXT, 
                  expiry_date TEXT, is_banned INTEGER DEFAULT 0)''')
    # جدول المفاتيح المولدة وغير المستخدمة
    c.execute('''CREATE TABLE IF NOT EXISTS generated_keys
                 (key_code TEXT PRIMARY KEY, duration_days INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# --- دوال المساعدة للذكاء الاصطناعي ---

def ai_parse_search(html_content):
    """استخراج نتائج البحث باستخدام Gemini"""
    prompt = """
    Analyze the following HTML from Anna's Archive search results.
    Extract a list of books. For each book, get:
    1. 'title': The full title.
    2. 'author': The author names.
    3. 'cover': The image URL (img src).
    4. 'link': The relative link to the book detail page (starts with /md5/...).
    5. 'format': The file format (PDF, EPUB, etc.).
    
    Return the result strictly as a JSON list of objects.
    """
    try:
        response = model.generate_content([prompt, html_content[:50000]]) # نرسل جزءاً من النص لتجنب تجاوز الحد إذا كان ضخماً
        return json.loads(response.text)
    except Exception as e:
        print(f"Error AI Search: {e}")
        return []

def ai_parse_details(html_content):
    """استخراج تفاصيل الكتاب وروابط التحميل البطيء"""
    prompt = """
    Analyze the HTML of a book detail page.
    Extract:
    1. 'description': The book description (summary).
    2. 'slow_links': A list of URLs found under "Slow Partner Server" or similar slow download sections. 
       Ignore "Fast Partner Server" links.
    
    Return JSON: {"description": "...", "slow_links": ["url1", "url2"]}
    """
    try:
        response = model.generate_content([prompt, html_content[:50000]])
        return json.loads(response.text)
    except Exception as e:
        print(f"Error AI Details: {e}")
        return {"description": "لا يوجد وصف متاح.", "slow_links": []}

def ai_extract_final_link(html_content):
    """استخراج رابط التحميل المباشر من صفحة الانتظار"""
    prompt = """
    Analyze this HTML from a download page. 
    Find the direct download URL for the file. 
    Look for text like "Download now" or a link ending in .pdf, .epub, .mobi inside the content.
    Usually it says "To download, copy this URL...". Extract that specific URL.
    
    Return JSON: {"download_url": "THE_URL"}
    """
    try:
        response = model.generate_content([prompt, html_content[:30000]])
        data = json.loads(response.text)
        return data.get("download_url")
    except Exception as e:
        print(f"Error AI Final Link: {e}")
        return None

# --- إدارة المستخدمين والصلاحيات ---

def generate_key(days=30):
    """توليد مفتاح عشوائي"""
    chars = string.ascii_uppercase + string.digits
    key = ''.join(random.choice(chars) for _ in range(12))
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO generated_keys (key_code, duration_days) VALUES (?, ?)", (key, days))
    conn.commit()
    conn.close()
    return key

def check_user_access(user_id):
    """التحقق من صلاحية المستخدم"""
    if user_id == OWNER_ID:
        return True, "admin"
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT expiry_date, is_banned FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    
    if not result:
        return False, "new"
    
    expiry_str, is_banned = result
    if is_banned:
        return False, "banned"
        
    expiry = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expiry:
        return False, "expired"
        
    return True, "active"

def activate_user(user_id, username, key_code):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # التحقق من المفتاح
    c.execute("SELECT duration_days FROM generated_keys WHERE key_code=?", (key_code,))
    key_data = c.fetchone()
    
    if not key_data:
        conn.close()
        return False, "المفتاح غير صحيح."
        
    days = key_data[0]
    expiry_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    
    # إضافة أو تحديث المستخدم
    c.execute("INSERT OR REPLACE INTO users (user_id, username, access_key, expiry_date, is_banned) VALUES (?, ?, ?, ?, 0)",
              (user_id, username, key_code, expiry_date))
    
    # حذف المفتاح المستخدم
    c.execute("DELETE FROM generated_keys WHERE key_code=?", (key_code,))
    conn.commit()
    conn.close()
    return True, f"تم التفعيل بنجاح! اشتراكك صالح لمدة {days} يوم."

# --- لوحة تحكم المالك ---

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != OWNER_ID:
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🔑 توليد مفتاح (30 يوم)", callback_data="admin_gen_30")
    btn2 = types.InlineKeyboardButton("🔑 توليد مفتاح (سنة)", callback_data="admin_gen_365")
    btn3 = types.InlineKeyboardButton("👥 عدد المستخدمين", callback_data="admin_stats")
    btn4 = types.InlineKeyboardButton("🛑 حظر مستخدم", callback_data="admin_ban")
    
    markup.add(btn1, btn2, btn3, btn4)
    bot.reply_to(message, "👮‍♂️ **لوحة تحكم المالك - MR. Classic**", parse_mode="Markdown", reply_markup=markup)

# --- التعامل مع البداية والبحث ---

@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    has_access, status = check_user_access(user_id)
    
    if user_id == OWNER_ID:
        bot.send_message(user_id, "أهلاً بك يا سيدي (MR. Classic). أنت المالك ولدي جميع الصلاحيات.\nاكتب /admin للتحكم.", parse_mode="Markdown")
        return

    if not has_access:
        if status == "banned":
            bot.send_message(user_id, "⛔ حسابك محظور من استخدام البوت.")
            return
        
        # إرسال طلب للمالك (محاكاة) أو طلب الكود
        msg_text = (
            f"🔒 **أهلاً بك في مكتبة MR. Classic**\n\n"
            f"هذا البوت خاص ولا يمكن استخدامه إلا بمفتاح دعوة.\n"
            f"🆔 الآيدي الخاص بك: `{user_id}`\n\n"
            f"للحصول على مفتاح الدخول، يرجى التواصل مع المالك وتزويده بالآيدي الخاص بك.\n"
            f"اذا كان لديك مفتاح، ارسله الآن في المحادثة."
        )
        
        # إشعار المالك بمحاولة الدخول
        try:
            bot.send_message(OWNER_ID, f"🔔 **محاولة دخول جديدة**\nالاسم: @{username}\nالآيدي: `{user_id}`", parse_mode="Markdown")
        except:
            pass
            
        bot.send_message(user_id, msg_text, parse_mode="Markdown")
        return

    bot.send_message(user_id, "📚 **مرحباً بك في مكتبتك..**\nأرسل اسم الكتاب للبحث عنه فوراً.", parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    # التحقق من الصلاحية أولاً
    has_access, status = check_user_access(user_id)
    if not has_access and user_id != OWNER_ID:
        # إذا أرسل كود تفعيل
        if len(text) == 12 and text.isalnum():
            success, response = activate_user(user_id, message.from_user.username, text)
            bot.reply_to(message, response)
            if success:
                 bot.send_message(user_id, "يمكنك الآن إرسال اسم أي كتاب للبحث عنه.")
        else:
            bot.reply_to(message, "⛔ يجب عليك إدخال مفتاح تفعيل صالح.")
        return

    # عملية البحث
    msg = bot.send_message(user_id, f"🔍 جاري البحث عن: *{text}* ...", parse_mode="Markdown")
    
    try:
        search_url = f"https://ar.annas-archive.li/search?q={text}"
        res = requests.get(search_url, headers=HEADERS)
        
        if res.status_code != 200:
            bot.edit_message_text("❌ حدث خطأ في الاتصال بالموقع.", chat_id=user_id, message_id=msg.message_id)
            return

        # تحليل النتائج بالذكاء الاصطناعي
        books = ai_parse_search(res.text)
        
        if not books:
            bot.edit_message_text("❌ لم يتم العثور على نتائج.", chat_id=user_id, message_id=msg.message_id)
            return

        # عرض النتائج (أول نتيجة كمثال، أو قائمة)
        # سنعرض قائمة بأول 5 نتائج
        markup = types.InlineKeyboardMarkup()
        for i, book in enumerate(books[:5]):
            btn_text = f"{i+1}. {book.get('title', 'No Title')[:30]} ({book.get('format', '?')})"
            callback_data = f"view_{i}" # سنخزن البيانات مؤقتاً أو نستخدم طريقة ذكية
            # ملاحظة: حجم الـ callback محدود، لذا الأفضل تخزين النتائج في dict مؤقت
            
            # حل سريع: تخزين النتائج في متغير عام (غير مثالي للإنتاج الضخم لكنه يعمل هنا)
            # الأفضل استخدام Redis أو قاعدة بيانات
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"sel_{i}"))
            
        # تخزين النتائج مؤقتاً في ذاكرة البوت (يجب تحسين هذا للإنتاج الفعلي)
        global search_cache
        if 'search_cache' not in globals(): search_cache = {}
        search_cache[user_id] = books

        bot.delete_message(user_id, msg.message_id)
        bot.send_message(user_id, f"📚 نتائج البحث عن: {text}", reply_markup=markup)

    except Exception as e:
        bot.edit_message_text(f"⚠️ حدث خطأ: {e}", chat_id=user_id, message_id=msg.message_id)

# --- التعامل مع الأزرار (Callbacks) ---

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    data = call.data

    # --- أدوات الأدمن ---
    if user_id == OWNER_ID:
        if data == "admin_gen_30":
            key = generate_key(30)
            bot.send_message(user_id, f"✅ مفتاح جديد (30 يوم):\n`{key}`", parse_mode="Markdown")
            return
        elif data == "admin_gen_365":
            key = generate_key(365)
            bot.send_message(user_id, f"✅ مفتاح جديد (سنة):\n`{key}`", parse_mode="Markdown")
            return
        elif data == "admin_stats":
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users")
            count = c.fetchone()[0]
            conn.close()
            bot.answer_callback_query(call.id, f"عدد المستخدمين: {count}")
            return

    # --- أدوات المستخدم ---
    
    # اختيار كتاب
    if data.startswith("sel_"):
        index = int(data.split("_")[1])
        if user_id in search_cache:
            book = search_cache[user_id][index]
            
            # إرسال الغلاف أولاً
            cover_url = book.get('cover', '')
            details_text = f"📖 **{book.get('title')}**\n\n👤 المؤلف: {book.get('author')}\n📄 الصيغة: {book.get('format')}\n\n⏳ جاري جلب التفاصيل..."
            
            try:
                if cover_url and cover_url.startswith("http"):
                    bot.send_photo(user_id, cover_url, caption=details_text, parse_mode="Markdown")
                else:
                    bot.send_message(user_id, details_text, parse_mode="Markdown")
            except:
                bot.send_message(user_id, details_text, parse_mode="Markdown")

            # جلب التفاصيل والروابط
            full_link = f"https://ar.annas-archive.li{book.get('link')}"
            res = requests.get(full_link, headers=HEADERS)
            details = ai_parse_details(res.text)
            
            desc = details.get('description', '..')
            slow_links = details.get('slow_links', [])
            
            final_msg = f"📖 **{book.get('title')}**\n\n📝 الوصف:\n{desc[:800]}..." # تقصير الوصف
            
            markup = types.InlineKeyboardMarkup()
            for idx, link in enumerate(slow_links):
                # نستخدم short_hash أو index لتمرير الرابط لأن الرابط طويل جداً على الـ callback
                # سنخزن الرابط في كاش جديد
                link_id = f"dl_{user_id}_{idx}"
                global download_cache
                if 'download_cache' not in globals(): download_cache = {}
                download_cache[link_id] = link
                
                markup.add(types.InlineKeyboardButton(f"📥 خيار تحميل {idx+1} (بطيء)", callback_data=link_id))
            
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_search"))
            
            bot.send_message(user_id, final_msg, parse_mode="Markdown", reply_markup=markup)

    # بدء التحميل
    elif data.startswith("dl_"):
        link_id = data
        if link_id in download_cache:
            raw_url = download_cache[link_id]
            
            # رسالة الانتظار
            wait_msg = bot.send_message(user_id, "⏳ **يرجى الانتظار...**\n🐢 جاري الاتصال بخوادم التحميل البطيء واستخراج الملف...", parse_mode="Markdown")
            
            # العملية تأخذ وقتاً، لذا سنقوم بها في دالة منفصلة
            threading.Thread(target=process_download, args=(user_id, raw_url, wait_msg.message_id)).start()
        else:
            bot.answer_callback_query(call.id, "انتهت صلاحية الرابط، ابحث مجدداً.")

# --- منطق التحميل المعقد ---

def process_download(user_id, initial_url, message_id):
    try:
        # 1. الدخول لصفحة التحميل الأولية
        session = requests.Session()
        session.headers.update(HEADERS)
        
        # بعض الروابط قد تحتاج تعديل للوصول لصفحة الانتظار
        res = session.get(initial_url)
        
        # 2. استخدام AI لاستخراج رابط التحميل النهائي من صفحة الانتظار
        final_url = ai_extract_final_link(res.text)
        
        if not final_url:
             # محاولة ثانية: أحياناً يكون الرابط مباشراً في زر "Download now"
             # سنفترض أن الـ AI ذكي كفاية، لكن كاحتياط، إذا فشل، نعطي الرابط للمستخدم
             bot.edit_message_text(f"⚠️ لم يستطع البوت سحب الملف مباشرة.\n🔗 تفضل الرابط للتحميل اليدوي:\n{initial_url}", chat_id=user_id, message_id=message_id)
             return

        # 3. بدء التحميل الفعلي للملف
        bot.edit_message_text("⏳ **تم العثور على الملف!**\n⬇️ جاري التنزيل إلى السيرفر (قد يستغرق وقتاً حسب الحجم)...", chat_id=user_id, message_id=message_id)
        
        file_response = session.get(final_url, stream=True)
        filename = final_url.split("/")[-1]
        # تنظيف اسم الملف
        filename = filename.split("?")[0] 
        if len(filename) > 50: filename = "book_mr_classic" + os.path.splitext(filename)[1]

        file_path = f"downloads/{filename}"
        os.makedirs("downloads", exist_ok=True)
        
        with open(file_path, 'wb') as f:
            for chunk in file_response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # 4. رفع الملف لتيليجرام
        bot.edit_message_text("📤 جاري الرفع إليك...", chat_id=user_id, message_id=message_id)
        
        with open(file_path, 'rb') as doc:
            bot.send_document(user_id, doc, caption="🎁 **تم التحميل بواسطة مكتبة MR. Classic**")
            
        # 5. تنظيف
        bot.delete_message(user_id, message_id)
        os.remove(file_path)

    except Exception as e:
        bot.edit_message_text(f"❌ فشل التحميل: {str(e)[:100]}", chat_id=user_id, message_id=message_id)

# --- التشغيل ---
print("Bot MR. Classic is running...")
bot.infinity_polling()
  
