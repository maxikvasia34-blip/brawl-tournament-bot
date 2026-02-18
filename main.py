import os
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_PATH = "bot.db"


# ---------- DATABASE ----------

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        nickname TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()


# ---------- MENUS ----------

def main_menu():
    keyboard = [
        [InlineKeyboardButton("✅ Записаться", callback_data="join")],
        [InlineKeyboardButton("🎟 Мой статус", callback_data="status")],
    ]
    return InlineKeyboardMarkup(keyboard)


def price_menu():
    keyboard = [
        [InlineKeyboardButton("15 грн", callback_data="price_15"),
         InlineKeyboardButton("20 грн", callback_data="price_20")],
        [InlineKeyboardButton("30 грн", callback_data="price_30"),
         InlineKeyboardButton("50 грн", callback_data="price_50")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ---------- HANDLERS ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Добро пожаловать в турнир по Brawl Stars 🔥",
        reply_markup=main_menu()
    )


async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "join":
        context.user_data["awaiting_nick"] = True
        await query.edit_message_text("Напиши свой ник в игре:")

    elif query.data.startswith("price_"):
        amount = int(query.data.split("_")[1])

        conn = db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO entries (user_id, amount, created_at) VALUES (?, ?, ?)",
            (query.from_user.id, amount, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

        await query.edit_message_text(
            f"💳 Переведи {amount} грн на карту Sens Bank.\n"
            f"После оплаты отправь скрин сюда."
        )

    elif query.data == "status":
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT status FROM entries WHERE user_id=? ORDER BY id DESC LIMIT 1",
                    (query.from_user.id,))
        result = cur.fetchone()
        conn.close()

        if result:
            await query.edit_message_text(f"Твой статус: {result['status']}")
        else:
            await query.edit_message_text("Ты ещё не записан.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_nick"):
        context.user_data["awaiting_nick"] = False

        conn = db()
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO users (user_id, nickname) VALUES (?, ?)",
                    (update.message.from_user.id, update.message.text))
        conn.commit()
        conn.close()

        await update.message.reply_text("Выбери сумму участия:", reply_markup=price_menu())


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE entries SET status='pending_confirmation' WHERE user_id=?",
                (user_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text("Скрин получен. Ожидай подтверждения ✅")

    if ADMIN_ID:
        await context.bot.send_photo(
            ADMIN_ID,
            photo=update.message.photo[-1].file_id,
            caption=f"Новая оплата от {user_id}"
        )


# ---------- ADMIN ----------

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    user_id = int(context.args[0])

    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE entries SET status='paid' WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text("Подтверждено ✅")
    await context.bot.send_message(user_id, "Твоя оплата подтверждена 🔥")


# ---------- MAIN ----------

def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("confirm", confirm))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    app.run_polling()


if __name__ == "__main__":
    main()
      
