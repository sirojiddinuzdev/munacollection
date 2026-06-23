import logging
from telegram import Update
from telegram.ext import ContextTypes
import config
from database import db
from funksiyalar import get_main_keyboard, start_checkout
from registratsiya import is_authorized, request_registration

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if this is a group chat
    if update.effective_chat.type != "private":
        bot_info = await context.bot.get_me()
        await update.message.reply_text(
            f"Iltimos, botdan foydalanish uchun shaxsiy chatga o'ting: t.me/{bot_info.username}"
        )
        return

    user_id = update.effective_user.id
    args = context.args

    # Check if this is a deep link for a purchase
    if args and args[0].startswith("buy_"):
        product_id = int(args[0].split("_")[1])
        if not await is_authorized(update, context):
            # Save pending purchase and ask for registration
            context.user_data['pending_buy_product_id'] = product_id
            await request_registration(update, context)
            return
        else:
            # Start checkout directly
            await start_checkout(update, context, product_id)
            return

    # Normal start
    if db.is_admin(user_id):
        await update.message.reply_text(
            "Xush kelibsiz, Admin! Quyidagi menyudan foydalanishingiz mumkin:",
            reply_markup=get_main_keyboard(user_id)
        )
    elif db.is_user_registered(user_id):
        await update.message.reply_text(
            "Xush kelibsiz! Quyidagi menyudan foydalanishingiz mumkin:",
            reply_markup=get_main_keyboard(user_id)
        )
    else:
        await request_registration(update, context)

async def test_btn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Test tugmasi 🔘", callback_data="test_callback")]
    ])
    await update.message.reply_text("Test tugmasini bosing:", reply_markup=keyboard)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
        
    await update.message.reply_text(
        f"🙋‍♂️ *Admin bog'lanish ma'lumotlari:*\n\n"
        f"Savollar yoki takliflar yuzasidan admin bilan quyidagi havola orqali bog'lanishingiz mumkin:\n"
        f"Username: {config.ADMIN_USERNAME}",
        parse_mode="Markdown"
    )
