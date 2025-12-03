import os
import json
from datetime import datetime
from flask import Flask, request
from openpyxl import Workbook
from telebot import TeleBot, types

# ========================== НАСТРОЙКИ ==========================
TOKEN = os.getenv("BOT_TOKEN")
if TOKEN is None:
    raise ValueError("BOT_TOKEN не задан! Проверь Environment Variables")

bot = TeleBot(TOKEN)
app = Flask(__name__)

DATA_FILE = "data.json"
HISTORY_FILE = "history.txt"

user_state = {}  # ожидание суммы


# ========================== ФАЙЛЫ ==========================
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"USD": 0, "UAH": 0}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def add_to_history(text):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")


# ========================== КНОПКИ ==========================
def main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        types.KeyboardButton("➕ USD"), types.KeyboardButton("➖ USD"),
        types.KeyboardButton("➕ UAH"), types.KeyboardButton("➖ UAH")
    )
    kb.add(types.KeyboardButton("Баланс"), types.KeyboardButton("История"))
    kb.add(types.KeyboardButton("Экспорт в Excel"))
    return kb


# ========================== СТАРТ ==========================
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "Добро пожаловать!\nВыбери действие:",
        reply_markup=main_keyboard()
    )


# ========================== ОЖИДАНИЕ СУММЫ ==========================
def ask_amount(message, operation, currency):
    user_state[message.chat.id] = (operation, currency)
    bot.send_message(message.chat.id, f"Введи сумму для '{operation} {currency}':")


@bot.message_handler(func=lambda m: m.text in ["➕ USD", "➖ USD", "➕ UAH", "➖ UAH"])
def handle_buttons(message):
    txt = message.text
    currency = "USD" if "USD" in txt else "UAH"
    operation = "+" if "➕" in txt else "-"
    ask_amount(message, operation, currency)


@bot.message_handler(func=lambda m: m.chat.id in user_state)
def process_amount(message):
    try:
        amount = float(message.text)
    except:
        bot.send_message(message.chat.id, "Введите число.")
        return

    operation, currency = user_state.pop(message.chat.id)
    data = load_data()

    if operation == "+":
        data[currency] += amount
    else:
        data[currency] -= amount

    save_data(data)

    log = f"{datetime.now()} — {operation}{amount} {currency} → USD={data['USD']} UAH={data['UAH']}"
    add_to_history(log)

    bot.send_message(
        message.chat.id,
        f"Операция выполнена: {operation}{amount} {currency}\n\n"
        f"Баланс:\nUSD: {data['USD']}\nUAH: {data['UAH']}",
        reply_markup=main_keyboard()
    )


# ========================== БАЛАНС ==========================
@bot.message_handler(func=lambda m: m.text == "Баланс")
def balance(message):
    data = load_data()
    bot.send_message(message.chat.id, f"USD: {data['USD']}\nUAH: {data['UAH']}")


# ========================== ИСТОРИЯ ==========================
@bot.message_handler(func=lambda m: m.text == "История")
def history(message):
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            text = f.read() or "История пустая."
    except:
        text = "История пустая."

    bot.send_message(message.chat.id, text[:3500])


# ========================== ЭКСЕЛЬ ==========================
@bot.message_handler(func=lambda m: m.text == "Экспорт в Excel")
def excel(message):
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except:
        bot.send_message(message.chat.id, "История пустая.")
        return

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "History"
    sheet.append(["Дата", "Операция", "USD", "UAH"])

    for line in lines:
        try:
            parts = line.split(" — ")
            date = parts[0]
            op = parts[1].split(" → ")[0]
            balances = parts[1].split(" → ")[1]
            usd = float(balances.split(" ")[0].split("=")[1])
            uah = float(balances.split(" ")[1].split("=")[1])
            sheet.append([date, op, usd, uah])
        except:
            continue

    filename = "history.xlsx"
    workbook.save(filename)

    with open(filename, "rb") as f:
        bot.send_document(message.chat.id, f)

    bot.send_message(message.chat.id, "Готово!")


# ========================== WEBHOOK ==========================
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200


@app.route("/setwebhook", methods=["GET"])
def set_webhook():
    url = os.getenv("RENDER_EXTERNAL_URL")
    full_url = f"{url}/{TOKEN}"
    bot.remove_webhook()
    bot.set_webhook(full_url)
    return f"Webhook установлен: {full_url}", 200


@app.route("/")
def index():
    return "Бот работает!"


# ========================== ЗАПУСК СЕРВЕРА ==========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))




