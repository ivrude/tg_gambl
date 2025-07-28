from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import User, BankCard
from bot.database import SessionLocal
from bot.config import ADMIN_IDS
import re
from sqlalchemy import select

from bot.services import game

router = Router()
class GameState(StatesGroup):
    waiting_for_guess = State()
    waiting_for_bet = State()

def setup_handlers(dp):
    dp.include_router(router)

@router.message(F.text.in_(['/start', '📋 Меню']))
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
    buttons = [
        [KeyboardButton(text="🎮 Ігри")],
        [KeyboardButton(text="💳 Депозит")]
    ]
    if msg.from_user.id in ADMIN_IDS:
        buttons.append([KeyboardButton(text="🛠 Адмін панель")])

    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

    await msg.answer("Вітаю в грі! Обери опцію:", reply_markup=keyboard)

@router.message(F.text.in_(["🎲 Більше / Менше", "🎲 Зіграти ще"]))
async def start_game(msg: Message, state: FSMContext):
    first_number = game.generate_number()  # Генеруємо перше число з game.py
    await state.update_data(first_number=first_number)
    await msg.answer(
        f"🎲 Перше число: <b>{first_number}</b>\n"
        "Виберіть варіант: менше, більше або рівно (відносно <b>другого числа</b>)"
    )
    await state.set_state(GameState.waiting_for_guess)


@router.message(GameState.waiting_for_guess)
async def choose_guess(msg: Message, state: FSMContext):
    guess = msg.text.lower()
    if guess not in ["менше", "більше", "рівно"]:
        await msg.answer("❌ Введіть лише: менше, більше або рівно")
        return
    await state.update_data(guess=guess)
    await msg.answer("💰 Введіть суму ставки:")
    await state.set_state(GameState.waiting_for_bet)


