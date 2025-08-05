import re
import psycopg2
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()
token = os.getenv("TOKEN")
db_url = os.getenv("DATABASE_URL")
allowed_chat_id = int(os.getenv("CHAT_ID"))

# Инициализация базы данных
conn = psycopg2.connect(db_url)
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
    cursor.execute(
        "INSERT INTO debts (from_user, to_user, amount) VALUES (%s, %s, %s)",
        (from_user, to_user, amount)
    )
    conn.commit()

# Очистка долгов
def clear_all_debts():
    cursor.execute("DELETE FROM debts")
    conn.commit()

# Получение всех долгов
def get_summary():
    # Получаем все долги
    cursor.execute("SELECT from_user, to_user, amount FROM debts")
    rows = cursor.fetchall()

    if not rows:
        return f"Все долги возвращены 🙌"

    balance = defaultdict(float)

    for from_user, to_user, amount in rows:
        # отнимаем у должника, прибавляем получателю
        balance[(from_user, to_user)] += amount

    # Считаем итог по каждому направлению, компенсируем взаимные долги
    net_debts = defaultdict(float)

    for (from_user, to_user), amount in balance.items():
        reverse = (to_user, from_user)
        if reverse in net_debts:
            if net_debts[reverse] > amount:
                net_debts[reverse] -= amount
            elif net_debts[reverse] < amount:
                net_debts[(from_user, to_user)] = amount - net_debts[reverse]
                del net_debts[reverse]
            else:
                del net_debts[reverse]
        else:
            net_debts[(from_user, to_user)] = amount

    if not net_debts:
        return f"Все долги возвращены 🙌"

    lines = [f"{f} должен {t}: {round(a, 2)}PLN" for (f, t), a in net_debts.items()]
    return f"\n".join(lines)

def get_chat_id(update: Update) -> int:
    return update.effective_chat.id

# Парсинг долга
def parse_debt(message):
    pattern = r"@(\w+)\s+должен\s+@(\w+)\s+(\d+(?:\.\d+)?)"
    match = re.search(pattern, message)
    if match:
        return match.group(1), match.group(2), float(match.group(3))
    return None

# Обработка сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = get_chat_id(update)

    if chat_id != allowed_chat_id:
        return

    if update.message is None:
        return

    text = update.message.text
    if "должен" in text:
        parsed = parse_debt(text)
        if parsed:
            from_user, to_user, amount = parsed
            add_debt(from_user, to_user, amount)
            await update.message.reply_text(f"Записано: @{from_user} должен @{to_user} {amount}PLN")
        else:
            await update.message.reply_text("Не удалось распознать долг. Формат: @user1 должен @user2 100")
    elif text.lower() == "обнулить долги":
        clear_all_debts()
        await update.message.reply_text("Все долги обнулены ✅")
    elif text.lower() == "долги":
        summary = get_summary()
        await update.message.reply_text(summary)
    elif text.lower() == "чатайди":
        await update.message.reply_text(f"Chat ID: `{chat_id}`")

# Запуск бота
def main():
    app = ApplicationBuilder().token(token).build()

    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        webhook_url="https://tg-debps.onrender.com"
    )

    print("Бот запущен...")

if __name__ == "__main__":
    main()
