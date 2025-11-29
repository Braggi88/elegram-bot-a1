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

# === ЗАГРУЗКА НАСТРОЕК ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# === КОНСТАНТЫ ===
STUDIOS = {
    "1": "Алеутская улица, 2а",
    "2": "ТЦ «Берёзка», Русская улица, 16",
    "3": "Некрасовский рынок, Некрасовская улица, 69",
    "4": "ТЦ «Серп и Молот», улица Калинина, 275Б"
}

ID_PHOTO_SIZES = {
    "3×4 см (паспорт РФ)": 350,
    "35×45 мм (загранпаспорт)": 400,
    "4×6 см (виза, международные)": 450,
    "5×5 см (иные документы)": 450
}

PHOTO_SIZES = {"10×15": 35, "13×18": 50, "15×21": 70, "20×30": 120}
MATTE_SURCHARGE = 10
PRINT_PRICES = {"Чёрно-белая": 5, "Цветная": 15}

# === СОСТОЯНИЯ ===
class PhotoIDStates(StatesGroup):
    studio = State()
    size = State()
    phone = State()
    time = State()

class PhotoPrintStates(StatesGroup):
    studio = State()
    size = State()
    quantity = State()
    paper_type = State()
    waiting_for_photos = State()

class DocumentPrintStates(StatesGroup):
    studio = State()
    print_type = State()
    quantity = State()

# === УНИВЕРСАЛЬНЫЕ ФУНКЦИИ МЕНЮ ===
def make_keyboard(buttons, with_cancel=True):
    kb = ReplyKeyboardBuilder()
    if isinstance(buttons[0], list):
        for row in buttons:
            for btn in row:
                kb.button(text=btn)
            kb.adjust(*[1]*len(row))  # гибкая настройка
    else:
        for btn in buttons:
            kb.button(text=btn)
        kb.adjust(2)
    if with_cancel:
        kb.button(text="❌ Отмена")
    return kb.as_markup(resize_keyboard=True, one_time_keyboard=False)

def main_menu():
    return make_keyboard([
        ["📸 Фото на документы", "🖨️ Фотопечать"],
        ["👕 Сувениры", "📄 Распечатка документов"]
    ], with_cancel=False)

def studio_menu():
    return make_keyboard([
        "1. Алеутская ул., 2а",
        "2. ТЦ Берёзка, Русская 16",
        "3. Некрасовский рынок, Некрасовская 69",
        "4. ТЦ Серп и Молот, Калинина 275Б"
    ])

def id_photo_size_menu():
    return make_keyboard(list(ID_PHOTO_SIZES.keys()))

def photo_size_menu():
    return make_keyboard(list(PHOTO_SIZES.keys()))

def paper_type_menu():
    return make_keyboard(["Глянцевая", "Матовая"])

def print_type_menu():
    return make_keyboard(["Чёрно-белая", "Цветная"])

# === РАБОТА С БД ===
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
    c.execute('''CREATE TABLE IF NOT EXISTS photos (
        order_id INTEGER,
        file_id TEXT
    )''')
    conn.commit()
    conn.close()

def save_order(user_id, username, service, details):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO orders (user_id, username, service, details) VALUES (?, ?, ?, ?)",
              (user_id, username, service, details))
    order_id = c.lastrowid
    conn.commit()
    conn.close()
    return order_id

