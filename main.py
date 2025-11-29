import os
import sqlite3
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from dotenv import load_dotenv

# === НАСТРОЙКИ ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# === АДРЕСА СТУДИЙ ===
STUDIOS = {
    "1": "Алеутская улица, 2а",
    "2": "ТЦ «Берёзка», Русская улица, 16",
    "3": "Некрасовский рынок, Некрасовская улица, 69",
    "4": "ТЦ «Серп и Молот», улица Калинина, 275Б"
}

# === ЦЕНЫ НА ФОТО НА ДОКУМЕНТЫ ===
ID_PHOTO_SIZES = {
    "3×4 см (паспорт РФ)": 750,
    "35×45 мм (загранпаспорт)": 850,
    "4×6 см (виза, международные)": 850,
    "5×5 см (иные документы)": 850
}

# === ЦЕНЫ НА ФОТОПЕЧАТЬ ===
PHOTO_SIZES = {
    "10×15": 45,
    "13×18": 85,
    "15×21": 100,
    "20×30": 150
}

# === ЦЕНЫ НА ПЕЧАТЬ ДОКУМЕНТОВ ===
PRINT_PRICES = {
    "Чёрно-белая": 20,
    "Цветная": 100
}

# === СОСТОЯНИЯ FSM ===
class PhotoIDStates(StatesGroup):
    waiting_for_studio = State()
    waiting_for_size = State()
    waiting_for_phone = State()
    waiting_for_time = State()

class PhotoPrintStates(StatesGroup):
    waiting_for_studio = State()
    waiting_for_size = State()
    waiting_for_quantity = State()

class DocumentPrintStates(StatesGroup):
    waiting_for_studio = State()
    waiting_for_type = State()
    waiting_for_quantity = State()

# === ФУНКЦИИ МЕНЮ ===
def main_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="📸 Фото на документы")
    kb.button(text="🖨️ Фотопечать")
    kb.button(text="👕 Сувениры")
    kb.button(text="📄 Распечатка документов")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

def studio_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="1. Алеутская ул., 2а")
    kb.button(text="2. ТЦ Берёзка, Русская 16")
    kb.button(text="3. Некрасовский рынок, Некрасовская 69")
    kb.button(text="4. ТЦ Серп и Молот, Калинина 275Б")
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)

def id_photo_size_menu():
    kb = ReplyKeyboardBuilder()
    for size in ID_PHOTO_SIZES.keys():
        kb.button(text=size)
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)

def photo_size_menu():
    kb = ReplyKeyboardBuilder()
    for size in PHOTO_SIZES.keys():
        kb.button(text=size)
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

def print_type_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="Чёрно-белая")
    kb.button(text="Цветная")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

def save_order(user_id, username, service, details):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO orders (user_id, username, service, details) VALUES (?, ?, ?, ?)",
              (user_id, username, service, details))
    conn.commit()
    conn.close()

# === КОМАНДЫ ===
@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Здравствуйте! Это бот студии A1 во Владивостоке.\nВыберите услугу:",
        reply_markup=main_menu()
    )

# === ФОТО НА ДОКУМЕНТЫ С ВЫБОРОМ РАЗМЕРА ===
@router.message(F.text == "📸 Фото на документы")
async def photo_id_start(message: Message, state: FSMContext):
    await message.answer("Выберите студию:", reply_markup=studio_menu())
    await state.set_state(PhotoIDStates.waiting_for_studio)

@router.message(PhotoIDStates.waiting_for_studio)
async def process_studio_id(message: Message, state: FSMContext):
    text = message.text
    studio = None
    if text.startswith("1."): studio = STUDIOS["1"]
    elif text.startswith("2."): studio = STUDIOS["2"]
    elif text.startswith("3."): studio = STUDIOS["3"]
    elif text.startswith("4."): studio = STUDIOS["4"]
    else:
        await message.answer("Выберите студию из списка:", reply_markup=studio_menu())
        return
    await state.update_data(studio=studio)
    await message.answer("Выберите размер фото:", reply_markup=id_photo_size_menu())
    await state.set_state(PhotoIDStates.waiting_for_size)

@router.message(PhotoIDStates.waiting_for_size)
async def process_id_size(message: Message, state: FSMContext):
    if message.text not in ID_PHOTO_SIZES:
        await message.answer("Выберите размер из списка:", reply_markup=id_photo_size_menu())
        return
    await state.update_data(size=message.text)
    await message.answer("Укажите ваш номер телефона (для связи и чека):")
    await state.set_state(PhotoIDStates.waiting_for_phone)

