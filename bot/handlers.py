from aiogram import Router, F
from aiogram.types import Message
from bot.models import User
from bot.database import SessionLocal
from bot.config import ADMIN_IDS
import re
from sqlalchemy import select
import random

router = Router()

def setup_handlers(dp):
    dp.include_router(router)

@router.message(F.text == "/start")
async def start_handler(msg: Message):
    async with SessionLocal() as session:
        result = await session.execute(
            User.__table__.select().where(User.telegram_id == msg.from_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            user = User(telegram_id=msg.from_user.id, balance=100)
            session.add(user)
            await session.commit()
        await msg.answer("Вітаю в грі! Ваш баланс: 100 грн\nНапишіть /play щоб зіграти.")

@router.message(F.text == "/balance")
async def balance_handler(msg: Message):
    telegram_id = msg.from_user.id

    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user:
            await msg.answer(f"Ваш баланс: {user.balance:.2f} грн")
        else:
            await msg.answer("❌ Вас не знайдено в базі. Зареєструйтесь спочатку.")

@router.message(F.text == "/deposit")
async def deposit_handler(msg: Message):
    await msg.answer(
        "💳 Для поповнення балансу:\n"
        "1. Здійсніть переказ на карту: <b>5375 xxxx xxxx xxxx</b>\n"
        "2. Надішліть фото квитанції у чат."
    )

# --- Отримання квитанції ---
@router.message(F.photo)
async def handle_receipt_photo(msg: Message):
    photo = msg.photo[-1].file_id
    caption = f"🧾 Нова квитанція!\nTelegram ID: <code>{msg.from_user.id}</code>"

    for admin_id in ADMIN_IDS:
        await msg.bot.send_photo(chat_id=admin_id, photo=photo, caption=caption)

    await msg.answer("✅ Квитанцію надіслано адміну на перевірку.")

# --- Адмін поповнює баланс користувачу, відповідаючи на фото ---
@router.message(F.text.startswith("/approve"), F.from_user.id.in_(ADMIN_IDS))
async def approve_deposit(msg: Message):
    if not msg.reply_to_message or not msg.reply_to_message.caption:
        await msg.answer("⚠️ Ви маєте відповісти на повідомлення з квитанцією.")
        return

    caption = msg.reply_to_message.caption

    # Шукаємо ID з або без <code> тегів
    match = re.search(r'Telegram ID: ?(?:<code>)?(\d+)(?:</code>)?', caption)
    if not match:
        await msg.answer(f"❌ Не вдалося знайти Telegram ID у підписі.\nОтриманий caption:\n\n{caption}")
        return

    telegram_id = int(match.group(1))

    try:
        parts = msg.text.split()
        amount = float(parts[1])
    except:
        await msg.answer("❌ Формат: /approve <сума>")
        return

    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.balance += amount
            await session.commit()
            await msg.answer(f"✅ Баланс користувача {telegram_id} поповнено на {amount} грн.")
        else:
            await msg.answer("❌ Користувача не знайдено.")