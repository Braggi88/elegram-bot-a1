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

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# === СТУДИИ И АДМИНЫ ===
STUDIOS = {
    "1": "Алеутская улица, 2а",
    "2": "ТЦ «Берёзка», Русская улица, 16",
    "3": "Некрасовский рынок, Некрасовская улица, 69",
    "4": "ТЦ «Серп и Молот», улица Калинина, 275Б"
}

ADMINS = {
    "Алеутская улица, 2а": 111111111,
    "ТЦ «Берёзка», Русская улица, 16": 222222222,
    "Некрасовский рынок, Некрасовская улица, 69": 333333333,
    "ТЦ «Серп и Молот», улица Калинина, 275Б": 444444444
}

# === 🔄 СПИСОК ВАРИАНТОВ ОПЛАТЫ: НОМЕР + БАНК ===
SBP_OPTIONS = [
    {"number": "+7 (914) 111-11-11", "bank": "СберБанк"},
    {"number": "+7 (914) 111-11-11", "bank": "Тинькофф"},
    {"number": "+7 (924) 222-22-22", "bank": "ВТБ"},
    {"number": "+7 (924) 222-22-22", "bank": "Альфа-Банк"},
    {"number": "+7 (909) 333-33-33", "bank": "Райффайзен"},
    {"number": "+7 (987) 444-44-44", "bank": "Газпромбанк"},
]

# === ЦЕНЫ ===
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
# ... (остаются без изменений: PhotoIDStates, PhotoPrintStates и т.д.)

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

class SouvenirStates(StatesGroup):
    type = State()
    quantity = State()
    description = State()
    waiting_for_file = State()

# === МЕНЮ ===
# ... (все функции make_keyboard, main_menu и т.д. — без изменений)

def make_keyboard(buttons, with_cancel=True):
    kb = ReplyKeyboardBuilder()
    if isinstance(buttons[0], list):
        for row in buttons:
            for btn in row:
                kb.button(text=btn)
    else:
        for btn in buttons:
            kb.button(text=btn)
        kb.adjust(2)
    if with_cancel:
        kb.button(text="❌ Отмена")
    return kb.as_markup(resize_keyboard=True)

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

def souvenir_type_menu():
    return make_keyboard(["👕 Футболка", "☕ Кружка", "🖼️ Фото на керамике", "✏️ Другое"])

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
    c.execute('''CREATE TABLE IF NOT EXISTS photos (
        order_id INTEGER,
        file_id TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('last_sbp_index', '-1')")
    conn.commit()
    conn.close()

def get_next_sbp_option():
    """Возвращает следующую комбинацию {number, bank} по кругу."""
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = 'last_sbp_index'")
    index = int(c.fetchone()[0])
    next_index = (index + 1) % len(SBP_OPTIONS)
    c.execute("UPDATE settings SET value = ? WHERE key = 'last_sbp_index'", (str(next_index),))
    conn.commit()
    conn.close()
    return SBP_OPTIONS[next_index]

def save_order(user_id, username, service, details):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO orders (user_id, username, service, details) VALUES (?, ?, ?, ?)",
              (user_id, username, service, details))
    order_id = c.lastrowid()
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

# === УВЕДОМЛЕНИЕ АДМИНА ===
def get_admin_id(studio):
    return ADMINS.get(studio)

async def notify_admin(studio, text):
    admin_id = get_admin_id(studio)
    if admin_id:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            print(f"Ошибка отправки админу {admin_id}: {e}")

# === ОТМЕНА ===
@router.message(F.text == "❌ Отмена")
async def handle_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Заказ отменён. Вы в главном меню.", reply_markup=main_menu())

# === /start ===
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("👋 Выберите услугу:", reply_markup=main_menu())

# === ГЕНЕРАЦИЯ ИНСТРУКЦИИ С БАНКОМ ===
def generate_payment_instruction(sbp_option, amount=None):
    number = sbp_option["number"]
    bank = sbp_option["bank"]
    text = f"💳 Оплатите через СБП:\n📱 **{number}**\n🏦 **{bank}**"
    if amount:
        text += f"\n💰 Сумма: **{amount} ₽**"
    text += "\n\nПосле оплаты пришлите скриншот."
    return text

# === ПРИМЕР: ФОТО НА ДОКУМЕНТЫ ===
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
    await message.answer("❌ Выберите студию:", reply_markup=studio_menu())

@router.message(PhotoIDStates.size)
async def photo_id_size(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": return
    if message.text not in ID_PHOTO_SIZES:
        await message.answer("❌ Выберите размер:", reply_markup=id_photo_size_menu())
        return
    await state.update_data(size=message.text)
    await state.set_state(PhotoIDStates.phone)
    await message.answer("📱 Ваш телефон:")

@router.message(PhotoIDStates.phone)
async def photo_id_phone(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": return
    await state.update_data(phone=message.text)
    await state.set_state(PhotoIDStates.time)
    await message.answer("⏰ Дата и время:")

@router.message(PhotoIDStates.time)
async def photo_id_time(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": return
    data = await state.get_data()
    studio = data['studio']
    size = data['size']
    phone = data['phone']
    time = message.text
    price = ID_PHOTO_SIZES[size]
    
    # 🔄 Получаем следующую комбинацию (номер + банк)
    sbp_option = get_next_sbp_option()
    
    details = (
        f"Студия: {studio}\nРазмер: {size}\nТелефон: {phone}\nВремя: {time}\n"
        f"Сумма: {price} ₽\nНомер: {sbp_option['number']}\nБанк: {sbp_option['bank']}"
    )
    save_order(message.from_user.id, message.from_user.username, "photo_id", details)

    await message.answer(
        f"✅ Запись подтверждена!\n📍 {studio}\n\n"
        f"{generate_payment_instruction(sbp_option, price)}"
    )
    await notify_admin(studio, f"🆕 Фото на документы\n{details}")
    await state.clear()
    await message.answer("✅ Заказ в работе!", reply_markup=main_menu())

# === ОСТАЛЬНЫЕ УСЛУГИ (фотопечать, документы, сувениры) ===
# Аналогично: в каждом финальном шаге замените:
#
#   sbp_number = get_next_sbp_number()
#
# на:
#
#   sbp_option = get_next_sbp_option()
#
# и используйте `generate_payment_instruction(sbp_option, total)`
#
# (полный код всех хендлеров можно расширить по аналогии)

# === ЗАПУСК ===
async def main():
    init_db()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
