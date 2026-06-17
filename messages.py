import logging
from telegram import Update
from telegram.ext import ContextTypes
import config
from registratsiya import is_authorized, request_registration, handle_contact
from funksiyalar import get_main_keyboard
from admin_handlers import handle_admin_message
from user_handlers import handle_user_message

logger = logging.getLogger(__name__)

# Text & Media Message Router
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if this is a group chat
    if update.effective_chat.type != "private":
        return

    user_id = update.effective_user.id
    text = update.message.text
    state = context.user_data.get('state')
    logger.info(f"Message received from user_id={user_id}: state={state}, text={text}")

    # Force registration check first for normal users
    if not await is_authorized(update, context):
        if update.message.contact:
            await handle_contact(update, context)
        else:
            await request_registration(update, context)
        return

    # Check for "Bekor qilish ❌" button
    if text == "Bekor qilish ❌":
        context.user_data['state'] = None
        # Clean any draft states
        context.user_data.pop('new_ad_photo', None)
        context.user_data.pop('new_ad_photos', None)
        context.user_data.pop('new_ad_location', None)
        context.user_data.pop('new_ad_delivery', None)
        context.user_data.pop('new_ad_price', None)
        context.user_data.pop('new_ad_description', None)
        context.user_data.pop('buy_product_id', None)
        context.user_data.pop('edit_product_id', None)
        context.user_data.pop('edit_field', None)
        context.user_data.pop('edit_photos', None)
        
        # Clean catalog messages if any
        prev_msg_ids = context.user_data.get('catalog_msg_ids', [])
        if prev_msg_ids:
            for mid in prev_msg_ids:
                try:
                    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=mid)
                except Exception as e:
                    logger.error(f"Could not delete message {mid}: {e}")
            context.user_data['catalog_msg_ids'] = []
        
        await update.message.reply_text(
            "Amal bekor qilindi.",
            reply_markup=get_main_keyboard(user_id)
        )
        return

    # Route to admin handlers if user is admin
    if user_id in config.ADMIN_IDS:
        handled = await handle_admin_message(update, context)
        if handled:
            return

    # Fallback to user handlers
    await handle_user_message(update, context)

async def log_all_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info(f"RAW UPDATE: {update.to_dict()}")
    except Exception as e:
        logger.error(f"Error logging raw update: {e}")
