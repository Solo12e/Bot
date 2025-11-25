from telebot import types

# ---------------------------
# زر زجاجي بسيط (أيقونة + نص)
# ---------------------------
def glass(text: str, emoji: str = "") -> str:
    """
    يعيد نص الزر مع أيقونة زجاجية (رمزي)
    """
    return f"{emoji} {text}".strip()

# ---------------------------
# لوحة رئيسية للمستخدم
# ---------------------------
def main_menu() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(glass("بحث عن كتاب", "🔍"), callback_data="search"),
        types.InlineKeyboardButton(glass("مساعدة", "❓"), callback_data="help")
    )
    return markup

# ---------------------------
# أزرار نتائج البحث
# ---------------------------
def search_results_button(title: str, callback_id: str) -> types.InlineKeyboardMarkup:
    """
    زر لنتيجة بحث معينة، يعرض عنوان الكتاب
    """
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(glass(title, "📖"), callback_data=callback_id)
    )
    return markup

# ---------------------------
# أزرار روابط التحميل البطيء
# ---------------------------
def download_buttons(links: list) -> types.InlineKeyboardMarkup:
    """
    links: قائمة من tuples [(label, callback_data)]
    """
    markup = types.InlineKeyboardMarkup()
    buttons = [types.InlineKeyboardButton(glass(label, "🐢"), callback_data=cb) for label, cb in links]
    for btn in buttons:
        markup.add(btn)
    return markup

# ---------------------------
# أزرار تحكم المالك
# ---------------------------
def owner_control_buttons() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(glass("عرض المستخدمين", "👥"), callback_data="owner_users"),
        types.InlineKeyboardButton(glass("إدارة الرموز", "🔑"), callback_data="owner_codes"),
        types.InlineKeyboardButton(glass("إيقاف البوت", "⏹️"), callback_data="owner_stop"),
        types.InlineKeyboardButton(glass("تشغيل البوت", "▶️"), callback_data="owner_start")
    )
    return markup

# ---------------------------
# أزرار العودة
# ---------------------------
def back_button(callback_id="back") -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(glass("⬅️ رجوع", ""), callback_data=callback_id)
    )
    return markup
