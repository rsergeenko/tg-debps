import re
import sqlite3
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("TOKEN")

# Инициализация базы данных
conn = sqlite3.connect("debts.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS debts (
    from_user TEXT,
    to_user TEXT,
    amount REAL
)
""")
conn.commit()

# Добавление долга
def add_debt(from_user, to_user, amount):
    cursor.execute("INSERT INTO debts (from_user, to_user, amount) VALUES (?, ?, ?)", (from_user, to_user, amount))
    conn.commit()

# Очистка долгов
def clear_all_debts():
    cursor.execute("DELETE FROM debts")
    conn.commit()

# Получение всех долгов
def get_summary():
    cursor.execute("SELECT from_user, to_user, SUM(amount) FROM debts GROUP BY from_user, to_user")
    rows = cursor.fetchall()
    if not rows:
        return "Нет долгов 🙌"
    return "\n".join([f"{f} должен {t}: {a}₽" for f, t, a in rows])

# Парсинг долга
def parse_debt(message):
    pattern = r"@(\w+)\s+должен\s+@(\w+)\s+(\d+(?:\.\d+)?)"
    match = re.search(pattern, message)
    if match:
        return match.group(1), match.group(2), float(match.group(3))
    return None

# Обработка сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return

    text = update.message.text
    if "должен" in text:
        parsed = parse_debt(text)
        if parsed:
            from_user, to_user, amount = parsed
            add_debt(from_user, to_user, amount)
            await update.message.reply_text(f"Записано: @{from_user} должен @{to_user} {amount}₽")
        else:
            await update.message.reply_text("Не удалось распознать долг. Формат: @user1 должен @user2 100")
    elif text.lower() == "все долги вернули":
        clear_all_debts()
        await update.message.reply_text("Все долги обнулены ✅")
    elif text.lower() == "долги":
        summary = get_summary()
        await update.message.reply_text(summary)

# Запуск бота
def main():
    app = ApplicationBuilder().token(token).build()

    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
