import logging
import asyncio
import time
import re
from datetime import datetime, timedelta
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto
)
from telegram.ext import ContextTypes
import config
from database import db
from funksiyalar import (
    get_main_keyboard,
    get_cancel_keyboard,
    update_group_post_after_edit,
    show_catalog,
    get_super_admin_keyboard
)

logger = logging.getLogger(__name__)

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    text = update.message.text
    state = context.user_data.get('state')

    # Ensure user is admin
    if not db.is_admin(user_id):
        return False

    # --- ADMIN STATES ---
    
    # 1. Ad creation states
    if state == 'AD_PHOTO':
        if not update.message.photo:
            await update.message.reply_text("Iltimos, faqat rasm yuboring.")
            return True
        
        if 'new_ad_photos' not in context.user_data:
            context.user_data['new_ad_photos'] = []
            
        context.user_data['new_ad_photos'].append(update.message.photo[-1].file_id)
        
        current_time = time.time()
        context.user_data['last_photo_time'] = current_time
        
        async def process_photos_after_delay(user_data_ref, chat_id, last_time):
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
        return True

    elif state == 'AD_LOCATION':
        if not text:
            await update.message.reply_text("Iltimos, matn yuboring.")
            return True
        context.user_data['new_ad_location'] = text
        context.user_data['state'] = 'AD_DELIVERY'
        await update.message.reply_text("Kelish muddatini yozing:")
        return True

    elif state == 'AD_DELIVERY':
        if not text:
            await update.message.reply_text("Iltimos, matn yuboring.")
            return True
        context.user_data['new_ad_delivery'] = text
        context.user_data['state'] = 'AD_PRICE'
        await update.message.reply_text("Mahsulot narxini yozing:")
        return True

    elif state == 'AD_PRICE':
        if not text:
            await update.message.reply_text("Iltimos, matn yuboring.")
            return True
        context.user_data['new_ad_price'] = text
        context.user_data['state'] = 'AD_DESCRIPTION'
        await update.message.reply_text("Mahsulot haqida izoh yozing:")
        return True

    elif state == 'AD_DESCRIPTION':
        if not text:
            await update.message.reply_text("Iltimos, matn yuboring.")
            return True
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
        return True

    # 2. Card detail update states
    elif state == 'CARD_NUMBER':
        if not text:
            await update.message.reply_text("Iltimos, karta raqamini matn ko'rinishida kiriting.")
            return True
        db.set_setting('card_number', text)
        context.user_data['state'] = 'CARD_HOLDER'
        await update.message.reply_text("Karta egasining ismini kiriting:")
        return True

    elif state == 'CARD_HOLDER':
        if not text:
            await update.message.reply_text("Iltimos, ismni kiriting.")
            return True
        db.set_setting('card_holder', text)
        context.user_data['state'] = None
        await update.message.reply_text(
            f"Karta ma'lumotlari muvaffaqiyatli yangilandi! ✅\n\n"
            f"Karta: {db.get_setting('card_number')}\n"
            f"Egasi: {db.get_setting('card_holder')}",
            reply_markup=get_main_keyboard(user_id)
        )
        return True

    # 3. Edit Existing Product state
    elif state == 'EDIT_VALUE':
        product_id = context.user_data['edit_product_id']
        field = context.user_data['edit_field']

        if field == 'photo_id':
            if not update.message.photo:
                await update.message.reply_text("Iltimos, yangi rasmni rasm ko'rinishida yuboring.")
                return True
            
            if 'edit_photos' not in context.user_data:
                context.user_data['edit_photos'] = []
            
            context.user_data['edit_photos'].append(update.message.photo[-1].file_id)
            
            current_time = time.time()
            context.user_data['last_edit_photo_time'] = current_time
            
            async def process_edit_photos_after_delay(user_data_ref, chat_id, last_time):
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
            return True
        else:
            if not text:
                await update.message.reply_text("Tahrirlash bekor qilindi. Matn yuborilmadi.", reply_markup=get_main_keyboard(user_id))
                return True
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
            return True

    elif state == 'SUPER_ADD_ADMIN':
        if not text or not text.isdigit():
            await update.message.reply_text("Iltimos, faqat foydalanuvchining sonli Telegram ID raqamini yuboring:")
            return True
        
        new_admin_id = int(text)
        if db.is_admin(new_admin_id):
            await update.message.reply_text("Ushbu foydalanuvchi allaqachon admin!", reply_markup=get_super_admin_keyboard())
            context.user_data['state'] = None
            return True
        
        db.add_admin(new_admin_id)
        context.user_data['state'] = None
        await update.message.reply_text(
            f"Yangi admin muvaffaqiyatli qo'shildi! ✅\nID: `{new_admin_id}`",
            parse_mode="Markdown",
            reply_markup=get_super_admin_keyboard()
        )
        return True

    elif state == 'SUPER_DEL_ADMIN':
        if not text or not text.isdigit():
            await update.message.reply_text("Iltimos, faqat o'chirmoqchi bo'lgan adminning Telegram ID raqamini yuboring:")
            return True
        
        del_admin_id = int(text)
        
        if del_admin_id in config.ADMIN_IDS:
            await update.message.reply_text(
                "Tizim adminini (static admin) o'chirib bo'lmaydi! Uni faqat .env faylidan o'chirish mumkin.",
                reply_markup=get_super_admin_keyboard()
            )
            context.user_data['state'] = None
            return True
            
        db_admins = [a['user_id'] for a in db.get_db_admins()]
        if del_admin_id not in db_admins:
            await update.message.reply_text(
                "Ushbu ID dinamik adminlar ro'yxatida topilmadi.",
                reply_markup=get_super_admin_keyboard()
            )
            context.user_data['state'] = None
            return True
        
        db.remove_admin(del_admin_id)
        context.user_data['state'] = None
        await update.message.reply_text(
            f"Admin muvaffaqiyatli o'chirildi! ❌\nID: `{del_admin_id}`",
            parse_mode="Markdown",
            reply_markup=get_super_admin_keyboard()
        )
        return True

    # --- ADMIN MENU NAVIGATION ---
    
    # Elon Joylashtirish ➕
    if text == "Elon Joylashtirish ➕":
        context.user_data['state'] = 'AD_PHOTO'
        await update.message.reply_text(
            "Yangi e'lon yaratish jarayoni boshlandi. ➕\n\n"
            "Iltimos, mahsulot *rasmini(larini)* yuboring:\n"
            "(Agar bir nechta rasm bo'lsa, hammasini albom shaklida birdan yuboring va bot rasmlarni yig'ib olishi uchun 3 soniya kuting):",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard()
        )
        return True

    # Karta Raqami 💳
    elif text == "Karta Raqami 💳":
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
        return True

    # Statistika 📊
    elif text == "Statistika 📊":
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
        return True

    # Buyurtmalar 📝
    elif text == "Buyurtmalar 📝":
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
            return True

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
        return True

    # Yetkazilmagan buyurtmalar ⏳
    elif text == "Yetkazilmagan buyurtmalar ⏳":
        await send_undelivered_orders_page(update, context, start_index=0)
        return True

    # Yetkazilgan buyurtmalar ✅
    elif text == "Yetkazilgan buyurtmalar ✅":
        orders = db.get_delivered_orders()
        if not orders:
            await update.message.reply_text("Hozircha yetkazilgan buyurtmalar mavjud emas. ✅")
            return True
            
        # List last 15 delivered orders
        slice_orders = orders[:15]
        await update.message.reply_text(f"Oxirgi yetkazilgan {len(slice_orders)} ta buyurtma:")
        
        for order in slice_orders:
            buyer_username = f"@{order['username']}" if order['username'] else "Mavjud emas"
            msg_text = (
                f"✅ *BUYURTMA #{order['id']}* (Yetkazilgan)\n\n"
                f"👤 Xaridor: {buyer_username}\n"
                f"📞 Telefon: {order['phone_number']}\n"
                f"📅 Qabul qilingan: {order['approved_at'] or order['created_at']}\n"
                f"🚚 Yetkazib berilgan: {order['delivered_at']}\n\n"
                f"📦 *Mahsulot parametrlari:*\n"
                f"- Joyi: {order['location']}\n"
                f"- Narxi: {order['price']}\n"
                f"- Izohi: {order['description']}"
            )
            
            photo_ids = [pid.strip() for pid in order['photo_id'].split(",") if pid.strip()]
            try:
                if photo_ids:
                    await update.message.reply_photo(
                        photo=photo_ids[0],
                        caption=msg_text,
                        parse_mode="Markdown"
                    )
                else:
                    await update.message.reply_text(
                        msg_text,
                        parse_mode="Markdown"
                    )
            except Exception as e:
                logger.error(f"Error listing delivered order {order['id']}: {e}")
        return True

    # --- SUPER ADMIN MENU NAVIGATION ---
    elif text == "Super Admin 👑" and user_id == config.SUPER_ADMIN_ID:
        await update.message.reply_text(
            "👑 *Super Admin paneliga xush kelibsiz!*\n\n"
            "Quyidagi tugmalar orqali adminlarni boshqarishingiz mumkin:",
            parse_mode="Markdown",
            reply_markup=get_super_admin_keyboard()
        )
        return True

    elif text == "Adminlar ro'yxati 📋" and user_id == config.SUPER_ADMIN_ID:
        static_admins = config.ADMIN_IDS
        db_admins_list = db.get_db_admins()
        
        msg = "📋 *Bot Administratorlari Ro'yxati:*\n\n"
        msg += "*Tizim adminlari (static, .env):*\n"
        for idx, uid in enumerate(static_admins):
            user = db.get_user(uid)
            username_str = f" (@{user['username']})" if user and user['username'] else ""
            msg += f"{idx+1}. `{uid}`{username_str}\n"
            
        if db_admins_list:
            msg += "\n*Dinamik adminlar (bazadan):*\n"
            for idx, adm in enumerate(db_admins_list):
                username_str = f" (@{adm['username']})" if adm['username'] else ""
                msg += f"{idx+1}. `{adm['user_id']}`{username_str} — qo'shilgan: {adm['added_at']}\n"
        else:
            msg += "\n*Dinamik adminlar yo'q.*"
            
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_super_admin_keyboard())
        return True

    elif text == "Admin qo'shish ➕" and user_id == config.SUPER_ADMIN_ID:
        context.user_data['state'] = 'SUPER_ADD_ADMIN'
        await update.message.reply_text(
            "Qo'shmoqchi bo'lgan yangi adminning Telegram *User ID* (faqat raqamlardan iborat) raqamini yuboring:\n\n"
            "Masalan: `123456789`\n"
            "(User ID ni aniqlash uchun @userinfobot botidan foydalanish mumkin)",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard()
        )
        return True

    elif text == "Admin o'chirish ❌" and user_id == config.SUPER_ADMIN_ID:
        db_admins_list = db.get_db_admins()
        if not db_admins_list:
            await update.message.reply_text(
                "Bazada dinamik qo'shilgan adminlar mavjud emas.",
                reply_markup=get_super_admin_keyboard()
            )
            return True
            
        context.user_data['state'] = 'SUPER_DEL_ADMIN'
        msg = "O'chirmoqchi bo'lgan adminning Telegram *User ID* raqamini kiriting:\n\n"
        for idx, adm in enumerate(db_admins_list):
            username_str = f" (@{adm['username']})" if adm['username'] else ""
            msg += f"- `{adm['user_id']}`{username_str}\n"
            
        await update.message.reply_text(
            msg,
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard()
        )
        return True

    elif text == "Orqaga ⬅️" and user_id == config.SUPER_ADMIN_ID:
        await update.message.reply_text(
            "Asosiy menyuga qaytdingiz.",
            reply_markup=get_main_keyboard(user_id)
        )
        return True

    return False

