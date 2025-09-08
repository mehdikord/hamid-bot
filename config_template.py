from zoneinfo import ZoneInfo

# Telegram Bot API token (from @BotFather)
# Get your bot token from @BotFather on Telegram
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# Role definitions: list user IDs for managers and sellers
# Replace with actual Telegram user IDs
MANAGER_IDS = [123456789]        # <-- replace with actual manager Telegram ID(s)
SELLER_IDS = [123456789]         # <-- replace with actual seller Telegram ID(s)

# Optional: Mapping of user IDs to names for display in reports
# Add your team members' IDs and names here
USER_NAMES = {
    123456789: "نام مدیر",
    987654321: "نام فروشنده",
    # Add more team members as needed
}

# Internal group chat ID for posting team reports/announcements 
# Must be a Telegram group ID (usually negative number)
# To get group ID: add @userinfobot to your group and send /start
GROUP_CHAT_ID = -1234567890    # <-- replace with your group chat ID

# Timezone for scheduling and time display (use Olson timezone string)
# Common options: "Asia/Tehran", "UTC", "America/New_York", "Europe/London"
TIMEZONE = "Asia/Tehran"
TZ = ZoneInfo(TIMEZONE)

# Instructions:
# 1. Copy this file to config.py
# 2. Replace all placeholder values with your actual data
# 3. Never commit config.py to version control (it's already in .gitignore)
# 4. Keep your bot token and user IDs secure
