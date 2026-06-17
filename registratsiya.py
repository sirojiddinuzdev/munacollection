from telegram import Update
from telegram.ext import ContextTypes
import config
from database import db
from funksiyalar import get_register_keyboard, get_main_keyboard, start_checkout

async def is_authorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if user_id in config.ADMIN_IDS:
        return True
    if db.is_user_registered(user_id):
        return True
    return False

async def request_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Xush kelibsiz! Bot xizmatlaridan foydalanish uchun telefon raqamingiz orqali ro'yxatdan o'tish tugmasini bosing:",
        reply_markup=get_register_keyboard()
    )

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    contact = update.message.contact
    username = update.effective_user.username or ""
    phone_number = contact.phone_number

    # Normalize phone number (make sure it starts with + if needed)
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number

    db.add_user(user_id, username, phone_number)
    await update.message.reply_text(
        "Muvaffaqiyatli ro'yxatdan o'tdingiz! 🎉",
        reply_markup=get_main_keyboard(user_id)
    )

    # Check if there is a pending purchase
    pending_buy_id = context.user_data.pop('pending_buy_product_id', None)
    if pending_buy_id:
        await start_checkout(update, context, pending_buy_id)
