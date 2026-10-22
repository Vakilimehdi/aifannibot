	mport os
import sqlite3
import logging
import requests
from datetime import datetime
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

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

ADMIN_CHAT_ID = 162256307
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

DB_NAME = "bot_database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            credits INTEGER DEFAULT 3,
            last_reset_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_today_string():
    return datetime.now().strftime("%Y-%m-%d")

def check_and_reset_daily_credits(user_id):
    if user_id == ADMIN_CHAT_ID:
        return

    today = get_today_string()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT credits, last_reset_date FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    
    if not row:
        cursor.execute('INSERT INTO users (user_id, credits, last_reset_date) VALUES (?, ?, ?)', (user_id, 3, today))
        conn.commit()
    else:
        credits, last_date = row
        if last_date != today:
            new_credits = max(credits, 3)
            cursor.execute('UPDATE users SET credits = ?, last_reset_date = ? WHERE user_id = ?', (new_credits, today, user_id))
            conn.commit()
            
    conn.close()

def get_credits(user_id):
    if user_id == ADMIN_CHAT_ID:
        return 999999

    check_and_reset_daily_credits(user_id)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT credits FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 3

def add_credits(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT credits FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if row:
        cursor.execute('UPDATE users SET credits = credits + ? WHERE user_id = ?', (amount, user_id))
    else:
        cursor.execute('INSERT INTO users (user_id, credits, last_reset_date) VALUES (?, ?, ?)', (user_id, 3 + amount, get_today_string()))
    conn.commit()
    conn.close()

def use_credit(user_id):
    if user_id == ADMIN_CHAT_ID:
        return True

    check_and_reset_daily_credits(user_id)
    credits = get_credits(user_id)
    
    if credits > 0:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET credits = credits - 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True
    return False

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    credits = get_credits(user_id)
    
    keyboard = [
        [InlineKeyboardButton("💳 خرید اعتبار (کارت به کارت)", callback_data="buy_credit")],
        [InlineKeyboardButton("📊 استعلام اعتبار باقی‌مانده", callback_data="check_credit")],
        [InlineKeyboardButton("💰 قیمت لحظه‌ای طلا و دلار", callback_data="get_prices")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    credit_display = "نامحدود (مدیریت)" if user_id == ADMIN_CHAT_ID else f"{credits} بار (روزانه)"
    
    welcome_text = (
        f"سلام {update.effective_user.first_name} عزیز! 👋\n"
        f"به ربات هوشمند **ای‌آی فنی** خوش آمدید.\n\n"
        f"🎁 **اعتبار امروز شما:** {credit_display}\n"
        f"*(هر روز ۳ اعتبار رایگان به حساب شما اضافه می‌شود)*\n\n"
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
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == "buy_credit":
        await query.message.reply_text(BANK_CARD_TEXT, parse_mode="Markdown")
    elif query.data == "check_credit":
        credits = get_credits(user_id)
        credit_display = "نامحدود (مدیریت)" if user_id == ADMIN_CHAT_ID else f"{credits} بار"
        await query.message.reply_text(f"📊 **اعتبار باقی‌مانده امروز شما:** {credit_display}")
    elif query.data == "get_prices":
        prices = fetch_financial_prices()
        await query.message.reply_text(prices, parse_mode="Markdown")

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prices = fetch_financial_prices()
    await update.message.reply_text(prices, parse_mode="Markdown")

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(BANK_CARD_TEXT, parse_mode="Markdown")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
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
    
    if not use_credit(user.id):
        await update.message.reply_text("❌ اعتبار رایگان امروز شما به پایان رسیده است.\nبرای استفاده بیشتر می‌توانید تا فردا صبر کنید یا جهت خرید اعتبار از دستور /buy استفاده کنید.")
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

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not use_credit(user_id):
        await update.message.reply_text(
            "❌ اعتبار رایگان امروز شما به پایان رسیده است.\n"
            "برای استفاده بیشتر می‌توانید تا فردا صبر کنید یا جهت خرید اعتبار از دکمه زیر یا دستور /buy استفاده کنید."
        )
        return

    await update.message.reply_text("✨ درخواست شما دریافت شد و در حال پردازش توسط هوش مصنوعی است...")

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

