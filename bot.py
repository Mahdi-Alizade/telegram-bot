import telebot
import os
from dotenv import load_dotenv

# 1. Load environment variables from .env file
load_dotenv()

# 2. Securely fetch the token
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not BOT_TOKEN:
    print("❌ Error: Missing TELEGRAM_BOT_TOKEN in .env file!")
    exit(1)

# 3. Initialize the bot
try:
    bot = telebot.TeleBot(BOT_TOKEN)
except Exception as e:
    print(f"❌ Failed to initialize bot: {e}")
    exit(1)

# 4. Handler for /start command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    username = message.from_user.username if message.from_user.username else "User"
    bot.send_message(message.chat.id, f"سلام {username}! 👋\nبایت تلگرام شخصی تو با موفقیت لایو شد.")

# 5. Simple fallback handler (Optional - keeps chat alive)
@bot.message_handler(func=lambda m: True)
def echo_all(message):
    bot.send_message(message.chat.id, "🤖 من فعلاً فقط فرمان /start رو میشناسم. ولی آماده توسعه‌ام.")

# 6. Start polling
if __name__ == '__main__':
    print("✅ Bot started successfully. Waiting for updates...")
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")