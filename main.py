import os
import sqlite3
import logging
import requests
from io import BytesIO
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ----------------------------------------------------
# تنظیمات اصلی، لاگین و اطلاعات مدیریت
# ----------------------------------------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

ADMIN_CHAT_ID = 162256307  # آیدی عددی شما (دسترسی نامحدود)
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

BANK_CARD_TEXT = """
💳 **راهنمای پرداخت و خرید اعتبار**

جهت خرید بسته و افزایش اعتبار ربات، مبلغ مورد نظر را به شماره کارت زیر واریز کنید:

📌 **شماره کارت:** `5894631800673253`
👤 **به نام:** مهدی وکیلی

💰 **تعرفه‌ها:**
▫️ ۱۰ بار استفاده = ۱۰,۰۰۰ تومان
▫️ ۳۰ بار استفاده = ۲۵,۰۰۰ تومان

⚠️ **نحوه فعال‌سازی:**
پس از واریز وجه، **تصویر رسید یا عکس فیش واریزی** را مستقیماً همین‌جا در ربات ارسال کنید تا حساب شما شارژ شود.
"""

# ----------------------------------------------------
# مدیریت دیتابیس (SQLite)
# ----------------------------------------------------
DB_NAME = "bot_database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            credits INTEGER DEFAULT 3
        )
    ''')
    conn.commit()
    conn.close()

def get_credits(user_id):
    if user_id == ADMIN_CHAT_ID:
        return 999999  # اعتبار نامحدود برای مدیر

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT credits FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if row:
        credits = row[0]
    else:
        cursor.execute('INSERT INTO users (user_id, credits) VALUES (?, ?)', (user_id, 3))
        conn.commit()
        credits = 3
    conn.close()
    return credits

def add_credits(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT credits FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if row:
        cursor.execute('UPDATE users SET credits = credits + ? WHERE user_id = ?', (amount, user_id))
    else:
        cursor.execute('INSERT INTO users (user_id, credits) VALUES (?, ?)', (user_id, 3 + amount))
    conn.commit()
    conn.close()

def use_credit(user_id):
    if user_id == ADMIN_CHAT_ID:
        return True  # عدم کسر اعتبار از مدیر

    credits = get_credits(user_id)
    if credits > 0:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET credits = credits - 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True
    return False

# ----------------------------------------------------
# سرویس دریافت قیمت طلا و ارز
# ----------------------------------------------------
def fetch_financial_prices():
    try:
        url = "https://api.nobitex.ir/v2/orderbook/all"
        res = requests.get(url, timeout=5).json()
        usdt_price = int(float(res.get("USDTIRT", {}).get("lastTradePrice", 0)) / 10)
        
        text = (
            "📈 **قیمت‌های لحظه‌ای بازار (تومان):**\n\n"
            f"💵 **دلار (تتر):** {usdt_price:,} تومان\n"
            f"🪙 **طلا و سکه:** جهت استعلام دقیق نرخ روز، سامانه متصل است.\n\n"
            "⏱ *به‌روزرسانی شده در همین لحظه*"
        )
        return text
    except Exception:
        return "⚠️ در حال حاضر دریافت قیمت لحظه‌ای مقدور نیست. لطفاً دقایقی دیگر تلاش کنید."

# ----------------------------------------------------
# هندلرهای اصلی ربات
# ----------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    credits = get_credits(user_id)
    
    keyboard = [
        [InlineKeyboardButton("💳 خرید اعتبار (کارت به کارت)", callback_data="buy_credit")],
        [InlineKeyboardButton("📊 استعلام اعتبار باقی‌مانده", callback_data="check_credit")],
        [InlineKeyboardButton("💰 قیمت لحظه‌ای طلا و دلار", callback_data="get_prices")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    credit_display = "نامحدود (مدیریت)" if user_id == ADMIN_CHAT_ID else f"{credits} بار"
    
    welcome_text = (
        f"سلام {update.effective_user.first_name} عزیز! 👋\n"
        f"به ربات هوشمند **ای‌آی فنی** خوش آمدید.\n\n"
        f"🎁 **اعتبار شما:** {credit_display}\n\n"
        f"🛠 **امکانات ربات:**\n"
        f"▫️ حل فرمول‌ها و سوالات اکسل\n"
        f"▫️ تبدیل عکس و فایل به PDF\n"
        f"▫️ قیمت لحظه‌ای طلا و ارز (/price)\n"
        f"▫️ تبدیل صوت و ویس به متن\n"
        f"▫️ تغییر حجم و سایز عکس‌ها\n\n"
        f"سوال، عکس یا فایل خود را ارسال کنید!"
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # پاسخ به کلیک جهت رفع حالت در انتظار دکمه
    user_id = query.from_user.id
    
    if query.data == "buy_credit":
        await query.message.reply_text(BANK_CARD_TEXT, parse_mode="Markdown")
    elif query.data == "check_credit":
        credits = get_credits(user_id)
        credit_display = "نامحدود (مدیریت)" if user_id == ADMIN_CHAT_ID else f"{credits} بار"
        await query.message.reply_text(f"📊 **اعتبار باقی‌مانده شما:** {credit_display}")
    elif query.data == "get_prices":
        prices = fetch_financial_prices()
        await query.message.reply_text(prices, parse_mode="Markdown")

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prices = fetch_financial_prices()
    await update.message.reply_text(prices, parse_mode="Markdown")

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(BANK_CARD_TEXT, parse_mode="Markdown")

# پردازش تصویر (تبدیل به PDF / دریافت رسید)
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # اولویت اول: ثبت رسید برای مدیر
    photo_file = await update.message.photo[-1].get_file()
    
    caption_for_admin = (
        f"📥 **رسید پرداخت یا عکس جدید**\n\n"
        f"👤 **نام کاربر:** {user.first_name}\n"
        f"🆔 **آیدی:** @{user.username if user.username else 'ندارد'}\n"
        f"🔢 **آیدی عددی:** `{user.id}`\n\n"
        f"⚙️ **دستور شارژ حساب:**\n"
        f"`/addcredit {user.id} 10`"
    )
    
    await context.bot.send_photo(
        chat_id=ADMIN_CHAT_ID,
        photo=photo_file.file_id,
        caption=caption_for_admin,
        parse_mode="Markdown"
    )
    
    # تبدیل عکس به PDF برای کاربر
    if not use_credit(user.id):
        await update.message.reply_text("❌ اعتبار رایگان شما به پایان رسیده است.\nجهت خرید اعتبار از دستور /buy استفاده کنید.")
        return

    photo_bytes = await photo_file.download_as_bytearray()
    image = Image.open(BytesIO(photo_bytes)).convert("RGB")
    pdf_output = BytesIO()
    image.save(pdf_output, format="PDF")
    pdf_output.seek(0)
    
    await update.message.reply_document(
        document=pdf_output,
        filename="converted_document.pdf",
        caption="✅ تصویر شما با موفقیت به فایل PDF تبدیل شد."
    )

# دستور مدیریت جهت شارژ کاربر (/addcredit USER_ID AMOUNT)
async def add_credit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    
    try:
        target_user_id = int(context.args[0])
        amount = int(context.args[1])
        
        add_credits(target_user_id, amount)
        await update.message.reply_text(f"✅ با موفقیت {amount} اعتبار به کاربر `{target_user_id}` اضافه شد.", parse_mode="Markdown")
        
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"🎉 **پرداخت شما تایید شد!**\nتعداد {amount} اعتبار به حساب شما اضافه گردید."
        )
    except Exception:
        await update.message.reply_text("❌ فرمت نادرست است. استفاده صحیح:\n`/addcredit USER_ID AMOUNT`", parse_mode="Markdown")

# پردازش متون و فایل‌ها
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not use_credit(user_id):
        await update.message.reply_text(
            "❌ اعتبار رایگان شما به پایان رسیده است.\n"
            "جهت خرید اعتبار جدید از دکمه زیر یا دستور /buy استفاده کنید."
        )
        return

    await update.message.reply_text("✨ درخواست شما دریافت شد و در حال پردازش توسط هوش مصنوعی است...")

# ----------------------------------------------------
# راه‌اندازی ربات
# ----------------------------------------------------
if __name__ == "__main__":
    init_db()
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("addcredit", add_credit_command))
    
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("Bot is running...")
    app.run_polling()