# --- HELPERS FOR ORDER DELIVERY AND NOTIFICATIONS ---

def extract_first_number(s: str) -> int:
    if not s:
        return 7
    match = re.search(r'\d+', s)
    if match:
        return int(match.group())
    return 7

def get_order_days_left(order):
    deadline_str = order.get('delivery_deadline')
    if not deadline_str:
        created_at_str = order.get('created_at')
        days = extract_first_number(order.get('delivery_time', '7'))
        try:
            created_dt = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            created_dt = datetime.now()
        deadline_dt = created_dt + timedelta(days=days)
    else:
        try:
            deadline_dt = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            deadline_dt = datetime.now()
            
    now = datetime.now()
    time_left = deadline_dt - now
    return time_left.total_seconds(), deadline_dt

async def send_undelivered_orders_page(update: Update, context: ContextTypes.DEFAULT_TYPE, start_index: int = 0):
    orders = db.get_undelivered_orders()
    if not orders:
        msg = "Hozircha yetkazilmagan buyurtmalar mavjud emas. ⏳"
        if update.message:
            await update.message.reply_text(msg)
        elif update.callback_query:
            await update.callback_query.message.reply_text(msg)
        return

    # Calculate remaining time and sort
    sorted_orders = []
    for o in orders:
        sec_left, deadline_dt = get_order_days_left(o)
        sorted_orders.append((sec_left, deadline_dt, o))
        
    # Sort: nearest deadline (least sec_left) first
    sorted_orders.sort(key=lambda x: x[0])
    
    total = len(sorted_orders)
    slice_orders = sorted_orders[start_index : start_index + 10]
    
    chat_id = update.effective_chat.id
    
    # Send title
    msg_title = f"⏳ Yetkazilmagan buyurtmalar ({start_index + 1} - {min(start_index + 10, total)} / {total}):"
    if update.message:
        await update.message.reply_text(msg_title)
    elif update.callback_query:
        await update.callback_query.message.reply_text(msg_title)
        
    for sec_left, deadline_dt, order in slice_orders:
        buyer_username = f"@{order['username']}" if order['username'] else "Mavjud emas"
        
        days_left = int(sec_left // 86400)
        hours_left = int((sec_left % 86400) // 3600)
        
        if sec_left > 0:
            if days_left > 0:
                time_status = f"⏳ Muddat: {days_left} kun, {hours_left} soat qoldi"
            else:
                time_status = f"⏳ Muddat: {hours_left} soat qoldi"
        else:
            overdue_days = abs(days_left)
            if overdue_days == 0:
                time_status = f"🚨 MUDDATI BUGUN TUGAYDI (yoki bir necha soat o'tgan)!"
            else:
                time_status = f"🚨 MUDDATI O'TGAN: {overdue_days} kunga!"
            
        deadline_formatted = deadline_dt.strftime("%Y-%m-%d %H:%M")
        
        msg_text = (
            f"📋 *BUYURTMA #{order['id']}*\n\n"
            f"👤 Xaridor: {buyer_username}\n"
            f"📞 Telefon: {order['phone_number']}\n"
            f"📅 Qabul qilingan: {order['approved_at'] or order['created_at']}\n"
            f"⏱ Yetkazilishi kerak: {deadline_formatted}\n"
            f"{time_status}\n\n"
            f"📦 *Mahsulot parametrlari:*\n"
            f"- Joyi: {order['location']}\n"
            f"- Narxi: {order['price']}\n"
            f"- Izohi: {order['description']}"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Yetkazildi ✅", callback_data=f"deliver_order_{order['id']}")]
        ])
        
        # Send photo(s) if available
        photo_ids = [pid.strip() for pid in order['photo_id'].split(",") if pid.strip()]
        try:
            if not photo_ids:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=msg_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            elif len(photo_ids) == 1:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_ids[0],
                    caption=msg_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            else:
                # Send as a media group
                media = [InputMediaPhoto(media=pid) for pid in photo_ids]
                await context.bot.send_media_group(
                    chat_id=chat_id,
                    media=media
                )
                # Send caption and keyboard
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=msg_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
        except Exception as e:
            logger.error(f"Error sending undelivered order {order['id']}: {e}")
            
    # Check if there are more orders for next page
    if total > start_index + 10:
        next_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Keyingi 10 ta buyurtma ➡️", callback_data=f"undel_page_{start_index + 10}")]
        ])
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Yana {total - (start_index + 10)} ta yetkazilmagan buyurtma mavjud. Keyingi 10 tasini yuklashni xohlaysizmi?",
            reply_markup=next_keyboard
        )
