import os
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import sqlite3

# === НАСТРОЙКИ ===
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
scheduler = AsyncIOScheduler()

# === БАЗА ДАННЫХ ===
def init_db():
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        service TEXT,
        details TEXT,
        appointment_time TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

# === FSM СОСТОЯНИЯ ===
class PhotoIDStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_time = State()

# === КНОПКИ ===
def main_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="📸 Фото на документы")
    kb.button(text="🖨️ Фотопечать")
    kb.button(text="👕 Сувениры")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

# === КОМАНДЫ ===
@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот студии A1 во Владивостоке.\n\nВыберите услугу:",
        reply_markup=main_menu()
    )

@router.message(F.text == "📸 Фото на документы")
async def photo_id_start(message: Message, state: FSMContext):
    await message.answer("Введите ваш номер телефона (для связи и чека):")
    await state.set_state(PhotoIDStates.waiting_for_phone)

@router.message(PhotoIDStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("Укажите желаемую дату и время (например: 1 декабря 10:00):")
    await state.set_state(PhotoIDStates.waiting_for_time)

@router.message(PhotoIDStates.waiting_for_time)
async def process_time(message: Message, state: FSMContext):
    user_data = await state.get_data()
    phone = user_data["phone"]
    time_str = message.text

    # Сохраняем заказ
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('''INSERT INTO orders (user_id, username, service, details, appointment_time)
                 VALUES (?, ?, ?, ?, ?)''',
              (message.from_user.id, message.from_user.username, "photo_id", phone, time_str))
    conn.commit()
    order_id = c.lastrowid
    conn.close()

    # Инструкция по оплате
    await message.answer(
        "✅ Запись принята!\n\n"
        "💳 Чтобы оплатить 350 ₽ через СБП:\n"
        "1. Откройте ваш банк (Сбер, Тинькофф и др.)\n"
        "2. Перейдите в «Переводы» → «По номеру телефона»\n"
        "3. Введите наш номер: **+7 (423) XXX-XX-XX**\n"
        "4. Укажите сумму: **350 ₽**\n\n"
        "После оплаты пришлите скриншот — мы подтвердим запись!"
    )

    # Уведомляем админа
    await bot.send_message(
        ADMIN_ID,
        f"🆕 Новая запись!\n"
        f"Клиент: @{message.from_user.username} (ID: {message.from_user.id})\n"
        f"Телефон: {phone}\n"
        f"Время: {time_str}\n"
        f"Заказ ID: {order_id}"
    )

    await state.clear()

# === ЗАПУСК ===
async def main():
    init_db()
    dp.include_router(router)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
