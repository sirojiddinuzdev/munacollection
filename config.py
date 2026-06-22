import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram Bot Token (obtained from @BotFather)
BOT_TOKEN = os.getenv("BOT_TOKEN")

# List of Admin Telegram User IDs (integers).
# In .env it can be a comma-separated list like ADMIN_IDS=123,456
ADMIN_IDS_STR = os.getenv("ADMIN_IDS")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip()]

# Super Admin ID (the owner of the bot, typically the first admin ID in the list)
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", ADMIN_IDS[0] if ADMIN_IDS else 0))

# Telegram Group Chat ID where the ads will be posted.
GROUP_ID = int(os.getenv("GROUP_ID"))

# Contact username of the admin for buyers to reach out if needed.
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")

# Database configuration
DB_FILE = os.getenv("DB_FILE", "sales_bot.db")

# Default card number for payments
DEFAULT_CARD = os.getenv("DEFAULT_CARD")
DEFAULT_CARD_HOLDER = os.getenv("DEFAULT_CARD_HOLDER")
