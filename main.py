import os
import sys
import threading
import logging
import telebot
from telebot import types
from dotenv import load_dotenv
import yt_dlp

# تنظیمات لاگ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# بارگذاری متغیرهای محیطی
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    logger.critical("Missing TELEGRAM_BOT_TOKEN! Check your .env file.")
    sys.exit(1)

bot = telebot.TeleBot(TOKEN)

# نگه‌داری وضعیت موقت کاربران
user_states = {}

def get_main_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_yt = types.InlineKeyboardButton("🎬 دانلود از یوتیوب", callback_data="dl_youtube")
    btn_ig = types.InlineKeyboardButton("📸 دانلود از اینستاگرام", callback_data="dl_instagram")
    markup.add(btn_yt, btn_ig)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_states[message.chat.id] = None
    bot.reply_to(
        message,
        "👋 سلام! لطفاً پلتفرم مورد نظر برای دانلود را انتخاب کنید:",
        reply_markup=get_main_keyboard()
    )

@bot.callback_query_handler(func=lambda call: call.data in ["dl_youtube", "dl_instagram"])
def handle_callback(call):
    if call.data == "dl_youtube":
        user_states[call.message.chat.id] = "waiting_youtube"
        bot.send_message(call.message.chat.id, "🔗 لطفاً لینک ویدیوی **یوتیوب** را ارسال کنید:")
    elif call.data == "dl_instagram":
        user_states[call.message.chat.id] = "waiting_instagram"
        bot.send_message(call.message.chat.id, "🔗 لطفاً لینک پست/ریلز **اینستاگرام** را ارسال کنید:")
    
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda m: not m.text.startswith('/'))
def handle_incoming_link(message):
    chat_id = message.chat.id
    current_state = user_states.get(chat_id)
    url = message.text.strip()

    if not current_state:
        # تشخیص خودکار در صورت عدم انتخاب دکمه
        if "youtube.com" in url or "youtu.be" in url:
            current_state = "waiting_youtube"
        elif "instagram.com" in url:
            current_state = "waiting_instagram"
        else:
            return bot.reply_to(message, "لطفاً ابتدا یک گزینه را انتخاب کنید:", reply_markup=get_main_keyboard())

    # اعتبارسنجی اولیه لینک بر اساس انتخاب
    if current_state == "waiting_youtube" and not any(x in url for x in ["youtube.com", "youtu.be"]):
        return bot.reply_to(message, "❌ لینک ارسالی مربوط به یوتیوب نیست. لطفاً مجدد تلاش کنید.")
    
    if current_state == "waiting_instagram" and "instagram.com" not in url:
        return bot.reply_to(message, "❌ لینک ارسالی مربوط به اینستاگرام نیست. لطفاً مجدد تلاش کنید.")

    # ریست کردن وضعیت کاربر
    user_states[chat_id] = None

    bot.send_message(chat_id, "⏳ در حال دریافت و پردازش ویدیو... لطفاً شکیبا باشید.")
    bot.send_chat_action(chat_id, 'upload_video')

    thread = threading.Thread(target=_process_download, args=(bot, message, url))
    thread.start()

def _process_download(b, msg, url):
    ydl_opts = {
        'quiet': True,
        'noplaylist': True,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': f'downloads/{msg.chat.id}_%(id)s.%(ext)s',
        'merge_output_format': 'mp4',
        'max_filesize': 50 * 1024 * 1024  # محدودیت ۵۰ مگابایت استاندارد تلگرام
    }

    try:
        os.makedirs('downloads', exist_ok=True)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if not filename.endswith('.mp4'):
                filename = os.path.splitext(filename)[0] + '.mp4'

        b.send_chat_action(msg.chat.id, 'upload_video')
        with open(filename, 'rb') as video_file:
            b.send_video(
                msg.chat.id,
                video_file,
                caption=f"🎬 {info.get('title', 'ویدیو')[:100]}",
                reply_markup=get_main_keyboard()
            )

        if os.path.exists(filename):
            os.remove(filename)

    except Exception as e:
        logger.error(f"Download error: {e}")
        b.send_message(
            msg.chat.id,
            "❌ دانلود ناموفق بود. ممکن است حجم ویدیو بیش از ۵۰ مگابایت، پیج خصوصی یا لینک نامعتبر باشد.",
            reply_markup=get_main_keyboard()
        )

if __name__ == '__main__':
    logger.info("Bot is running...")
    bot.infinity_polling()