	mport os
import sqlite3
import logging
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
# تنظیمات لاگین و اطلاعات مدیریت
# ----------------------------------------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# اطلاعات اختصاصی مدیریت و کارت بانکی
ADMIN_CHAT_ID = 162256307  # آیدی عددی شما[span_0](start_span)[span_0](end_span)
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
# هندلرهای ربات
# ----------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    credits = get_credits(user_id)
    
    keyboard = [
        [InlineKeyboardButton("💳 خرید اعتبار (کارت به کارت)", callback_data="buy_credit")],
        [InlineKeyboardButton("📊 استعلام اعتبار باقی‌مانده", callback_data="check_credit")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"سلام {update.effective_user.first_name} عزیز! 👋\n"
        f"به ربات هوشمند **ای‌آی فنی** خوش آمدید.\n\n"
        f"🎁 **اعتبار هدیه شما:** {credits} بار استفاده رایگان\n\n"
        f"🛠 **امکانات ربات:**\n"
        f"▫️ حل فرمول‌ها و سوالات اکسل\n"
        f"▫️ تبدیل صوت و ویس به متن\n"
        f"▫️ تغییر حجم و سایز عکس‌ها\n\n"
        f"سوال یا فایل خود را ارسال کنید!"
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
        await query.message.reply_text(f"📊 **اعتبار باقی‌مانده شما:** {credits} بار استفاده")

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(BANK_CARD_TEXT, parse_mode="Markdown")

# دریافت و پردازش عکس رسید و ارسال به مدیر
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # اگر کاربر عکس فرستاد، ابتدا به عنوان رسید پردازش می‌کنیم
    photo_file = await update.message.photo[-1].get_file()
    
    caption_for_admin = (
        f"📥 **رسید پرداخت جدید**\n\n"
        f"👤 **نام کاربر:** {user.first_name}\n"
        f"🆔 **آیدی:** @{user.username if user.username else 'ندارد'}\n"
        f"🔢 **آیدی عددی:** `{user.id}`\n\n"
        f"⚙️ **دستور شارژ حساب:**\n"
        f"`/addcredit {user.id} 10`"
    )
    
    # ارسال به تلگرام شما
    await context.bot.send_photo(
        chat_id=ADMIN_CHAT_ID,
        photo=photo_file.file_id,
        caption=caption_for_admin,
        parse_mode="Markdown"
    )
    
    await update.message.reply_text(
        "✅ رسید شما با موفقیت دریافت شد.\n"
        "پس از بررسی و تایید مدیریت، حساب شما شارژ خواهد شد."
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
        
        # اطلاع‌رسانی به کاربر
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"🎉 **پرداخت شما تایید شد!**\nتعداد {amount} اعتبار به حساب شما اضافه گردید."
        )
    except Exception as e:
        await update.message.reply_text(f"❌ فرمت نادرست است. استفاده صحیح:\n`/addcredit USER_ID AMOUNT`", parse_mode="Markdown")

# پردازش پیام‌های متنی (اکسل و خدمات)
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not use_credit(user_id):
        await update.message.reply_text(
            "❌ اعتبار رایگان شما به پایان رسیده است.\n"
            "جهت خرید اعتبار جدید از دستور /buy استفاده کنید."
        )
        return

    # پاسخ آزمایشی برای اکسل/متن
    await update.message.reply_text("✨ درخواست شما دریافت شد و در حال پردازش توسط هوش مصنوعی است...")

# ----------------------------------------------------
# اجرا و راه‌اندازی ربات
# ----------------------------------------------------
if __name__ == "__main__":
    init_db()
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # ثبت دستورات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy_command))
    app.add_handler(CommandHandler("addcredit", add_credit_command))
    
    # ثبت هندلر دکمه‌ها و پیام‌ها
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("Bot is running...")
    app.run_polling()

