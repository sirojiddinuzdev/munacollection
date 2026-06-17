import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InputMediaPhoto
)
from telegram.ext import ContextTypes
import config
from database import db

logger = logging.getLogger(__name__)

# Keyboards
def get_main_keyboard(user_id):
    if user_id in config.ADMIN_IDS:
        return ReplyKeyboardMarkup([
            [KeyboardButton("Elon Joylashtirish ➕"), KeyboardButton("Bozor 🛍")],
            [KeyboardButton("Buyurtmalar 📝"), KeyboardButton("Karta Raqami 💳")],
            [KeyboardButton("Yetkazilmagan buyurtmalar ⏳"), KeyboardButton("Yetkazilgan buyurtmalar ✅")],
            [KeyboardButton("Statistika 📊")]
        ], resize_keyboard=True)
    else:
        return ReplyKeyboardMarkup([
            [KeyboardButton("Bozor 🛍")],
            [KeyboardButton("Aloqa 📞")]
        ], resize_keyboard=True)

def get_register_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Ro'yxatdan o'tish 📱", request_contact=True)]
    ], resize_keyboard=True, one_time_keyboard=True)

def get_cancel_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Bekor qilish ❌")]
    ], resize_keyboard=True)

# Checkout Flow (Buy product)
async def start_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    user_id = update.effective_user.id
    product = db.get_product(product_id)

    if not product:
        if update.message:
            await update.message.reply_text("Kechirasiz, ushbu mahsulot topilmadi yoki o'chirilgan.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("Kechirasiz, ushbu mahsulot topilmadi yoki o'chirilgan.")
        return

    # Delete previous catalog messages to keep chat clean
    prev_msg_ids = context.user_data.get('catalog_msg_ids', [])
    if prev_msg_ids:
        for mid in prev_msg_ids:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=mid)
            except Exception as e:
                logger.error(f"Could not delete message {mid}: {e}")
        context.user_data['catalog_msg_ids'] = []

    card_number = db.get_setting('card_number', config.DEFAULT_CARD)
    card_holder = db.get_setting('card_holder', config.DEFAULT_CARD_HOLDER)

    context.user_data['state'] = 'BUY_RECEIPT'
    context.user_data['buy_product_id'] = product_id

    text = (
        f"🛒 *Mahsulot sotib olish:*\n\n"
        f"📍 Kelish joyi: {product['location']}\n"
        f"💵 Narxi: {product['price']}\n"
        f"📝 Izoh: {product['description']}\n\n"
        f"💳 *To'lov ma'lumotlari:*\n"
        f"Karta raqami: `{card_number}`\n"
        f"Karta egasi: *{card_holder}*\n\n"
        f"Iltimos, to'lovni amalga oshiring va to'lov *chekini (skrinshot yoki rasm)* shu yerga yuboring."
    )

    if update.message:
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard()
        )
    elif update.callback_query:
        await update.callback_query.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard()
        )

