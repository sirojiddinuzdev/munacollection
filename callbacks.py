import logging
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
    start_checkout,
    show_catalog,
    update_group_post_after_edit
)

logger = logging.getLogger(__name__)

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
        await show_catalog(update, context, index=index)
        return

    # Buy Product trigger from within the bot catalog
    if data.startswith("buy_prod_"):
        product_id = int(data.split("_")[2])
        await query.answer()
        await start_checkout(update, context, product_id)
        return

    # --- ADMIN CALLBACKS ---
    if not db.is_admin(user_id):
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
            
            # Always send only the first photo to the group with the caption and the inline button (Variant A)
            main_photo = photo_ids[0] if photo_ids else None
            if main_photo:
                group_msg = await context.bot.send_photo(
                    chat_id=config.GROUP_ID,
                    photo=main_photo,
                    caption=group_text,
                    parse_mode="Markdown",
                    reply_markup=group_keyboard
                )
                sent_msg_ids.append(group_msg.message_id)
            else:
                group_msg = await context.bot.send_message(
                    chat_id=config.GROUP_ID,
                    text=group_text,
                    parse_mode="Markdown",
                    reply_markup=group_keyboard
                )
                sent_msg_ids.append(group_msg.message_id)
            
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

        if is_approved:
            from admin_handlers import extract_first_number
            days = extract_first_number(order['delivery_time'])
            
            approved_at = datetime.now()
            delivery_deadline = approved_at + timedelta(days=days)
            
            approved_at_str = approved_at.strftime("%Y-%m-%d %H:%M:%S")
            delivery_deadline_str = delivery_deadline.strftime("%Y-%m-%d %H:%M:%S")
            
            db.approve_order(order_id, approved_at_str, delivery_deadline_str)
        else:
            db.update_order_status(order_id, 'rejected')
        
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
        return

    # Deliver Order request (Shows confirmation buttons in place)
    if data.startswith("deliver_order_"):
        order_id = int(data.split("_")[2])
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Ishonchim komil ✅", callback_data=f"confirm_deliv_{order_id}")],
            [InlineKeyboardButton("Orqaga ⬅️", callback_data=f"cancel_deliv_{order_id}")]
        ])
        await query.message.edit_reply_markup(reply_markup=keyboard)
        await query.answer("Buyurtma yetkazilganini tasdiqlang")
        return

    # Cancel delivery confirmation (restores "Yetkazildi ✅" button)
    if data.startswith("cancel_deliv_"):
        order_id = int(data.split("_")[2])
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Yetkazildi ✅", callback_data=f"deliver_order_{order_id}")]
        ])
        await query.message.edit_reply_markup(reply_markup=keyboard)
        await query.answer()
        return

    # Confirm delivery
    if data.startswith("confirm_deliv_"):
        order_id = int(data.split("_")[2])
        order = db.get_order(order_id)
        if not order:
            await query.answer("Buyurtma topilmadi", show_alert=True)
            return

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.deliver_order(order_id, now_str)

        # Update caption to show it's delivered
        original_caption = query.message.caption or ""
        new_caption = f"{original_caption}\n\n✅ YETKAZIB BERILDI! (Vaqt: {now_str})"
        
        try:
            await query.message.edit_caption(caption=new_caption, reply_markup=None)
        except Exception:
            try:
                await query.message.edit_text(text=f"{query.message.text}\n\n✅ YETKAZIB BERILDI! (Vaqt: {now_str})", reply_markup=None)
            except Exception:
                pass

        await query.answer("Buyurtma yetkazildi deb belgilandi! ✅")

        # Notify Buyer
        buyer_text = (
            f"🎉 Tabriklaymiz! Sizning #{order_id} raqamli buyurtmangiz yetkazildi!\n\n"
            f"📦 Mahsulot sizga eson-omon yetib bordi degan umiddamiz.\n"
            f"Agar mahsulot bo'yicha biror muammo yoki savol bo'lsa, admin bilan bog'laning: {config.ADMIN_USERNAME}"
        )
        try:
            await context.bot.send_message(chat_id=order['user_id'], text=buyer_text)
        except Exception as e:
            logger.error(f"Could not notify buyer {order['user_id']} of delivery: {e}")
        return

    # Extend order deadline request (shows options)
    if data.startswith("extend_order_"):
        order_id = int(data.split("_")[2])
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("3 kun 🗓", callback_data=f"ext_days_3_{order_id}"),
             InlineKeyboardButton("7 kun 🗓", callback_data=f"ext_days_7_{order_id}")],
            [InlineKeyboardButton("14 kun 🗓", callback_data=f"ext_days_14_{order_id}")],
            [InlineKeyboardButton("Orqaga ⬅️", callback_data=f"cancel_deliv_{order_id}")]
        ])
        await query.message.edit_reply_markup(reply_markup=keyboard)
        await query.answer("Uzaytirish muddatini tanlang")
        return

    # Process extension
    if data.startswith("ext_days_"):
        parts = data.split("_")
        days = int(parts[2])
        order_id = int(parts[3])
        
        order = db.get_order(order_id)
        if not order:
            await query.answer("Buyurtma topilmadi", show_alert=True)
            return

        # Calculate new deadline relative to current deadline or now (whichever is later)
        deadline_str = order.get('delivery_deadline')
        now = datetime.now()
        
        current_deadline = None
        if deadline_str:
            try:
                current_deadline = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
                
        if current_deadline and current_deadline > now:
            new_deadline = current_deadline + timedelta(days=days)
        else:
            new_deadline = now + timedelta(days=days)
            
        new_deadline_str = new_deadline.strftime("%Y-%m-%d %H:%M:%S")
        db.extend_order_deadline(order_id, new_deadline_str)
        
        # Reset the reply markup to original deliver button
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Yetkazildi ✅", callback_data=f"deliver_order_{order_id}")]
        ])
        
        # Edit text/caption to show updated deadline
        original_caption = query.message.caption or ""
        new_deadline_formatted = new_deadline.strftime("%Y-%m-%d %H:%M")
        new_caption = f"{original_caption}\n\n⏱ Yangi muddat: {new_deadline_formatted} (Uzaytirildi +{days} kun)"
        
        try:
            await query.message.edit_caption(caption=new_caption, reply_markup=keyboard)
        except Exception:
            try:
                await query.message.edit_text(text=f"{query.message.text}\n\n⏱ Yangi muddat: {new_deadline_formatted} (Uzaytirildi +{days} kun)", reply_markup=keyboard)
            except Exception:
                pass
                
        await query.answer(f"Buyurtma muddati {days} kunga uzaytirildi! 🗓")
        return

    # Pagination for undelivered orders
    if data.startswith("undel_page_"):
        start_index = int(data.split("_")[2])
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        from admin_handlers import send_undelivered_orders_page
        await send_undelivered_orders_page(update, context, start_index=start_index)
        return

    # Fallback answer to prevent infinite loading spinner if any path didn't call answer()
    try:
        await query.answer()
    except Exception:
        pass
