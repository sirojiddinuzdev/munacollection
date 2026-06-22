import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import config
from database import db
from funksiyalar import (
    get_main_keyboard,
    show_catalog
)

logger = logging.getLogger(__name__)

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    text = update.message.text
    state = context.user_data.get('state')

    # --- USER STATES ---
    
    # 1. Buy flow receipt upload state
    if state == 'BUY_RECEIPT':
        if not update.message.photo:
            await update.message.reply_text("Iltimos, faqat to'lov cheki rasmini yuboring.")
            return True

        receipt_photo_id = update.message.photo[-1].file_id
        product_id = context.user_data.pop('buy_product_id', None)
        context.user_data['state'] = None

        if not product_id:
            await update.message.reply_text("Xato: Buyurtma holati yo'qoldi.", reply_markup=get_main_keyboard(user_id))
            return True

        product = db.get_product(product_id)
        if not product:
            await update.message.reply_text("Xato: Mahsulot topilmadi.", reply_markup=get_main_keyboard(user_id))
            return True

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

        for admin_id in db.get_all_admin_ids():
            try:
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=receipt_photo_id,
                    caption=admin_msg_text,
                    reply_markup=admin_keyboard
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
        return True

    # --- USER MENU NAVIGATION ---
    
    # Bozor 🛍
    if text == "Bozor 🛍":
        await show_catalog(update, context, index=0)
        return True

    # Aloqa 📞
    elif text == "Aloqa 📞":
        await update.message.reply_text(
            f"Aloqa bo'limi 📞\n\n"
            f"Savollar yoki takliflar yuzasidan admin bilan bog'lanishingiz mumkin:\n"
            f"Admin username: {config.ADMIN_USERNAME}"
        )
        return True

    # Guruh havolasi 👥
    elif text == "Guruh havolasi 👥":
        await update.message.reply_text(
            f"👥 *Muna Collection guruhimiz havolasi:*\n\n"
            f"Havola: https://t.me/munatest1",
            parse_mode="Markdown"
        )
        return True

    # Default fallback
    else:
        await update.message.reply_text(
            "Tushunarsiz buyruq. Menyudan foydalaning.",
            reply_markup=get_main_keyboard(user_id)
        )
        return True
