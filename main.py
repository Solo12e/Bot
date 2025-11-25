
import telebot
from telebot import types
import time
from config import BOT_TOKEN, OWNER_ID
from auth import upsert_user, is_user_allowed, is_user_banned, validate_and_assign_code, log_activity
from keyboards import main_menu, search_results_button, download_buttons, owner_control_buttons
from search import search_books
from downloader import download_and_send

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

# ---------------------------
# بدء البوت
# ---------------------------
print("Bot MR. classic is running...")

# ---------------------------
# /start
# ---------------------------
@bot.message_handler(commands=['start'])
def handle_start(msg):
    user_id = msg.from_user.id
    upsert_user(user_id, msg.from_user.username, msg.from_user.first_name, msg.from_user.last_name)

    if is_user_banned(user_id):
        bot.send_message(user_id, "❌ لقد تم حظر حسابك من استخدام البوت.")
        return

    if not is_user_allowed(user_id):
        bot.send_message(user_id, "🔒 *أنت غير مسموح لك بالدخول بعد. أرسل رمز الدخول الذي يعطيك إياه المالك.*")
        return

    bot.send_message(user_id, "*مرحباً بك في مَكتبة MR. classic 📚*", reply_markup=main_menu())

# ---------------------------
# استقبال الرموز
# ---------------------------
@bot.message_handler(func=lambda m: m.text.isdigit())
def handle_code(msg):
    user_id = msg.from_user.id
    code = msg.text.strip()
    valid, message = validate_and_assign_code(code, user_id)
    bot.send_message(user_id, message)
    if valid:
        bot.send_message(user_id, "*تم قبول دخولك!*", reply_markup=main_menu())

# ---------------------------
# الأزرار
# ---------------------------
@bot.callback_query_handler(func=lambda c: True)
def handle_callbacks(call: types.CallbackQuery):
    user_id = call.from_user.id
    data = call.data

    # ---------------------------
    # البحث
    # ---------------------------
    if data == "search":
        msg = bot.send_message(user_id, "🔍 *اكتب اسم الكتاب الذي تريد البحث عنه:*")
        bot.register_next_step_handler(msg, handle_search)

    # ---------------------------
    # تحكم المالك
    # ---------------------------
    elif user_id == OWNER_ID:
        if data == "owner_users":
            from auth import list_users
            users = list_users(limit=50)
            text = "👥 *قائمة المستخدمين:*\n"
            for u in users:
                text += f"{u['user_id']} - {u['username']} - {'✔️' if u['allowed'] else '❌'}\n"
            bot.send_message(user_id, text)
        elif data == "owner_codes":
            from auth import list_access_codes
            codes = list_access_codes()
            text = "🔑 *قائمة الرموز:*\n"
            for c in codes:
                text += f"{c['code']} - {'✔️' if c['active'] else '❌'} - {c['expires_at']}\n"
            bot.send_message(user_id, text)

# ---------------------------
# البحث بعد استقبال النص
# ---------------------------
def handle_search(msg):
    user_id = msg.from_user.id
    query = msg.text.strip()
    bot.send_message(user_id, f"⏳ جاري البحث عن: `{query}`...")
    results = search_books(query)

    if not results:
        bot.send_message(user_id, "❌ لم يتم العثور على أي كتب.")
        return

    for idx, book in enumerate(results):
        markup = download_buttons(book['slow_links'])
        text = f"📘 *{book['title']}*\n\n{book['description']}"
        if book['cover']:
            try:
                bot.send_photo(user_id, book['cover'], caption=text, reply_markup=markup)
            except:
                bot.send_message(user_id, text, reply_markup=markup)
        else:
            bot.send_message(user_id, text, reply_markup=markup)

# ---------------------------
# التعامل مع روابط التحميل
# ---------------------------
@bot.callback_query_handler(func=lambda c: c.data.startswith("slow"))
def handle_slow_links(call):
    user_id = call.from_user.id
    url = call.data.split("|")[-1]  # صيغة: slow|<url>
    download_and_send(bot, user_id, url)

# ---------------------------
# تشغيل البوت
# ---------------------------
bot.infinity_polling()
