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

# === ЦЕНЫ И АДРЕСА ===
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

PHOTO_SIZES = {
    "10×15": 35,
    "13×18": 50,
    "15×21": 70,
    "20×30": 120
}

MATTE_SURCHARGE = 10

PRINT_PRICES = {
    "Чёрно-белая": 5,
    "Цветная": 15
}

# === СОСТОЯНИЯ ===
class PhotoIDStates(StatesGroup):
    waiting_for_studio = State()
    waiting_for_size = State()
    waiting_for_phone = State()
    waiting_for_time = State()

class PhotoPrintStates(StatesGroup):
    waiting_for_studio = State()
    waiting_for_size = State()
    waiting_for_quantity = State()
    waiting_for_paper_type = State()
    waiting_for_photos = State()

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

def cancel_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="❌ Отмена")
    return kb.as_markup(resize_keyboard=True, one_time_keyboard=False)

def studio_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="1. Алеутская ул., 2а")
    kb.button(text="2. ТЦ Берёзка, Русская 16")
    kb.button(text="3. Некрасовский рынок, Некрасовская 69")
    kb.button(text="4. ТЦ Серп и Молот, Калинина 275Б")
    kb.button(text="❌ Отмена")
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)

def id_photo_size_menu():
    kb = ReplyKeyboardBuilder()
    for size in ID_PHOTO_SIZES.keys():
        kb.button(text=size)
    kb.button(text="❌ Отмена")
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)

def photo_size_menu():
    kb = ReplyKeyboardBuilder()
    for size in PHOTO_SIZES.keys():
        kb.button(text=size)
    kb.button(text="❌ Отмена")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

def paper_type_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="Глянцевая")
    kb.button(text="Матовая")
    kb.button(text="❌ Отмена")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

def print_type_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="Чёрно-белая")
    kb.button(text="Цветная")
    kb.button(text="❌ Отмена")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
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

def save_photo_file(order_id, file_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS photos (order_id INTEGER, file_id TEXT)")
    c.execute("INSERT INTO photos (order_id, file_id) VALUES (?, ?)", (order_id, file_id))
    conn.commit()
    conn.close()

# === ГЛОБАЛЬНЫЙ ХЭНДЛЕР ОТМЕНЫ ===
@router.message(F.text == "❌ Отмена")
async def cancel_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Вы уже в главном меню.", reply_markup=main_menu())
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    
    if order_id:
        delete_order(order_id)
    
    await state.clear()
    await message.answer("Заказ отменён. Вы в главном меню.", reply_markup=main_menu())

# === ОСНОВНЫЕ ХЭНДЛЕРЫ ===
@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Здравствуйте! Это бот студии A1 во Владивостоке.\nВыберите услугу:",
        reply_markup=main_menu()
    )

# === ФОТО НА ДОКУМЕНТЫ ===
@router.message(F.text == "📸 Фото на документы")
async def photo_id_start(message: Message, state: FSMContext):
    await message.answer("Выберите студию:", reply_markup=studio_menu())
    await state.set_state(PhotoIDStates.waiting_for_studio)

