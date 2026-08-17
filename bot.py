import telebot
import os
from dotenv import load_dotenv
import yt_dlp
import logging
import sys
import threading
import re

# تنظیم لاگ‌گیری ساده برای دیباگ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# لود متغیرهای محیطی
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    logger.critical("Missing TELEGRAM_BOT_TOKEN! Check your .env file.")
    sys.exit(1)

# راه‌اندازی ربات تلگرام
try:
    bot = telebot.TeleBot(TOKEN)
except Exception as e:
    logger.critical(f"Failed to connect to Telegram API: {e}")
    sys.exit(1)

# --- هندلرها ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "⚡️ آماده دانلود! لینک یوتیوب یا آپارات رو بفرست.")

@bot.message_handler(func=lambda m: _detect_video_url(m.text))
def handle_video_download(message):
    """شناسایی لینک و شروع دانلود"""
    url = _extract_video_url(message.text)
    if not url:
        return bot.reply_to(message, "❌ لینک معتبر پیدا نشد. مطمئن شو لینک مستقیم به یوتیوب یا آپارات اشاره می‌کنه.")
    
    if not _is_allowed_source(url):
        return bot.answer_callback_query(callback_query_id=message.id) # یا ریجکت کن

    bot.send_chat_action(message.chat.id, 'upload_document')
    
    # اجرای دانلود در یک Thread جدا تا بات هنگ نکند
    thread = threading.Thread(target=_process_download, args=(bot, message, url))
    thread.start()

def _is_allowed_source(url):
    """چک کردن دامنه لینک (اختیاری)"""
    allowed_domains = ["youtube.com", "youtu.be", "aparat.com"]
    for domain in allowed_domains:
        if domain in url:
            return True
    return False

def _detect_video_url(text):
    if text.startswith('/'): return False
    video_patterns = [
        r'(https?://)?(www\.)?(youtube\.com|youtu\.be|aparat\.com)/.+',
    ]
    for pattern in video_patterns:
        if re.search(pattern, text):
            return True
    return False

def _extract_video_url(text):
    try:
        # فرض بر اینکه لینک آخرین واژه است یا کل متن لینک است
        words = text.split()
        for word in words:
            if any(x in word.lower() for x in ['http', '.com']):
                return word
    except:
        pass
    return None

def _process_download(b, msg, url):
    try:
        # فرمت‌های پشتیبانی شده
        opts = {
            'quiet': False,
            'noplaylist': True,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', # محدود به mp4 برای تلگرام بهتره
            'outtmpl': '%(title)s.%(ext)s',
            'nooverwrites': False,
            'merge_output_format': 'mp4'
        }
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # پیدا کردن آخرین فایل دانلود شده
            filename = ydl.prepare_filename(info)
            
            b.send_chat_action(msg.chat.id, 'upload_document')
            b.send_document(msg.chat.id, open(filename, 'rb'), filename=f"{info['title'][:50]}.mp4")
            
            # پاکسازی فایل
            if os.path.exists(filename):
                os.remove(filename)
            logger.info(f"Downloaded and deleted: {filename}")
            
    except Exception as e:
        logger.error(e)
        b.send_message(msg.chat.id, f"❌ خطا در دانلود: {e}")
        # تلاش مجدد (ریسک Rate Limit)
        try:
            b.send_message(msg.chat.id, "🔄 دوباره تلاش میکنم..."); 
            _process_download(b, msg, url)
        except:
            logger.warning("Max retries reached or second error.")


if __name__ == '__main__':
    logger.info("Starting Bot with simplified features...")
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        logger.info("Stopping...")