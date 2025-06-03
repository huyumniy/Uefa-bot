from flask import Flask, jsonify, request
import asyncio
import threading
import subprocess
from aiogram import Bot, Dispatcher, executor, types
from waitress import serve
import sys

# Initialize the Bot instance
bot = Bot(token='7256914379:AAFSDgHNuCZy8JAx1Wxu_-WLjf_fniHnfUs')

dp = Dispatcher(bot)

app = Flask(__name__)

status = True

@app.route('/match', methods=['POST'])
def send_match():
    if status:
        data = request.json
        asyncio.run(send_to_group_channel(data))
    return ''

# Create a new book
@app.route('/book', methods=['POST'])
def create_book():
    if request.json:
        match_number = request.json['match_number']
        total_price = request.json['total_price']
        unit_price = request.json['unit_price']
        category = request.json['category']
        username = request.json['username']
        password = request.json['password']
        ads = request.json['ads']
        formatted_data = f'<b>Матч:</b> <i>{match_number}</i>\n<b>Кількість квитків та категорія:</b> <i>{category}</i>\n<b>Ціна за квиток:</b> <i>{unit_price}</i>\n<b>Ціна за всі квитки:</b> <i>{total_price}</i>\n<b>username:</b> <i>{username}</i>\n<b>password:</b> <i>{password}</i>\n<b>ads:</b> <i>{ads}</i>'
        asyncio.run(send_to_group_channel(formatted_data))
    return ''

async def send_to_group_channel(data):
    # Replace 'GROUP_CHANNEL_ID' with the actual ID of your group channel
    await bot.send_message(chat_id='-4228000254', text=data, parse_mode="html")


@dp.message_handler(commands=['start'])
async def start(message: types.Message):    
    global status
    status = True
    await bot.send_message(chat_id=message.chat.id, text='Повідомлення про наявність квитків та матчів увімкнені.', parse_mode="HTML")


@dp.message_handler(commands=['stop'])
async def start(message: types.Message):    
    global status
    status = False
    await bot.send_message(chat_id=message.chat.id, text='Повідомлення про наявність квитків та матчів призупинені.', parse_mode="HTML")


if __name__ == '__main__':
    is_win = "win32" if sys.platform == "win32" else None
    if not is_win: subprocess.Popen(['gunicorn', '--workers=1', '--bind=0.0.0.0:8000', 'server:app'])
    else: subprocess.Popen(['waitress-serve', '--listen=0.0.0.0:8000', 'server:app'])

    # Start the Telegram bot
    executor.start_polling(dp, skip_updates=True)


# -4228000254