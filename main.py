import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, InputMediaPhoto
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    TypeHandler,
    filters
)
import config
from database import db
from commands import start_command, test_btn_command, admin_command
from callbacks import handle_callback_query
from messages import handle_message, log_all_updates
from registratsiya import handle_contact

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

async def check_and_notify_deadlines(bot):
    orders = db.get_undelivered_orders()
    now = datetime.now()
    
    for order in orders:
        deadline_str = order.get('delivery_deadline')
        if not deadline_str:
            continue
            
        try:
            deadline_dt = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.error(f"Error parsing deadline for order {order['id']}: {e}")
            continue
            
        time_left = deadline_dt - now
        total_seconds_left = time_left.total_seconds()
        days_left_exact = total_seconds_left / 86400.0
        
        last_notified = order.get('last_notified_days_left')
        if last_notified is None:
            last_notified = 999  # 999 means never notified
            
        notify_milestone = None
        milestone_text = ""
        
        if days_left_exact <= 0:
            overdue_days = int(abs(days_left_exact))
            expected_milestone = -overdue_days if overdue_days >= 1 else 0
            if last_notified != expected_milestone:
                notify_milestone = expected_milestone
                if overdue_days == 0:
                    milestone_text = "🚨 BUGUN YETKAZIB BERISH MUDDATI TUGADI!"
                else:
                    milestone_text = f"🚨 YETKAZIB BERISH MUDDATI {overdue_days} KUN O'TIB KETDI!"
                
        elif days_left_exact <= 1.0 and days_left_exact > 0 and last_notified != 1:
            notify_milestone = 1
            milestone_text = "⏳ MUDDAT TUGASHIGA 1 KUN QOLDI!"
            
        elif days_left_exact <= 3.0 and days_left_exact > 1.0 and last_notified != 3:
            notify_milestone = 3
            milestone_text = "⏳ MUDDAT TUGASHIGA 3 KUN QOLDI!"
            
        if notify_milestone is not None:
            db.update_order_notified_days(order['id'], notify_milestone)
            
            buyer_username = f"@{order['username']}" if order['username'] else "Mavjud emas"
            deadline_formatted = deadline_dt.strftime("%Y-%m-%d %H:%M")
            
            admin_msg_text = (
                f"🚨 *BUYURTMA OGOHLANTIRISHI!*\n"
                f"{milestone_text}\n\n"
                f"📋 *Buyurtma #{order['id']}*\n"
                f"👤 Xaridor: {buyer_username}\n"
                f"📞 Telefon: {order['phone_number']}\n"
                f"⏱ Muddat: {deadline_formatted}\n\n"
                f"📦 *Mahsulot:*\n"
                f"- Joyi: {order['location']}\n"
                f"- Narxi: {order['price']}\n"
                f"- Izohi: {order['description']}\n\n"
                f"Ushbu buyurtma yetkazildimi?"
            )
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Ha, yetkazildi ✅", callback_data=f"deliver_order_{order['id']}")],
                [InlineKeyboardButton("Yo'q, muddatni uzaytirish ⏱", callback_data=f"extend_order_{order['id']}")]
            ])
            
            for admin_id in db.get_all_admin_ids():
                try:
                    photo_ids = [pid.strip() for pid in order['photo_id'].split(",") if pid.strip()]
                    if not photo_ids:
                        await bot.send_message(
                            chat_id=admin_id,
                            text=admin_msg_text,
                            parse_mode="Markdown",
                            reply_markup=keyboard
                        )
                    elif len(photo_ids) == 1:
                        await bot.send_photo(
                            chat_id=admin_id,
                            photo=photo_ids[0],
                            caption=admin_msg_text,
                            parse_mode="Markdown",
                            reply_markup=keyboard
                        )
                    else:
                        # Send all photos as media group
                        media = [InputMediaPhoto(media=pid) for pid in photo_ids]
                        await bot.send_media_group(
                            chat_id=admin_id,
                            media=media
                        )
                        # Send text details and keyboard below it
                        await bot.send_message(
                            chat_id=admin_id,
                            text=admin_msg_text,
                            parse_mode="Markdown",
                            reply_markup=keyboard
                        )
                except Exception as e:
                    logger.error(f"Failed to send deadline notification to admin {admin_id}: {e}")

async def deadline_checker_loop(bot):
    logger.info("Deadline checker background task started.")
    while True:
        try:
            await check_and_notify_deadlines(bot)
        except Exception as e:
            logger.error(f"Error in deadline_checker_loop: {e}")
        await asyncio.sleep(3600)

async def post_init(application: Application) -> None:
    commands = [
        BotCommand("start", "ishga tushirish yoki yangilash"),
        BotCommand("admin", "admin bog'lanish malumotlari")
    ]
    try:
        await application.bot.set_my_commands(commands)
        logger.info("Bot commands successfully set.")
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}")
        
    asyncio.create_task(deadline_checker_loop(application.bot))

def main():
    # Verify TOKEN
    if not config.BOT_TOKEN or config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("ILTIMOS: main.py-ni ishga tushirishdan oldin .env fayliga bot tokenini (BOT_TOKEN) kiriting!")
        return

    # Build Application
    application = Application.builder().token(config.BOT_TOKEN).post_init(post_init).concurrent_updates(True).build()

    # Global Logger Handler
    application.add_handler(TypeHandler(Update, log_all_updates), group=-1)

    # Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("test_btn", test_btn_command))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    # Run
    print("Bot polling rejimida ishga tushmoqda...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
