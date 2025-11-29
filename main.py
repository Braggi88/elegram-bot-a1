import os
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from dotenv import load_dotenv

# === ЗАГРУЗКА НАСТРОЕК ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

# === СОСТОЯНИЯ ДЛЯ ФОТО НА ДОКУМЕНТЫ ===
class PhotoIDStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_time = State()

# === КНОПКИ МЕНЮ ===
def main_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="📸 Фото на документы")
    kb.button(text="🖨️ Фотопечать")
    kb.button(text="👕 Сувениры")
    kb.button(text="📄 Распечатка документов")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

# === КОМАНДЫ ===
@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Здравствуйте! Это официальный бот студии A1 во Владивостоке.\n\n"
        "Выберите услугу:",
        reply_markup=main_menu()
    )

@router.message(F.text == "📸 Фото на документы")
async def photo_id_start(message: Message, state: FSMContext):
    await message.answer("Пожалуйста, укажите ваш номер телефона (для связи и чека):")
    await state.set_state(PhotoIDStates.waiting_for_phone)

@router.message(PhotoIDStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("Укажите желаемую дату и время (например: 1 декабря, 10:00):")
    await state.set_state(PhotoIDStates.waiting_for_time)

@router.message(PhotoIDStates.waiting_for_time)
async def process_time(message: Message, state: FSMContext):
    user_data = await state.get_data()
    phone = user_data["phone"]
    time = message.text

    # Сохраняем в базу
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO orders (user_id, username, service, details) VALUES (?, ?, ?, ?)",
              (message.from_user.id, message.from_user.username, "photo_id", f"Телефон: {phone}, Время: {time}"))
    conn.commit()
    conn.close()

    # Инструкция по оплате
    await message.answer(
        "✅ Ваша запись принята!\n\n"
        "💳 Чтобы оплатить 350 ₽ через СБП:\n"
        "1. Откройте ваш банк (Сбер, Тинькофф и др.)\n"
        "2. Перейдите в «Переводы» → «По номеру телефона»\n"
        "3. Введите наш номер: **+7 (984) 150-73-80**\n"
        "4. Укажите сумму: **350 ₽**\n\n"
        "После оплаты пришлите скриншот — мы подтвердим запись!"
    )

    # Уведомление админу
    await bot.send_message(
        ADMIN_ID,
        f"🆕 НОВАЯ ЗАПИСЬ!\n\n"
        f"Услуга: Фото на документы\n"
        f"Клиент: @{message.from_user.username} (ID: {message.from_user.id})\n"
        f"Данные: {phone}\n"
        f"Время: {time}"
    )
    await state.clear()

# === ДРУГИЕ УСЛУГИ (заготовки) ===
@router.message(F.text.in_({"🖨️ Фотопечать", "👕 Сувениры", "📄 Распечатка документов"}))
async def other_services(message: Message):
    service_name = {
        "🖨️ Фотопечать": "Фотопечать",
        "👕 Сувениры": "Сувенирная продукция",
        "📄 Распечатка документов": "Распечатка документов"
    }[message.text]

    await message.answer(
        f"Вы выбрали: {service_name}.\n\n"
        "Пожалуйста, опишите ваш заказ (размер, количество, пожелания) и прикрепите файлы (фото, PDF).\n\n"
        "После получения мы пришлём расчёт и инструкцию по оплате."
    )

@router.message(F.document | F.photo)
async def handle_files(message: Message):
    await message.answer("Файл получен! Ожидайте расчёт и инструкцию по оплате.")
    await bot.send_message(
        ADMIN_ID,
        f"📥 Новый файл от @{message.from_user.username} (ID: {message.from_user.id})"
    )

# === ЗАПУСК ===
async def main():
    init_db()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
