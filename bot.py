import logging
import re
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InputMediaPhoto
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    TypeHandler
)
import config
from database import Database

# Enable logging to both console and a log file
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Database
db = Database(config.DB_FILE)

# Helper Keyboards
def get_main_keyboard(user_id):
    if user_id in config.ADMIN_IDS:
        return ReplyKeyboardMarkup([
            [KeyboardButton("Elon Joylashtirish ➕"), KeyboardButton("Bozor 🛍")],
            [KeyboardButton("Buyurtmalar 📝"), KeyboardButton("Karta Raqami 💳")],
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

# Registration decorator/check
async def is_authorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if user_id in config.ADMIN_IDS:
        return True
    if db.is_user_registered(user_id):
        return True
    return False

async def request_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Xush kelibsiz! Bot xizmatlaridan foydalanish uchun telefon raqamingiz orqali ro'yxatdan o'ting:",
        reply_markup=get_register_keyboard()
    )

# Commands
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
    if user_id in config.ADMIN_IDS:
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
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Test tugmasi 🔘", callback_data="test_callback")]
    ])
    await update.message.reply_text("Test tugmasini bosing:", reply_markup=keyboard)

# Contact Registration Handler
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

# Checkout Flow (Buy product)
async def start_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    user_id = update.effective_user.id
    product = db.get_product(product_id)

    if not product:
        await update.message.reply_text("Kechirasiz, ushbu mahsulot topilmadi yoki o'chirilgan.")
        return

    card_number = db.get_setting('card_number', config.DEFAULT_CARD)
    card_holder = db.get_setting('card_holder', config.DEFAULT_CARD_HOLDER)

    context.user_data['state'] = 'BUY_RECEIPT'
    context.user_data['buy_product_id'] = product_id

    # If it is a callback query or a redirect message
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

    # Handle multiple photos
    photo_list = product['photo_id'].split(",")
    if photo_index < 0:
        photo_index = 0
    elif photo_index >= len(photo_list):
        photo_index = len(photo_list) - 1
        
    current_photo = photo_list[photo_index]

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
    
    # 2. Carousel buttons for multiple photos
    if len(photo_list) > 1:
        carousel_row = []
        if photo_index > 0:
            carousel_row.append(InlineKeyboardButton("⬅️ Rasm", callback_data=f"prod_pic_{index}_{photo_index-1}"))
        else:
            carousel_row.append(InlineKeyboardButton("❌", callback_data="noop"))
            
        carousel_row.append(InlineKeyboardButton(f"🖼 {photo_index+1}/{len(photo_list)}", callback_data="noop"))
        
        if photo_index < len(photo_list) - 1:
            carousel_row.append(InlineKeyboardButton("Rasm ➡️", callback_data=f"prod_pic_{index}_{photo_index+1}"))
        else:
            carousel_row.append(InlineKeyboardButton("❌", callback_data="noop"))
            
        keyboard.append(carousel_row)
        
    # 3. Product navigation buttons
    nav_row = []
    if index > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Oldingi Mahsulot", callback_data=f"cat_idx_{index-1}"))
    nav_row.append(InlineKeyboardButton(f"{index+1}/{total}", callback_data="noop"))
    if index < total - 1:
        nav_row.append(InlineKeyboardButton("Keyingi Mahsulot ➡️", callback_data=f"cat_idx_{index+1}"))
    keyboard.append(nav_row)

    # 4. Admin controls
    if user_id in config.ADMIN_IDS:
        keyboard.append([
            InlineKeyboardButton("Tahrirlash ✏️", callback_data=f"admin_edit_{product['id']}"),
            InlineKeyboardButton("O'chirish ❌", callback_data=f"admin_del_{product['id']}")
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if update.message:
            await update.message.reply_photo(
                photo=current_photo,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        elif update.callback_query:
            # Edit existing message media and caption to reduce spam
            query = update.callback_query
            await query.answer()
            await query.message.edit_media(
                media=InputMediaPhoto(media=current_photo, caption=caption, parse_mode="Markdown"),
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Catalog displaying error: {e}")
        # Fallback to sending a new message
        if update.callback_query:
            await update.callback_query.message.reply_photo(
                photo=current_photo,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )

# Callback Query Handler
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    logger.info(f"Callback query received: user_id={user_id}, data={data}")

    # Check if this is a group chat
    if update.effective_chat and update.effective_chat.type != "private":
        try:
            await query.answer("Bu xizmat guruhda ishlamaydi.", show_alert=True)
        except Exception:
            pass
        return

    if data == "noop":
        await query.answer()
        return

    if data == "test_callback":
        await query.answer("Test muvaffaqiyatli! ✅", show_alert=True)
        await query.message.reply_text("Callback query to'liq ishladi! 🎉")
        return

    # Catalog Index Navigation
    if data.startswith("cat_idx_"):
        index = int(data.split("_")[2])
        await show_catalog(update, context, index=index, photo_index=0)
        return

    # Carousel Picture Navigation
    if data.startswith("prod_pic_"):
        parts = data.split("_")
        catalog_index = int(parts[2])
        photo_index = int(parts[3])
        await show_catalog(update, context, index=catalog_index, photo_index=photo_index)
        return

    # Buy Product trigger from within the bot catalog
    if data.startswith("buy_prod_"):
        product_id = int(data.split("_")[2])
        await query.answer()
        await start_checkout(update, context, product_id)
        return

    # --- ADMIN CALLBACKS ---
    if user_id not in config.ADMIN_IDS:
        await query.answer("Siz admin emassiz!", show_alert=True)
        return

    # Edit Ad Trigger
    if data.startswith("admin_edit_"):
        product_id = int(data.split("_")[2])
        await query.answer()
        
        keyboard = [
            [InlineKeyboardButton("Rasm 🖼", callback_data=f"edit_f_photo_id_{product_id}")],
            [InlineKeyboardButton("Kelish Joyi 📍", callback_data=f"edit_f_location_{product_id}"),
             InlineKeyboardButton("Kelish Muddati ⏱", callback_data=f"edit_f_delivery_time_{product_id}")],
            [InlineKeyboardButton("Narxi 💵", callback_data=f"edit_f_price_{product_id}"),
             InlineKeyboardButton("Izoh 📝", callback_data=f"edit_f_description_{product_id}")],
            [InlineKeyboardButton("Bekor qilish ❌", callback_data="cat_idx_0")]
        ]
        
        await query.message.reply_text(
            "Qaysi bo'limni tahrirlamoqchisiz?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Field Selection for Editing
    if data.startswith("edit_f_"):
        parts = data.split("_")
        # format: edit_f_[field]_product_id
        # wait: field name can have multiple underscores e.g. delivery_time
        # let's extract:
        # fields can be: photo_id, location, delivery_time, price, description
        product_id = int(parts[-1])
        field = "_".join(parts[2:-1])
        
        context.user_data['state'] = 'EDIT_VALUE'
        context.user_data['edit_product_id'] = product_id
        context.user_data['edit_field'] = field
        
        field_names_uz = {
            'photo_id': "mahsulot rasmini (rasm ko'rinishida)",
            'location': "kelish joyini",
            'delivery_time': "kelish muddatini",
            'price': "mahsulot narxini",
            'description': "mahsulot izohini"
        }
        
        extra_info = ""
        if field == 'photo_id':
            extra_info = "\n(Agar bir nechta rasm yuborsangiz, ularni albom shaklida yuboring va bot rasmlarni yig'ib olishi uchun 3 soniya kuting)"

        await query.answer()
        await query.message.reply_text(
            f"Iltimos, yangi {field_names_uz.get(field, field)} yuboring:{extra_info}",
            reply_markup=get_cancel_keyboard()
        )
        return

    # Delete Ad Trigger
    if data.startswith("admin_del_"):
        product_id = int(data.split("_")[2])
        await query.answer()
        
        keyboard = [
            [InlineKeyboardButton("Ha, o'chirish ✅", callback_data=f"confirm_del_{product_id}")],
            [InlineKeyboardButton("Yo'q, bekor qilish ❌", callback_data="cat_idx_0")]
        ]
        
        await query.message.reply_text(
            "Haqiqatan ham ushbu e'lonni o'chirmoqchimisiz?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Confirm Delete
    if data.startswith("confirm_del_"):
        product_id = int(data.split("_")[2])
        product = db.get_product(product_id)
        
        if product:
            # Delete in db
            db.delete_product(product_id)
            
            # Delete from group if possible
            if product['group_message_id']:
                msg_ids = str(product['group_message_id']).split(",")
                for msg_id in msg_ids:
                    try:
                        await context.bot.delete_message(chat_id=config.GROUP_ID, message_id=int(msg_id))
                    except Exception as e:
                        logger.error(f"Could not delete message {msg_id} from group: {e}")
            
            await query.answer("E'lon o'chirildi", show_alert=True)
            # Delete confirmation prompt
            await query.message.delete()
            # Show catalog again
            await show_catalog(update, context, index=0)
        else:
            await query.answer("E'lon topilmadi", show_alert=True)
        return

    # Publish Ad Confirmed
    if data == "ad_publish":
        await query.answer()
        logger.info(f"ad_publish callback triggered. user_data keys: {list(context.user_data.keys())}")
        # Retrieve ad details
        photo = context.user_data.pop('new_ad_photo', None)
        location = context.user_data.pop('new_ad_location', None)
        delivery = context.user_data.pop('new_ad_delivery', None)
        price = context.user_data.pop('new_ad_price', None)
        description = context.user_data.pop('new_ad_description', None)
        context.user_data['state'] = None
        logger.info(f"ad_publish details: photo={bool(photo)}, location={location}, delivery={delivery}, price={price}, description={description}")
        
        if not all([photo, location, delivery, price, description]):
            await query.message.reply_text("Xato: Elon ma'lumotlari to'liq emas, iltimos qaytadan boshlang.")
            return

        # 1. Insert into Database first to get the Product ID
        product_id = db.add_product(photo, location, delivery, price, description)

        # 2. Format group message
        group_text = (
            f"🛍 *YANGI MAHSULOT!*\n\n"
            f"📍 Kelish joyi: {location}\n"
            f"⏱ Kelish muddati: {delivery}\n"
            f"💵 Narxi: {price}\n\n"
            f"📝 Izoh: {description}"
        )

        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
        
        # Inline button redirecting back to bot with deep link
        group_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Sotib olish 💳", url=f"https://t.me/{bot_username}?start=buy_{product_id}")]
        ])

        # 3. Post to the group
        try:
            photo_ids = photo.split(",")
            sent_msg_ids = []
            
            if len(photo_ids) == 1:
                group_msg = await context.bot.send_photo(
                    chat_id=config.GROUP_ID,
                    photo=photo_ids[0],
                    caption=group_text,
                    parse_mode="Markdown",
                    reply_markup=group_keyboard
                )
                sent_msg_ids.append(group_msg.message_id)
            else:
                media = []
                for idx, pid in enumerate(photo_ids):
                    if idx == 0:
                        media.append(InputMediaPhoto(media=pid, caption=group_text, parse_mode="Markdown"))
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
            
            # Save the message ID(s) of the group post (as a comma-separated string)
            group_msg_ids_str = ",".join(str(mid) for mid in sent_msg_ids)
            db.update_product_field(product_id, 'group_message_id', group_msg_ids_str)
            
            await query.message.reply_text(
                "E'lon guruhga muvaffaqiyatli joylashtirildi! 🚀",
                reply_markup=get_main_keyboard(user_id)
            )
            await query.message.delete() # Remove preview message
            
        except Exception as e:
            logger.error(f"Failed sending to group: {e}")
            await query.message.reply_text(
                f"❌ Xato: E'lon bazaga saqlandi, lekin guruhga yuborib bo'lmadi.\n"
                f"Tafsilotlar: {e}\n\n"
                f"Bot guruhga admin qilib qo'shilganiga va config.GROUP_ID to'g'ri ekanligiga ishonch hosil qiling.",
                reply_markup=get_main_keyboard(user_id)
            )

    # Cancel Ad Publish
    if data == "ad_cancel":
        await query.answer("E'lon bekor qilindi")
        context.user_data.pop('new_ad_photo', None)
        context.user_data.pop('new_ad_location', None)
        context.user_data.pop('new_ad_delivery', None)
        context.user_data.pop('new_ad_price', None)
        context.user_data.pop('new_ad_description', None)
        context.user_data['state'] = None
        
        await query.message.reply_text("E'lon bekor qilindi. ❌", reply_markup=get_main_keyboard(user_id))
        await query.message.delete()

    # Change Card Trigger (Callback from card view)
    if data == "change_card":
        await query.answer()
        context.user_data['state'] = 'CARD_NUMBER'
        await query.message.reply_text(
            "Iltimos, yangi karta raqamini kiriting:",
            reply_markup=get_cancel_keyboard()
        )
        return

    # Order approval/rejection (Admin review)
    if data.startswith("order_app_") or data.startswith("order_rej_"):
        is_approved = data.startswith("order_app_")
        order_id = int(data.split("_")[2])
        
        order = db.get_order(order_id)
        if not order:
            await query.answer("Buyurtma topilmadi", show_alert=True)
            return

        status = 'approved' if is_approved else 'rejected'
        db.update_order_status(order_id, status)
        
        status_text = "TASDIQLANDI ✅" if is_approved else "RAD ETILDI ❌"
        await query.answer(f"Buyurtma #{order_id} {status_text}")

        # Update Admin's view
        new_caption = (
            f"🔔 BUYURTMA #{order_id} ({status_text})\n\n"
            f"👤 Xaridor: @{order['username']} (ID: {order['user_id']})\n"
            f"📞 Telefon: {order['phone_number']}\n\n"
            f"📦 Mahsulot:\n"
            f"- ID: {order['product_id']}\n"
            f"- Joyi: {order['location']}\n"
            f"- Narxi: {order['price']}\n"
            f"- Izohi: {order['description']}"
        )
        
        await query.message.edit_caption(
            caption=new_caption,
            reply_markup=None # Remove approval buttons
        )

        # Notify Buyer
        buyer_text = ""
        if is_approved:
            buyer_text = (
                f"🎉 Tabriklaymiz! Sizning #{order_id} raqamli buyurtmangiz tasdiqlandi!\n\n"
                f"📦 Mahsulot tez orada yetkaziladi/tayyorlanadi.\n"
                f"Qo'shimcha savollar uchun: {config.ADMIN_USERNAME}"
            )
        else:
            buyer_text = (
                f"❌ Afsuski, sizning #{order_id} raqamli buyurtmangiz to'lovi rad etildi.\n\n"
                f"Iltimos, chekni va ma'lumotlarni qayta tekshiring yoki admin bilan bog'laning: {config.ADMIN_USERNAME}"
            )
            
        try:
            await context.bot.send_message(chat_id=order['user_id'], text=buyer_text)
        except Exception as e:
            logger.error(f"Could not notify buyer {order['user_id']}: {e}")

    # Fallback answer to prevent infinite loading spinner if any path didn't call answer()
    try:
        await query.answer()
    except Exception:
        pass

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
        
        await update.message.reply_text(
            "Amal bekor qilindi.",
            reply_markup=get_main_keyboard(user_id)
        )
        return

    # --- USER STATES ---
    
    # 1. Buy flow receipt upload state
    if state == 'BUY_RECEIPT':
        if not update.message.photo:
            await update.message.reply_text("Iltimos, faqat to'lov cheki rasmini yuboring.")
            return

        receipt_photo_id = update.message.photo[-1].file_id
        product_id = context.user_data.pop('buy_product_id')
        context.user_data['state'] = None

        product = db.get_product(product_id)
        if not product:
            await update.message.reply_text("Xato: Mahsulot topilmadi.", reply_markup=get_main_keyboard(user_id))
            return

        # Save Order in Database
        order_id = db.create_order(user_id, product_id, receipt_photo_id)

        # Notify Buyer
        await update.message.reply_text(
            f"✅ To'lov chekingiz qabul qilindi!\n\n"
            f"Adminlarimiz to'lovni tasdiqlashini kuting. Tez orada siz bilan bog'lanamiz.\n"
            f"Admin bilan bog'lanish: {config.ADMIN_USERNAME}",
            reply_markup=get_main_keyboard(user_id)
        )

        # Notify Admins
        buyer_user = db.get_user(user_id)
        buyer_username = f"@{buyer_user['username']}" if buyer_user['username'] else "Mavjud emas"
        admin_msg_text = (
            f"🔔 YANGI BUYURTMA #{order_id}!\n\n"
            f"👤 Xaridor: {buyer_username} (ID: {user_id})\n"
            f"📞 Telefon: {buyer_user['phone_number']}\n\n"
            f"📦 Mahsulot:\n"
            f"- ID: {product['id']}\n"
            f"- Joyi: {product['location']}\n"
            f"- Narxi: {product['price']}\n"
            f"- Izohi: {product['description']}"
        )

        admin_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Tasdiqlash ✅", callback_data=f"order_app_{order_id}"),
                InlineKeyboardButton("Rad etish ❌", callback_data=f"order_rej_{order_id}")
            ]
        ])

        for admin_id in config.ADMIN_IDS:
            try:
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=receipt_photo_id,
                    caption=admin_msg_text,
                    reply_markup=admin_keyboard
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
        return

    # --- ADMIN STATES ---
    
    # 2. Ad creation states
    if state == 'AD_PHOTO':
        if not update.message.photo:
            await update.message.reply_text("Iltimos, faqat rasm yuboring.")
            return
        
        if 'new_ad_photos' not in context.user_data:
            context.user_data['new_ad_photos'] = []
            
        context.user_data['new_ad_photos'].append(update.message.photo[-1].file_id)
        
        import time
        import asyncio
        current_time = time.time()
        context.user_data['last_photo_time'] = current_time
        
        async def process_photos_after_delay(user_data_ref, chat_id, last_time):
            import asyncio
            await asyncio.sleep(3.0)
            if user_data_ref.get('last_photo_time') == last_time:
                photos = user_data_ref.pop('new_ad_photos', [])
                user_data_ref.pop('last_photo_time', None)
                user_data_ref['new_ad_photo'] = ",".join(photos)
                user_data_ref['state'] = 'AD_LOCATION'
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"Rasm(lar) qabul qilindi: {len(photos)} ta rasm. ✅\nMahsulot qayerdan kelishini yozing:"
                )
                
        asyncio.create_task(process_photos_after_delay(context.user_data, update.effective_chat.id, current_time))
        return

    elif state == 'AD_LOCATION':
        if not text:
            await update.message.reply_text("Iltimos, matn yuboring.")
            return
        context.user_data['new_ad_location'] = text
        context.user_data['state'] = 'AD_DELIVERY'
        await update.message.reply_text("Kelish muddatini yozing:")
        return

    elif state == 'AD_DELIVERY':
        if not text:
            await update.message.reply_text("Iltimos, matn yuboring.")
            return
        context.user_data['new_ad_delivery'] = text
        context.user_data['state'] = 'AD_PRICE'
        await update.message.reply_text("Mahsulot narxini yozing:")
        return

    elif state == 'AD_PRICE':
        if not text:
            await update.message.reply_text("Iltimos, matn yuboring.")
            return
        context.user_data['new_ad_price'] = text
        context.user_data['state'] = 'AD_DESCRIPTION'
        await update.message.reply_text("Mahsulot haqida izoh yozing:")
        return

    elif state == 'AD_DESCRIPTION':
        if not text:
            await update.message.reply_text("Iltimos, matn yuboring.")
            return
        context.user_data['new_ad_description'] = text
        context.user_data['state'] = 'AD_CONFIRM'

        # Show preview
        photo_ids = context.user_data['new_ad_photo'].split(",")
        preview_photo = photo_ids[0]
        preview_text = (
            f"📦 *E'lon Preview:*\n\n"
            f"📍 Kelish joyi: {context.user_data['new_ad_location']}\n"
            f"⏱ Kelish muddati: {context.user_data['new_ad_delivery']}\n"
            f"💵 Narxi: {context.user_data['new_ad_price']}\n"
            f"📝 Izoh: {context.user_data['new_ad_description']}\n"
            f"🖼 Jami rasmlar: {len(photo_ids)} ta\n\n"
            f"Ushbu e'lonni chop etishni xohlaysizmi?"
        )

        preview_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Chop etish 🚀", callback_data="ad_publish"),
                InlineKeyboardButton("Bekor qilish ❌", callback_data="ad_cancel")
            ]
        ])

        await update.message.reply_photo(
            photo=preview_photo,
            caption=preview_text,
            parse_mode="Markdown",
            reply_markup=preview_keyboard
        )
        return

    # 3. Card detail update states (Admin only)
    elif state == 'CARD_NUMBER' and user_id in config.ADMIN_IDS:
        if not text:
            await update.message.reply_text("Iltimos, karta raqamini matn ko'rinishida kiriting.")
            return
        db.set_setting('card_number', text)
        context.user_data['state'] = 'CARD_HOLDER'
        await update.message.reply_text("Karta egasining ismini kiriting:")
        return

    elif state == 'CARD_HOLDER' and user_id in config.ADMIN_IDS:
        if not text:
            await update.message.reply_text("Iltimos, ismni kiriting.")
            return
        db.set_setting('card_holder', text)
        context.user_data['state'] = None
        await update.message.reply_text(
            f"Karta ma'lumotlari muvaffaqiyatli yangilandi! ✅\n\n"
            f"Karta: {db.get_setting('card_number')}\n"
            f"Egasi: {db.get_setting('card_holder')}",
            reply_markup=get_main_keyboard(user_id)
        )
        return

    # 4. Edit Existing Product state (Admin only)
    elif state == 'EDIT_VALUE' and user_id in config.ADMIN_IDS:
        product_id = context.user_data['edit_product_id']
        field = context.user_data['edit_field']

        if field == 'photo_id':
            if not update.message.photo:
                await update.message.reply_text("Iltimos, yangi rasmni rasm ko'rinishida yuboring.")
                return
            
            if 'edit_photos' not in context.user_data:
                context.user_data['edit_photos'] = []
            
            context.user_data['edit_photos'].append(update.message.photo[-1].file_id)
            
            import time
            import asyncio
            current_time = time.time()
            context.user_data['last_edit_photo_time'] = current_time
            
            async def process_edit_photos_after_delay(user_data_ref, chat_id, last_time):
                import asyncio
                await asyncio.sleep(3.0)
                if user_data_ref.get('last_edit_photo_time') == last_time:
                    photos = user_data_ref.pop('edit_photos', [])
                    user_data_ref.pop('edit_product_id', None)
                    user_data_ref.pop('edit_field', None)
                    user_data_ref.pop('last_edit_photo_time', None)
                    user_data_ref['state'] = None
                    
                    new_value = ",".join(photos)
                    
                    # Update DB
                    db.update_product_field(product_id, field, new_value)
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"Rasm(lar) muvaffaqiyatli yangilandi! Jami: {len(photos)} ta. ✅",
                        reply_markup=get_main_keyboard(user_id)
                    )
                    
                    # Update group post
                    await update_group_post_after_edit(context, product_id)
                    # Show catalog again
                    await show_catalog(update, context, index=0)
            
            asyncio.create_task(process_edit_photos_after_delay(context.user_data, update.effective_chat.id, current_time))
            return
        else:
            if not text:
                await update.message.reply_text("Tahrirlash bekor qilindi. Matn yuborilmadi.", reply_markup=get_main_keyboard(user_id))
                return
            new_value = text
            context.user_data.pop('edit_product_id')
            context.user_data.pop('edit_field')
            context.user_data['state'] = None

            # Update DB
            db.update_product_field(product_id, field, new_value)
            await update.message.reply_text("Mahsulot muvaffaqiyatli tahrirlandi! ✅", reply_markup=get_main_keyboard(user_id))

            # Update group post
            await update_group_post_after_edit(context, product_id)
            # Show catalog again
            await show_catalog(update, context, index=0)
            return

    # --- MENU NAVIGATION ---
    
    # Bozor 🛍
    if text == "Bozor 🛍":
        await show_catalog(update, context, index=0)

    # Aloqa 📞
    elif text == "Aloqa 📞":
        await update.message.reply_text(
            f"Aloqa bo'limi 📞\n\n"
            f"Savollar yoki takliflar yuzasidan admin bilan bog'lanishingiz mumkin:\n"
            f"Admin username: {config.ADMIN_USERNAME}"
        )

    # Elon Joylashtirish ➕ (Admin)
    elif text == "Elon Joylashtirish ➕" and user_id in config.ADMIN_IDS:
        context.user_data['state'] = 'AD_PHOTO'
        await update.message.reply_text(
            "Yangi e'lon yaratish jarayoni boshlandi. ➕\n\n"
            "Iltimos, mahsulot *rasmini(larini)* yuboring:\n"
            "(Agar bir nechta rasm bo'lsa, hammasini albom shaklida birdan yuboring va bot rasmlarni yig'ib olishi uchun 3 soniya kuting):",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard()
        )

    # Karta Raqami 💳 (Admin)
    elif text == "Karta Raqami 💳" and user_id in config.ADMIN_IDS:
        card_number = db.get_setting('card_number', config.DEFAULT_CARD)
        card_holder = db.get_setting('card_holder', config.DEFAULT_CARD_HOLDER)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Kartani o'zgartirish ✏️", callback_data="change_card")]
        ])
        
        await update.message.reply_text(
            f"💳 *Hozirgi karta ma'lumotlari:*\n\n"
            f"Karta raqami: `{card_number}`\n"
            f"Karta egasi: *{card_holder}*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    # Statistika 📊 (Admin)
    elif text == "Statistika 📊" and user_id in config.ADMIN_IDS:
        with db._get_connection() as conn:
            cursor = conn.cursor()
            
            # Users count
            cursor.execute("SELECT COUNT(*) FROM users")
            users_count = cursor.fetchone()[0]
            
            # Active ads
            cursor.execute("SELECT COUNT(*) FROM products WHERE status = 'active'")
            ads_count = cursor.fetchone()[0]
            
            # Orders breakdown
            cursor.execute("SELECT COUNT(*) FROM orders")
            total_orders = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
            pending_orders = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'approved'")
            approved_orders = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'rejected'")
            rejected_orders = cursor.fetchone()[0]

        stats_text = (
            f"📊 *Bot statistikasi:*\n\n"
            f"👥 Jami ro'yxatdan o'tgan foydalanuvchilar: *{users_count}*\n"
            f"🛍 Bozordagi faol e'lonlar soni: *{ads_count}*\n\n"
            f"📝 *Buyurtmalar bo'yicha:*\n"
            f"- Jami buyurtmalar: *{total_orders}*\n"
            f"- Kutilayotgan (Pending): *{pending_orders}*\n"
            f"- Tasdiqlangan (Approved): *{approved_orders}*\n"
            f"- Rad etilgan (Rejected): *{rejected_orders}*"
        )
        
        await update.message.reply_text(stats_text, parse_mode="Markdown")

    # Buyurtmalar 📝 (Admin)
    elif text == "Buyurtmalar 📝" and user_id in config.ADMIN_IDS:
        # Fetch up to 5 pending orders to review
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT o.id, o.user_id, o.product_id, o.receipt_photo_id, 
                       u.username, u.phone_number,
                       p.location, p.price, p.description
                FROM orders o
                JOIN users u ON o.user_id = u.user_id
                JOIN products p ON o.product_id = p.id
                WHERE o.status = 'pending'
                ORDER BY o.id ASC
                LIMIT 5
            """)
            orders = [dict(row) for row in cursor.fetchall()]

        if not orders:
            await update.message.reply_text("Kutilayotgan (Pending) buyurtmalar hozircha mavjud emas. 📝")
            return

        await update.message.reply_text(f"Kutilayotgan oxirgi {len(orders)} ta buyurtma yuborilmoqda. Ularni quyida tasdiqlashingiz yoki rad etishingiz mumkin:")

        for order in orders:
            buyer_username = f"@{order['username']}" if order['username'] else "Mavjud emas"
            admin_msg_text = (
                f"🔔 BUYURTMA #{order['id']}!\n\n"
                f"👤 Xaridor: {buyer_username} (ID: {order['user_id']})\n"
                f"📞 Telefon: {order['phone_number']}\n\n"
                f"📦 Mahsulot:\n"
                f"- ID: {order['product_id']}\n"
                f"- Joyi: {order['location']}\n"
                f"- Narxi: {order['price']}\n"
                f"- Izohi: {order['description']}"
            )

            admin_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Tasdiqlash ✅", callback_data=f"order_app_{order['id']}"),
                    InlineKeyboardButton("Rad etish ❌", callback_data=f"order_rej_{order['id']}")
                ]
            ])

            try:
                await update.message.reply_photo(
                    photo=order['receipt_photo_id'],
                    caption=admin_msg_text,
                    reply_markup=admin_keyboard
                )
            except Exception as e:
                logger.error(f"Error listing order {order['id']}: {e}")

    else:
        # Default fallback
        await update.message.reply_text(
            "Tushunarsiz buyruq. Menyudan foydalaning.",
            reply_markup=get_main_keyboard(user_id)
        )

async def log_all_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info(f"RAW UPDATE: {update.to_dict()}")
    except Exception as e:
        logger.error(f"Error logging raw update: {e}")

def main():
    # Verify TOKEN
    if config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("ILTIMOS: bot.py-ni ishga tushirishdan oldin config.py fayliga bot tokenini kiritganingizga ishonch hosil qiling!")
        # We'll build and run anyway or exit
        # return

    # Build Application
    application = Application.builder().token(config.BOT_TOKEN).build()

    # Global Logger Handler
    application.add_handler(TypeHandler(Update, log_all_updates), group=-1)

    # Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("test_btn", test_btn_command))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    # Run
    print("Bot polling rejimida ishga tushmoqda...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
