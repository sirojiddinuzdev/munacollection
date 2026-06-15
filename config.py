import os

# Telegram Bot Token (obtained from @BotFather)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8657142758:AAGUQRm-T_ITFafMBJHzhBNQ2ZhjhuXQ4oE")

# List of Admin Telegram User IDs (integers). Add your own Telegram User ID here.
# You can find your ID using bots like @userinfobot or @raw_data_bot.
ADMIN_IDS = [
    # Replace these with real Telegram User IDs
    8270492933,
]

# Telegram Group Chat ID where the ads will be posted.
# Note: Group IDs usually start with -100 (e.g., -1001234567890).
# The bot must be added to this group as an administrator with permission to post messages.
GROUP_ID = int(os.getenv("GROUP_ID", "-1004475483869"))

# Contact username of the admin for buyers to reach out if needed.
# Must start with @
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@Sirojiddin_Ibn_Baxtiyor")

# Database configuration
DB_FILE = "sales_bot.db"

# Default card number for payments
DEFAULT_CARD = "9860 0803 6807 5935"
DEFAULT_CARD_HOLDER = "SIROJBEK YULDOSHEV"