@router.message(GameState.waiting_for_bet)
async def enter_bet(msg: Message, state: FSMContext):
    try:
        bet = float(msg.text)
        if bet <= 0:
            raise ValueError
    except:
        await msg.answer("❌ Введіть коректну суму.")
        return

    data = await state.get_data()
    first_number = data["first_number"]
    guess = data["guess"]
    second_number = game.generate_number()  # Генеруємо друге число

    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == msg.from_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await msg.answer("❌ Користувач не знайдений.")
            return
        if user.balance < bet:
            await state.clear()  # Вийти з FSM, щоб не чекати введення суми
            await msg.answer("❌ Недостатньо коштів на балансі, для поповнення /deposit.")
            return

        # Викликаємо функцію evaluate_guess з game.py
        win, reward, f1, f2 = game.evaluate_guess(guess, bet, first_number, second_number)
        if win:
            user.balance += reward
            result_msg = f"🎉 Ви виграли {reward:.2f} грн!"
        else:
            user.balance -= bet
            result_msg = f"😢 Ви програли {bet:.2f} грн."

        await session.commit()
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎲 Зіграти ще")],
            [KeyboardButton(text="📋 Меню")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    await msg.answer(
        f"🎲 Перше число: <b>{f1}</b>\n"
        f"🎯 Друге число: <b>{f2}</b>\n"
        f"Ваша ставка: <b>{guess}</b>\n\n"
        f"{result_msg}",
        reply_markup = keyboard,
    )
    await state.clear()

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

@router.message(F.text.in_(["💳 Депозит", "/deposit"]))
async def deposit_handler(msg: Message):
    async with SessionLocal() as session:
        result = await session.execute(select(BankCard).limit(1))
        card = result.scalar_one_or_none()
        card_number = card.card_number if card else "❌ Картку не встановлено"

    await msg.answer(
        f"💳 Для поповнення балансу:\n"
        f"1. Здійсніть переказ на карту: <b>{card_number}</b>\n"
        f"2. Надішліть фото квитанції у чат."
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


@router.message(F.text.startswith("/set_card"))
async def set_bank_card(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        return await msg.answer("⛔️ У вас немає прав на цю дію.")

    try:
        _, card_number = msg.text.split(maxsplit=1)
    except ValueError:
        return await msg.answer("❗ Формат: /set_card 4444 1111 2222 3333")

    async with SessionLocal() as session:
        result = await session.execute(select(BankCard).limit(1))
        card = result.scalar_one_or_none()

        if card:
            card.card_number = card_number
        else:
            card = BankCard(card_number=card_number)
            session.add(card)

        await session.commit()

    await msg.answer(f"✅ Банківську картку оновлено:\n<code>{card_number}</code>")

@router.message(F.text.startswith("/find_user"))
async def find_user_handler(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        return await msg.answer("⛔️ У вас немає прав на цю дію.")

    try:
        _, telegram_id_str = msg.text.split(maxsplit=1)
        telegram_id = int(telegram_id_str)
    except (ValueError, IndexError):
        return await msg.answer("❗ Формат: /find_user 2233445566")

    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user:
            await msg.answer(
                f"👤 Інформація про користувача:\n"
                f"<b>Telegram ID:</b> <code>{user.telegram_id}</code>\n"
                f"<b>Баланс:</b> <code>{user.balance} грн</code>",
                parse_mode="HTML"
            )
        else:
            await msg.answer("❌ Користувача з таким ID не знайдено.")

@router.message(F.text.startswith("/change_user"))
async def change_user_balance(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        return await msg.answer("⛔️ У вас немає прав на цю дію.")

    try:
        _, user_id_str, change_str = msg.text.split(maxsplit=2)
        telegram_id = int(user_id_str)

        if not (change_str.startswith('+') or change_str.startswith('-')):
            raise ValueError("Немає + або - перед сумою")

        amount = float(change_str)
    except Exception:
        return await msg.answer("❗ Формат: /change_user telegram_id +/-сума\n"
                                "Приклад: /change_user 123456789 +100")

    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return await msg.answer("❌ Користувача з таким ID не знайдено.")

        user.balance += amount
        await session.commit()

        action = "додано" if amount > 0 else "віднято"
        await msg.answer(
            f"✅ Баланс користувача <code>{user.telegram_id}</code> оновлено.\n"
            f"Було {action} <b>{abs(amount)} грн</b>\n"
            f"📟 Новий баланс: <code>{user.balance:.2f} грн</code>",
            parse_mode="HTML"
        )

@router.message(F.text.in_(["🎮 Ігри","/games"]))
async def games_menu(msg: Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎲 Більше / Менше")],
            [KeyboardButton(text="🪙 Монетка")],
            [KeyboardButton(text="🎰 Казино")],
            [KeyboardButton(text="📋 Меню")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await msg.answer("🎮 Обери гру:", reply_markup=keyboard)

@router.message(F.text == "🪙 Монетка")
async def coin_handler(msg: Message):
    await msg.answer("Гра в монетку на етапі розробки.")

@router.message(F.text == "🎰 Казино")
async def casino_handler(msg: Message):
    await msg.answer("Гра в казино поки що на етапі розробки.")

@router.message(F.text.in_(["🛠 Адмін панель", "/admin"]))
async def admin_panel_handler(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        await msg.answer("🚫 У вас немає доступу до адмін панелі.")
        return

    buttons = [
        [KeyboardButton(text="🔍 Знайти користувача")],
        [KeyboardButton(text="💰 Змінити баланс користувача")],
        [KeyboardButton(text="💳 Змінити картку")],
        [KeyboardButton(text="📋 Меню")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

    await msg.answer("🛠 Адмін панель. Оберіть дію:", reply_markup=keyboard)

@router.message(F.text == "🔍 Знайти користувача")
async def casino_handler(msg: Message):
    await msg.answer("Введіть: /find_user 2233445566")

@router.message(F.text == "💰 Змінити баланс користувача")
async def casino_handler(msg: Message):
    await msg.answer("Введіть: /change_user 123456789 +100")

@router.message(F.text == "💳 Змінити картку")
async def casino_handler(msg: Message):
    await msg.answer("Введіть: /set_card 4444 1111 2222 3333")