# Catalog / Bozor flow
async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE, index=0, photo_index=0):
    products = db.get_active_products()
    if not products:
        msg = "Hozircha bozorda hech qanday e'lon yo'q."
        if update.message:
            await update.message.reply_text(msg)
        elif update.callback_query:
            await update.callback_query.answer("Bozor bo'sh")
            await update.callback_query.message.reply_text(msg)
        return

    if index < 0:
        index = 0
    elif index >= len(products):
        index = len(products) - 1

    product = products[index]
    total = len(products)
    user_id = update.effective_user.id

    # Delete previous catalog messages to keep chat clean
    prev_msg_ids = context.user_data.get('catalog_msg_ids', [])
    if prev_msg_ids:
        for mid in prev_msg_ids:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=mid)
            except Exception as e:
                logger.error(f"Could not delete message {mid}: {e}")
        context.user_data['catalog_msg_ids'] = []

    # Handle multiple photos
    photo_list = [pid.strip() for pid in product['photo_id'].split(",") if pid.strip()]

    # Construct description text
    caption = (
        f"🛍 *Bozor mahsuloti ({index+1}/{total})*\n\n"
        f"📍 Kelish joyi: {product['location']}\n"
        f"⏱ Kelish muddati: {product['delivery_time']}\n"
        f"💵 Narxi: {product['price']}\n"
        f"📝 Izoh: {product['description']}"
    )

    # Inline Keyboards
    keyboard = []
    
    # 1. Buy button
    keyboard.append([InlineKeyboardButton("Sotib olish 💳", callback_data=f"buy_prod_{product['id']}")])
    
    # 2. Product navigation buttons
    nav_row = []
    if index > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Oldingi Mahsulot", callback_data=f"cat_idx_{index-1}"))
    nav_row.append(InlineKeyboardButton(f"{index+1}/{total}", callback_data="noop"))
    if index < total - 1:
        nav_row.append(InlineKeyboardButton("Keyingi Mahsulot ➡️", callback_data=f"cat_idx_{index+1}"))
    keyboard.append(nav_row)

    # 3. Admin controls
    if user_id in config.ADMIN_IDS:
        keyboard.append([
            InlineKeyboardButton("Tahrirlash ✏️", callback_data=f"admin_edit_{product['id']}"),
            InlineKeyboardButton("O'chirish ❌", callback_data=f"admin_del_{product['id']}")
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send the products
    if not photo_list:
        try:
            msg = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=caption,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            context.user_data['catalog_msg_ids'] = [msg.message_id]
        except Exception as e:
            logger.error(f"Catalog text-only displaying error: {e}")
    elif len(photo_list) == 1:
        try:
            msg = await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=photo_list[0],
                caption=caption,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            context.user_data['catalog_msg_ids'] = [msg.message_id]
        except Exception as e:
            logger.error(f"Catalog single photo displaying error: {e}")
    else:
        # Send all photos as a media group, and then description as a text message with the keyboard
        try:
            media = [InputMediaPhoto(media=pid) for pid in photo_list]
            media_msgs = await context.bot.send_media_group(
                chat_id=update.effective_chat.id,
                media=media
            )
            msg_ids = [m.message_id for m in media_msgs]
            
            desc_msg = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=caption,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            msg_ids.append(desc_msg.message_id)
            context.user_data['catalog_msg_ids'] = msg_ids
        except Exception as e:
            logger.error(f"Catalog media group displaying error: {e}")

# Helper to update/repost an ad in the group after edit
async def update_group_post_after_edit(context: ContextTypes.DEFAULT_TYPE, product_id: int):
    product = db.get_product(product_id)
    if not product:
        return
        
    # Delete old group messages if they exist
    if product['group_message_id']:
        old_msg_ids = str(product['group_message_id']).split(",")
        for msg_id in old_msg_ids:
            try:
                await context.bot.delete_message(chat_id=config.GROUP_ID, message_id=int(msg_id))
            except Exception as e:
                logger.error(f"Could not delete old message {msg_id} from group: {e}")
                
    # Post new content
    new_caption = (
        f"🛍 *YANGI MAHSULOT!* (Tahrirlangan)\n\n"
        f"📍 Kelish joyi: {product['location']}\n"
        f"⏱ Kelish muddati: {product['delivery_time']}\n"
        f"💵 Narxi: {product['price']}\n\n"
        f"📝 Izoh: {product['description']}"
    )
    
    bot_info = await context.bot.get_me()
    group_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Sotib olish 💳", url=f"https://t.me/{bot_info.username}?start=buy_{product_id}")]
    ])
    
    try:
        photo_ids = product['photo_id'].split(",")
        sent_msg_ids = []
        
        if len(photo_ids) == 1:
            group_msg = await context.bot.send_photo(
                chat_id=config.GROUP_ID,
                photo=photo_ids[0],
                caption=new_caption,
                parse_mode="Markdown",
                reply_markup=group_keyboard
            )
            sent_msg_ids.append(group_msg.message_id)
        else:
            media = []
            for idx, pid in enumerate(photo_ids):
                if idx == 0:
                    media.append(InputMediaPhoto(media=pid, caption=new_caption, parse_mode="Markdown"))
                else:
                    media.append(InputMediaPhoto(media=pid))
            
            media_msgs = await context.bot.send_media_group(
                chat_id=config.GROUP_ID,
                media=media
            )
            for m in media_msgs:
                sent_msg_ids.append(m.message_id)
            
            # Send the button message below it
            btn_msg = await context.bot.send_message(
                chat_id=config.GROUP_ID,
                text=f"🛒 Sotib olish uchun quyidagi tugmani bosing:",
                reply_markup=group_keyboard
            )
            sent_msg_ids.append(btn_msg.message_id)
        
        group_msg_ids_str = ",".join(str(mid) for mid in sent_msg_ids)
        db.update_product_field(product_id, 'group_message_id', group_msg_ids_str)
        
    except Exception as e:
        logger.error(f"Failed updating group message for product {product_id}: {e}")