@router.message(PhotoIDStates.waiting_for_studio)
async def process_studio_id(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        return  # уже обработано глобальным хендлером
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
    await message.answer("Выберите размер:", reply_markup=id_photo_size_menu())
    await state.set_state(PhotoIDStates.waiting_for_size)

@router.message(PhotoIDStates.waiting_for_size)
async def process_id_size(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        return
    if message.text not in ID_PHOTO_SIZES:
        await message.answer("Выберите размер:", reply_markup=id_photo_size_menu())
        return
    await state.update_data(size=message.text)
    await message.answer("Ваш телефон:", reply_markup=cancel_menu())
    await state.set_state(PhotoIDStates.waiting_for_phone)

@router.message(PhotoIDStates.waiting_for_phone)
async def process_phone_id(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        return
    await state.update_data(phone=message.text)
    await message.answer("Дата и время (например: 1 декабря, 10:00):", reply_markup=cancel_menu())
    await state.set_state(PhotoIDStates.waiting_for_time)

@router.message(PhotoIDStates.waiting_for_time)
async def process_time_id(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        return
    data = await state.get_data()
    studio = data["studio"]
    size = data["size"]
    phone = data["phone"]
    time = message.text
    price = ID_PHOTO_SIZES[size]
    details = f"Студия: {studio}\nРазмер: {size}\nТелефон: {phone}\nВремя: {time}\nСумма: {price} ₽"
    save_order(message.from_user.id, message.from_user.username, "photo_id", details)
    await message.answer(
        f"✅ Запись в студию:\n📍 {studio}\n💰 К оплате: {price} ₽\n\n"
        f"Оплатите через СБП и пришлите скриншот подтверждения."
    )
    await bot.send_message(ADMIN_ID, f"🆕 Запись на фото\n{details}")
    await state.clear()
    await message.answer("✅ Ваш заказ принят в работу!", reply_markup=main_menu())

# === ФОТОПЕЧАТЬ ===
@router.message(F.text == "🖨️ Фотопечать")
async def photo_print_start(message: Message, state: FSMContext):
    await message.answer("Выберите студию:", reply_markup=studio_menu())
    await state.set_state(PhotoPrintStates.waiting_for_studio)

@router.message(PhotoPrintStates.waiting_for_studio)
async def process_studio_print(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        return
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
    if message.text == "❌ Отмена":
        return
    if message.text not in PHOTO_SIZES:
        await message.answer("Выберите размер:", reply_markup=photo_size_menu())
        return
    await state.update_data(size=message.text)
    await message.answer("Количество фото?", reply_markup=cancel_menu())
    await state.set_state(PhotoPrintStates.waiting_for_quantity)

@router.message(PhotoPrintStates.waiting_for_quantity)
async def process_quantity(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        return
    if not message.text.isdigit():
        await message.answer("Введите число:", reply_markup=cancel_menu())
        return
    quantity = int(message.text)
    await state.update_data(quantity=quantity)
    await message.answer("Выберите тип бумаги:", reply_markup=paper_type_job())
    await state.set_state(PhotoPrintStates.waiting_for_paper_type)

@router.message(PhotoPrintStates.waiting_for_paper_type)
async def process_paper_type(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        return
    if message.text not in ["Глянцевая", "Матовая"]:
        await message.answer("Выберите тип бумаги:", reply_markup=paper_type_menu())
        return

    data = await state.get_data()
    studio = data["studio"]
    size = data["size"]
    quantity = data["quantity"]
    paper_type = message.text

    base_price = PHOTO_SIZES[size]
    total = (base_price + (MATTE_SURCHARGE if paper_type == "Матовая" else 0)) * quantity
    details = f"Студия: {studio}\nРазмер: {size}\nКол-во: {quantity}\nБумага: {paper_type}\nСумма: {total} ₽"
    order_id = save_order(message.from_user.id, message.from_user.username, "photo_print", details)

    await state.update_data(order_id=order_id, expected_photos=quantity)
    await message.answer(
        f"✅ Ваш заказ:\n"
        f"📍 {studio}\n📏 {size}, {quantity} шт.\n📄 {paper_type}\n💰 Итого: {total} ₽\n\n"
        f"1. Оплатите через СБП.\n"
        f"2. Отправьте {quantity} фото для печати."
    )
    await bot.send_message(ADMIN_ID, f"🖨️ Новый заказ на фотопечать\n{details}")
    await state.set_state(PhotoPrintStates.waiting_for_photos)

@router.message(PhotoPrintStates.waiting_for_photos, F.photo)
async def handle_print_photos(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        return
    data = await state.get_data()
    order_id = data.get("order_id")
    expected = data.get("expected_photos", 1)

    if not order_id:
        await message.answer("Ошибка. Пожалуйста, начните заказ заново.")
        return

    file_id = message.photo[-1].file_id
    save_photo_file(order_id, file_id)

    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM photos WHERE order_id = ?", (order_id,))
    received = c.fetchone()[0]
    conn.close()

    if received < expected:
        await message.answer(f"🖼️ Фото получено ({received}/{expected}). Отправьте ещё {expected - received}.", reply_markup=cancel_menu())
    else:
        await message.answer("✅ Все фото получены! Заказ передан в работу.")
        await bot.send_message(ADMIN_ID, f"🖼️ Все фото для заказа ID {order_id} получены от @{message.from_user.username}")
        await state.clear()
        await message.answer("✅ Ваш заказ принят в работу!", reply_markup=main_menu())

@router.message(PhotoPrintStates.waiting_for_photos)
async def not_photo(message: Message):
    if message.text == "❌ Отмена":
        return
    await message.answer("Пожалуйста, отправьте фото (изображение).", reply_markup=cancel_menu())

# === РАСПЕЧАТКА ДОКУМЕНТОВ ===
@router.message(F.text == "📄 Распечатка документов")
async def doc_print_start(message: Message, state: FSMContext):
    await message.answer("Выберите студию:", reply_markup=studio_menu())
    await state.set_state(DocumentPrintStates.waiting_for_studio)

@router.message(DocumentPrintStates.waiting_for_studio)
async def process_studio_doc(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        return
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
    if message.text == "❌ Отмена":
        return
    if message.text not in PRINT_PRICES:
        await message.answer("Выберите тип:", reply_markup=print_type_menu())
        return
    await state.update_data(print_type=message.text)
    await message.answer("Количество листов?", reply_markup=cancel_menu())
    await state.set_state(DocumentPrintStates.waiting_for_quantity)

@router.message(DocumentPrintStates.waiting_for_quantity)
async def process_doc_quantity(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        return
    if not message.text.isdigit():
        await message.answer("Введите число листов:", reply_markup=cancel_menu())
        return
    quantity = int(message.text)
    data = await state.get_data()
    studio = data["studio"]
    ptype = data["print_type"]
    total = PRINT_PRICES[ptype] * quantity
    details = f"Студия: {studio}\nТип: {ptype}\nЛистов: {quantity}\nСумма: {total} ₽"
    save_order(message.from_user.id, message.from_user.username, "document_print", details)
    await message.answer(f"✅ Итого: {total} ₽. Оплатите и пришлите скрин. Затем отправьте файлы.")
    await bot.send_message(ADMIN_ID, f"📄 Распечатка документов\n{details}")
    await state.clear()
    await message.answer("✅ Ваш заказ принят в работу!", reply_markup=main_menu())

# === СУВЕНИРЫ ===
@router.message(F.text == "👕 Сувениры")
async def souvenirs(message: Message):
    await message.answer("Опишите заказ и пришлите макет. Мы пришлём расчёт.")
    await bot.send_message(ADMIN_ID, f"👕 Запрос на сувениры от @{message.from_user.username}")
    await message.answer("✅ Ваш заказ принят в работу!", reply_markup=main_menu())

# === ПРИЁМ ФАЙЛОВ ===
@router.message(F.document)
async def handle_documents(message: Message):
    await message.answer("📄 Файл получен! Ждите подтверждения.")

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
    c.execute('''CREATE此案
We've gone as far as we can with this conversation. If you'd like to continue, please start a new chat!