@router.message(PhotoIDStates.waiting_for_phone)
async def process_phone_id(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("Укажите желаемую дату и время (например: 1 декабря, 10:00):")
    await state.set_state(PhotoIDStates.waiting_for_time)

@router.message(PhotoIDStates.waiting_for_time)
async def process_time_id(message: Message, state: FSMContext):
    data = await state.get_data()
    studio = data["studio"]
    size = data["size"]
    phone = data["phone"]
    time = message.text
    price = ID_PHOTO_SIZES[size]

    details = f"Студия: {studio}\nРазмер: {size}\nТелефон: {phone}\nВремя: {time}\nСумма: {price} ₽"
    save_order(message.from_user.id, message.from_user.username, "photo_id", details)

    await message.answer(
        f"✅ Ваша запись:\n"
        f"📍 Студия: {studio}\n"
        f"📐 Размер: {size}\n"
        f"⏰ Время: {time}\n"
        f"💰 К оплате: {price} ₽\n\n"
        f"💳 Оплатите через СБП на наш номер: **+7 (423) XXX-XX-XX**\n"
        f"После оплаты пришлите скриншот — мы подтвердим запись!"
    )
    await bot.send_message(
        ADMIN_ID,
        f"🆕 Запись на фото\n{details}"
    )
    await state.clear()
    await message.answer("Выберите другую услугу:", reply_markup=main_menu())

# === ФОТОПЕЧАТЬ (без изменений, но для полноты) ===
@router.message(F.text == "🖨️ Фотопечать")
async def photo_print_start(message: Message, state: FSMContext):
    await message.answer("Выберите студию:", reply_markup=studio_menu())
    await state.set_state(PhotoPrintStates.waiting_for_studio)

@router.message(PhotoPrintStates.waiting_for_studio)
async def process_studio_print(message: Message, state: FSMContext):
    text = message.text
    studio = None
    if text.startswith("1."): studio = STUDIOS["1"]
    elif text.startswith("2."): studio = STUDIOS["2"]
    elif text.startswith("3."): studio = STUDIOS["3"]
    elif text.startswith("4."): studio = STUDIOS["4"]
    else:
        await message.answer("Выберите студию:", reply_markup=studio_menu())
        return
    await state.update_data(studio=studio)
    await message.answer("Выберите размер фото:", reply_markup=photo_size_menu())
    await state.set_state(PhotoPrintStates.waiting_for_size)

@router.message(PhotoPrintStates.waiting_for_size)
async def process_size(message: Message, state: FSMContext):
    if message.text not in PHOTO_SIZES:
        await message.answer("Выберите размер:", reply_markup=photo_size_menu())
        return
    await state.update_data(size=message.text)
    await message.answer("Количество фото?")
    await state.set_state(PhotoPrintStates.waiting_for_quantity)

@router.message(PhotoPrintStates.waiting_for_quantity)
async def process_quantity(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите число:")
        return
    quantity = int(message.text)
    data = await state.get_data()
    studio = data["studio"]
    size = data["size"]
    total = PHOTO_SIZES[size] * quantity
    details = f"Студия: {studio}\nРазмер: {size}\nКол-во: {quantity}\nСумма: {total} ₽"
    save_order(message.from_user.id, message.from_user.username, "photo_print", details)
    await message.answer(f"✅ Итого: {total} ₽. Оплатите через СБП и пришлите скрин.")
    await bot.send_message(ADMIN_ID, f"🖨️ Фотопечать\n{details}")
    await state.clear()
    await message.answer("Выберите услугу:", reply_markup=main_menu())

# === РАСПЕЧАТКА ДОКУМЕНТОВ ===
@router.message(F.text == "📄 Распечатка документов")
async def doc_print_start(message: Message, state: FSMContext):
    await message.answer("Выберите студию:", reply_markup=studio_menu())
    await state.set_state(DocumentPrintStates.waiting_for_studio)

@router.message(DocumentPrintStates.waiting_for_studio)
async def process_studio_doc(message: Message, state: FSMContext):
    text = message.text
    studio = None
    if text.startswith("1."): studio = STUDIOS["1"]
    elif text.startswith("2."): studio = STUDIOS["2"]
    elif text.startswith("3."): studio = STUDIOS["3"]
    elif text.startswith("4."): studio = STUDIOS["4"]
    else:
        await message.answer("Выберите студию:", reply_markup=studio_menu())
        return
    await state.update_data(studio=studio)
    await message.answer("Тип печати?", reply_markup=print_type_menu())
    await state.set_state(DocumentPrintStates.waiting_for_type)

@router.message(DocumentPrintStates.waiting_for_type)
async def process_print_type(message: Message, state: FSMContext):
    if message.text not in PRINT_PRICES:
        await message.answer("Выберите тип:", reply_markup=print_type_menu())
        return
    await state.update_data(print_type=message.text)
    await message.answer("Количество листов?")
    await state.set_state(DocumentPrintStates.waiting_for_quantity)

@router.message(DocumentPrintStates.waiting_for_quantity)
async def process_doc_quantity(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите число листов:")
        return
    quantity = int(message.text)
    data = await state.get_data()
    studio = data["studio"]
    ptype = data["print_type"]
    total = PRINT_PRICES[ptype] * quantity
    details = f"Студия: {studio}\nТип: {ptype}\nЛистов: {quantity}\nСумма: {total} ₽"
    save_order(message.from_user.id, message.from_user.username, "document_print", details)
    await message.answer(f"✅ Итого: {total} ₽. Оплатите и пришлите скрин.")
    await bot.send_message(ADMIN_ID, f"📄 Распечатка\n{details}")
    await state.clear()
    await message.answer("Выберите услугу:", reply_markup=main_menu())

# === СУВЕНИРЫ ===
@router.message(F.text == "👕 Сувениры")
async def souvenirs(message: Message):
    await message.answer("Опишите заказ на сувениры (кружка, футболка и т.д.) и пришлите макет. Мы пришлём расчёт.")
    await bot.send_message(ADMIN_ID, f"👕 Сувениры от @{message.from_user.username}")

# === ПРИЁМ ФАЙЛОВ ===
@router.message(F.document | F.photo)
async def handle_files(message: Message):
    await message.answer("Файл получен! Ожидайте подтверждения.")
    await bot.send_message(ADMIN_ID, f"📥 Файл от @{message.from_user.username}")

# === ЗАПУСК ===
async def main():
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
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
