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

# لود توکن از محیط محرمانه
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    logger.critical("Missing TELEGRAM_BOT_TOKEN! Check your .env file.")
    sys.exit(1)

bot = telebot.TeleBot(TOKEN)

# ساخت دکمه‌های عملیات برای لینک ارسالی
def get_action_keyboard(url):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_video = types.InlineKeyboardButton("🎬 دانلود ویدیو", callback_data="act_video")
    btn_audio = types.InlineKeyboardButton("🎧 استخراج صدا (Audio)", callback_data="act_audio")
    btn_thumb = types.InlineKeyboardButton("🖼 دریافت کاور (Thumb)", callback_data="act_thumb")
    markup.add(btn_video, btn_audio)
    markup.add(btn_thumb)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(
        message,
        "👋 سلام! لینک ویدیوی یوتیوب یا اینستاگرام را ارسال کنید تا گزینه‌های دانلود نمایش داده شوند."
    )

@bot.message_handler(func=lambda m: not m.text.startswith('/'))
def handle_link_input(message):
    url = message.text.strip()
    
    # بررسی ساده معتبر بودن آدرس
    if not ("youtube.com" in url or "youtu.be" in url or "instagram.com" in url):
        return bot.reply_to(message, "❌ لطفاً یک لینک معتبر از یوتیوب یا اینستاگرام ارسال کنید.")

    # ارسال منوی انتخاب نوع دانلود
    bot.reply_to(
        message,
        f"🔗 لینک دریافت شد.\nلطفاً نوع خروجی مورد نظر را انتخاب کنید:\n`{url}`",
        reply_markup=get_action_keyboard(url),
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data in ["act_video", "act_audio", "act_thumb"])
def handle_action_choice(call):
    bot.answer_callback_query(call.id)
    
    # استخراج لینک از متن پیام قبلی
    original_text = call.message.text
    url = None
    for word in original_text.split():
        if "http://" in word or "https://" in word:
            url = word.strip("`")
            break
            
    if not url:
        return bot.edit_message_text("❌ لینک نامعتبر یا منقضی شده است.", call.message.chat.id, call.message.message_id)

    action_type = call.data
    bot.edit_message_text("⏳ در حال پردازش و استخراج فایل... لطفاً شکیبا باشید.", call.message.chat.id, call.message.message_id)
    
    thread = threading.Thread(target=_process_request, args=(bot, call.message, url, action_type))
    thread.start()

def _process_request(b, msg, url, action_type):
    os.makedirs('downloads', exist_ok=True)
    chat_id = msg.chat.id

    try:
        if action_type == "act_thumb":
            # دریافت مستقیم تصویر کاور بدون نیاز به دانلود کل ویدیو
            ydl_opts = {'quiet': True, 'skip_download': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                thumb_url = info.get('thumbnail')
                
            if thumb_url:
                b.send_photo(chat_id, thumb_url, caption=f"🖼 کاور ویدیوی: {info.get('title', '')[:80]}")
            else:
                b.send_message(chat_id, "❌ تصویری برای کاور این ویدیو یافت نشد.")
            return

        elif action_type == "act_audio":
            b.send_chat_action(chat_id, 'upload_voice')
            # دانلود فقط با فرمت صدا
            ydl_opts = {
                'quiet': True,
                'noplaylist': True,
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
                'outtmpl': f'downloads/{chat_id}_%(id)s.%(ext)s',
                'max_filesize': 50 * 1024 * 1024
            }
        else:
            b.send_chat_action(chat_id, 'upload_video')
            # دانلود ویدیو
            ydl_opts = {
                'quiet': True,
                'noplaylist': True,
                'format': 'best[ext=mp4]/best',
                'outtmpl': f'downloads/{chat_id}_%(id)s.%(ext)s',
                'max_filesize': 50 * 1024 * 1024
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        # ارسال فایل به تلگرام
        if action_type == "act_audio":
            with open(filename, 'rb') as audio_file:
                b.send_audio(chat_id, audio_file, title=info.get('title', 'Audio')[:60])
        else:
            with open(filename, 'rb') as video_file:
                b.send_video(chat_id, video_file, caption=f"🎬 {info.get('title', 'Video')[:80]}")

        # حذف فایل موقت
        if os.path.exists(filename):
            os.remove(filename)

    except Exception as e:
        logger.error(f"Execution error: {e}")
        b.send_message(chat_id, "❌ پردازش با خطا مواجه شد. (لینک نامعتبر، پیج خصوصی یا حجم فایل بالای ۵۰ مگابایت است)")

if __name__ == '__main__':
    logger.info("Bot is running with audio/thumb extraction...")
    bot.infinity_polling()