def delete_order(order_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    c.execute("DELETE FROM photos WHERE order_id = ?", (order_id,))
    conn.commit()
    conn.close()

def save_photo(order_id, file_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO photos (order_id, file_id) VALUES (?, ?)", (order_id, file_id))
    conn.commit()
    conn.close()

def count_photos(order_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM photos WHERE order_id = ?", (order_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

# === ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОТМЕНЫ ===
@router.message(F.text == "❌ Отмена")
async def handle_cancel(message: Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        await message.answer("Вы в главном меню.", reply_markup=main_menu())
        return

    data = await state.get_data()
    order_id = data.get('order_id')
    if order_id:
        delete_order(order_id)

    await state.clear()
    await message.answer("❌ Заказ отменён. Вы в главном меню.", reply_markup=main_menu())

# === КОМАНДА /start ===
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Здравствуйте! Это официальный бот студии **A1** во Владивостоке.\n\n"
        "Выберите услугу:",
        reply_markup=main_menu()
    )

# === ФОТО НА ДОКУМЕНТЫ ===
@router.message(F.text == "📸 Фото на документы")
async def start_photo_id(message: Message, state: FSMContext):
    await state.set_state(PhotoIDStates.studio)
    await message.answer("📍 Выберите студию:", reply_markup=studio_menu())

@router.message(PhotoIDStates.studio)
async def photo_id_studio(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": return
    for key, addr in STUDIOS.items():
        if message.text.startswith(f"{key}."):
            await state.update_data(studio=addr)
            await state.set_state(PhotoIDStates.size)
            await message.answer("📏 Выберите размер:", reply_markup=id_photo_size_menu())
            return
    await message.answer("❌ Пожалуйста, выберите студию из списка:", reply_markup=studio_menu())

@router.message(PhotoIDStates.size)
async def photo_id_size(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": return
    if message.text not in ID_PHOTO_SIZES:
        await message.answer("❌ Выберите размер из списка:", reply_markup=id_photo_size_menu())
        return
    await state.update_data(size=message.text)
    await state.set_state(PhotoIDStates.phone)
    await message.answer("📱 Введите ваш номер телефона (для связи и чека):")

@router.message(PhotoIDStates.phone)
async def photo_id_phone(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": return
    await state.update_data(phone=message.text)
    await state.set_state(PhotoIDStates.time)
    await message.answer("⏰ Укажите дату и время (пример: *1 декабря, 10:00*):")

@router.message(PhotoIDStates.time)
async def photo_id_time(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": return
    data = await state.get_data()
    studio, size, phone, time = data['studio'], data['size'], message.text, message.text
    price = ID_PHOTO_SIZES[size]
    details = f"Студия: {studio}\nРазмер: {size}\nТелефон: {data['phone']}\nВремя: {time}\nСумма: {price} ₽"
    
    order_id = save_order(message.from_user.id, message.from_user.username, "photo_id", details)
    
    await message.answer(
        f"✅ Запись подтверждена!\n📍 {studio}\n💰 К оплате: {price} ₽\n\n"
        "💳 Оплатите через СБП на наш номер. После оплаты пришлите скриншот."
    )
    await bot.send_message(ADMIN_ID, f"🆕 Фото на документы\n{details}")
    await state.clear()
    await message.answer("✅ Ваш заказ принят в работу!", reply_markup=main_menu())

# === ФОТОПЕЧАТЬ ===
@router.message(F.text == "🖨️ Фотопечать")
async def start_photo_print(message: Message, state: FSMContext):
    await state.set_state(PhotoPrintStates.studio)
    await message.answer("📍 Выберите студию:", reply_markup=studio_menu())

@router.message(PhotoPrintStates.studio)
async def print_studio(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": return
    for key, addr in STUDIOS.items():
        if message.text.startswith(f"{key}."):
            await state.update_data(studio=addr)
            await state.set_state(PhotoPrintStates.size)
            await message.answer("📏 Выберите размер:", reply_markup=photo_size_menu())
            return
    await message.answer("❌ Выберите студию:", reply_markup=studio_menu())

@router.message(PhotoPrintStates.size)
async def print_size(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": return
    if message.text not in PHOTO_SIZES:
        await message.answer("❌ Выберите размер:", reply_markup=photo_size_menu())
        return
    await state.update_data(size=message.text)
    await state.set_state(PhotoPrintStates.quantity)
    await message.answer("🔢 Сколько фото напечатать? (введите число)")

@router.message(PhotoPrintStates.quantity)
async def print_quantity(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": return
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer("❌ Введите корректное число (например: 5):")
        return
    await state.update_data(quantity=int(message.text))
    await state.set_state(PhotoPrintStates.paper_type)
    await message.answer("📄 Выберите тип бумаги:", reply_markup=paper_type_menu())

@router.message(PhotoPrintStates.paper_type)
async def print_paper_type(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": return
    if message.text not in ["Глянцевая", "Матовая"]:
        await message.answer("❌ Выберите тип бумаги:", reply_markup=paper_type_menu())
        return
    
    data = await state.get_data()
    studio = data['studio']
    size = data['size']
    qty = data['quantity']
    paper = message.text
    base = PHOTO_SIZES[size]
    total = (base + (MATTE_SURCHARGE if paper == "Матовая" else 0)) * qty
    
    details = f"Студия: {studio}\nРазмер: {size}\nКол-во: {qty}\nБумага: {paper}\nСумма: {total} ₽"
    order_id = save_order(message.from_user.id, message.from_user.username, "photo_print", details)
    await state.update_data(order_id=order_id)
    
    await message.answer(
        f"✅ Заказ сформирован!\n"
        f"📍 {studio} | {size} | {qty} шт.\n"
        f"📄 {paper}\n"
        f"💰 Итого: {total} ₽\n\n"
        "1️⃣ Оплатите через СБП.\n"
        "2️⃣ Отправьте фото для печати (можно по одному)."
    )
    await bot.send_message(ADMIN_ID, f"🖨️ Фотопечать\n{details}")
    await state.set_state(PhotoPrintStates.waiting_for_photos)

@router.message(PhotoPrintStates.waiting_for_photos, F.photo)
async def receive_photo(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": return
    data = await state.get_data()
    order_id = data.get('order_id')
    if not order_id:
        await message.answer("❌ Ошибка. Начните заказ заново.", reply_markup=main_menu())
        await state.clear()
        return

    save_photo(order_id, message.photo[-1].file_id)
    received = count_photos(order_id)
    expected = data['quantity']

    if received < expected:
        await message.answer(f"🖼️ Получено {received}/{expected}. Отправьте ещё {expected - received}.")
    else:
        await message.answer("✅ Все фото получены! Заказ в работе.")
        await bot.send_message(ADMIN_ID, f"🖼️ Заказ ID {order_id} готов к печати от @{message.from_user.username}")
        await state.clear()
        await message.answer("✅ Ваш заказ принят в работу!", reply_markup=main_menu())

@router.message(PhotoPrintStates.waiting_for_photos)
async def not_photo_in_print(message: Message):
    if message.text == "❌ Отмена": return
    await message.answer("❌ Пожалуйста, отправьте фото (изображение).")

# === РАСПЕЧАТКА ДОКУМЕНТОВ ===
@router.message(F.text == "📄 Распечатка документов")
async def start_doc_print(message: Message, state: FSMContext):
    await state.set_state(DocumentPrintStates.studio)
    await message.answer("📍 Выберите студию:", reply_markup=studio_menu())

@router.message(DocumentPrintStates.studio)
async def doc_studio(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": return
    for key, addr in STUDIOS.items():
        if message.text.startswith(f"{key}."):
            await state.update_data(studio=addr)
            await state.set_state(DocumentPrintStates.print_type)
            await message.answer("🖨️ Выберите тип печати:", reply_markup=print_type_menu())
            return
    await message.answer("❌ Выберите студию:", reply_markup=studio_menu())

@router.message(DocumentPrintStates.print_type)
async def doc_type(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": return
    if message.text not in PRINT_PRICES:
        await message.answer("❌ Выберите тип печати:", reply_markup=print_type_menu())
        return
    await state.update_data(print_type=message.text)
    await state.set_state(DocumentPrintStates.quantity)
    await message.answer("📄 Сколько листов распечатать? (введите число)")

@router.message(DocumentPrintStates.quantity)
async def doc_quantity(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": return
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer("❌ Введите корректное число листов:")
        return
    qty = int(message.text)
    data = await state.get_data()
    studio = data['studio']
    ptype = data['print_type']
    total = PRINT_PRICES[ptype] * qty
    details = f"Студия: {studio}\nТип: {ptype}\nЛистов: {qty}\nСумма: {total} ₽"
    
    save_order(message.from_user.id, message.from_user.username, "document_print", details)
    await message.answer(f"✅ Итого: {total} ₽.\nОплатите через СБП и пришлите файлы для печати.")
    await bot.send_message(ADMIN_ID, f"📄 Распечатка\n{details}")
    await state.clear()
    await message.answer("✅ Ваш заказ принят в работу!", reply_markup=main_menu())

# === СУВЕНИРЫ ===
@router.message(F.text == "👕 Сувениры")
async def souvenirs(message: Message):
    await message.answer(
        "🎨 Опишите, что хотите заказать:\n"
        "- Кружка, футболка, фото на керамике и т.д.\n"
        "- Пришлите макет (если есть).\n\n"
        "Мы пришлём расчёт в ближайшее время!"
    )
    await bot.send_message(ADMIN_ID, f"👕 Сувениры от @{message.from_user.username}")
    await message.answer("✅ Ваш запрос принят в работу!", reply_markup=main_menu())

# === ФАЙЛЫ (документы, макеты) ===
@router.message(F.document)
async def handle_docs(message: Message):
    await message.answer("📎 Файл получен! Обрабатываем...")

# === ЗАПУСК ===
async def main():
    init_db()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
