import telebot
from telebot import types
from flask import Flask, request
import os
import re

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = 'AIzaSyDSGiFECuvVvKK5mlyhhbUmZszk2CwcIVQ'
# Эту ссылку мы получим ПОСЛЕ деплоя (сохрани код, задеплой, получи ссылку и вставь сюда)
# Пример: https://my-bot-service-uc.a.run.app
WEBHOOK_URL = 'https://grishavpn.onrender.com' 

ADMIN_ID = 7769226977
CHANNEL_ID = -1003423217810
CHANNEL_USERNAME = "@YouVPNs" # Для отображения в тексте

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Хранилище состояний (в оперативной памяти)
user_data = {}

APPS_LINKS = {
    "Happ": "https://play.google.com/store/apps/details?id=com.happ.proxy",
    "Shadowsocks": "https://play.google.com/store/apps/details?id=com.github.shadowsocks",
    "DarkTunnel": "https://play.google.com/store/apps/details?id=com.darktunnel.app",
    "Npv Tunnel": "https://play.google.com/store/apps/details?id=com.npv.tunnel",
    "V2Ray": "https://play.google.com/store/apps/details?id=com.v2ray.ang"
}

FLAGS_TO_RUS = {
    "🇳🇱": "Нидерланды", "🇺🇸": "США", "🇩🇪": "Германия", "🇬🇧": "Великобритания",
    "🇫🇷": "Франция", "🇹🇷": "Турция", "🇷🇺": "Россия", "🇺🇦": "Украина",
    "🇵🇱": "Польша", "🇫🇮": "Финляндия", "🇸🇪": "Швеция", "🇨🇦": "Канада",
    "🇯🇵": "Япония", "🇰🇿": "Казахстан", "🇪🇪": "Эстония"
}

# --- WEBHOOK SERVER ---
@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL + "/" + BOT_TOKEN)
    return "Webhook set!", 200

# --- ЛОГИКА БОТА ---

def is_admin(user_id):
    return user_id == ADMIN_ID

@bot.message_handler(commands=['start'])
def start(message):
    if not is_admin(message.from_user.id): return
    bot.send_message(message.chat.id, "👋 Привет! Жду конфиг (текст) или файл (.npvt).")
    user_data[message.chat.id] = {}

# 1. Прием кода/файла
@bot.message_handler(content_types=['text', 'document'])
def handle_input(message):
    if not is_admin(message.from_user.id): return
    
    # Очистка старых данных
    user_data[message.chat.id] = {}
    
    app_detected = "Неизвестно"
    
    if message.document:
        if message.document.file_name.endswith('.npvt'):
            app_detected = "Npv Tunnel"
            user_data[message.chat.id]['is_file'] = True
            user_data[message.chat.id]['file_id'] = message.document.file_id
            user_data[message.chat.id]['filename'] = message.document.file_name
        else:
            bot.reply_to(message, "⚠️ Только файлы .npvt")
            return
    elif message.text:
        code = message.text.strip()
        user_data[message.chat.id]['is_file'] = False
        user_data[message.chat.id]['code'] = code
        
        if code.startswith("happ://"): app_detected = "Happ"
        elif code.startswith("ss://"): app_detected = "Shadowsocks"
        elif code.startswith("darktunnel:/"): app_detected = "DarkTunnel"
        elif code.startswith("vless://") or code.startswith("vmess://"): app_detected = "V2Ray"

    user_data[message.chat.id]['app'] = app_detected
    
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add("Да", "Нет")
    msg = bot.send_message(message.chat.id, f"Приложение: <b>{app_detected}</b>. Верно?", parse_mode="HTML", reply_markup=markup)
    bot.register_next_step_handler(msg, confirm_app)

# 2. Подтверждение приложения
def confirm_app(message):
    if message.text.lower() == "да":
        ask_quality(message)
    else:
        msg = bot.send_message(message.chat.id, "Введи название вручную:", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, lambda m: [user_data[m.chat.id].update({'app': m.text}), ask_quality(m)])

# 3. Оценка качества (НОВОЕ)
def ask_quality(message):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.row("🟢 Апупенный", "🟡 Средний", "🔴 Плохой")
    msg = bot.send_message(message.chat.id, "Какое качество связи?", reply_markup=markup)
    bot.register_next_step_handler(msg, save_quality)

def save_quality(message):
    text = message.text
    if "Апупенный" in text:
        q_text, q_emoji = "Отличная", "🚀"
    elif "Средний" in text:
        q_text, q_emoji = "Средняя", "⚖️"
    elif "Плохой" in text:
        q_text, q_emoji = "Низкая", "🐢"
    else:
        q_text, q_emoji = "Неизвестно", "❓"
        
    user_data[message.chat.id]['quality_text'] = q_text
    user_data[message.chat.id]['quality_emoji'] = q_emoji
    
    ask_limit(message)

# 4. Лимит или Дата
def ask_limit(message):
    msg = bot.send_message(message.chat.id, "Введи лимит (напр. '50GB') ИЛИ дату (напр. '12.03.26'). Если хз, пиши '?'.", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, save_limit)

def save_limit(message):
    text = message.text.strip()
    
    if text == "?":
        limit_str = "♾️ <b>Лимит:</b> Неизвестно"
    # Проверка на дату (наличие точек и цифр, например 12.05.2024)
    elif re.search(r'\d{1,2}\.\d{1,2}', text):
        limit_str = f"⏳ <b>Работает до:</b> {text}"
    else:
        limit_str = f"📦 <b>Лимит трафика:</b> {text}"
        
    user_data[message.chat.id]['limit_str'] = limit_str
    
    msg = bot.send_message(message.chat.id, "Кидай флаг страны (один эмодзи):")
    bot.register_next_step_handler(msg, finish_post)

# 5. Публикация
def finish_post(message):
    flag = message.text.strip()
    country = FLAGS_TO_RUS.get(flag, flag) # Если нет в базе, оставит как есть
    
    data = user_data[message.chat.id]
    app_name = data.get('app')
    dl_link = APPS_LINKS.get(app_name, "https://play.google.com/store/apps")
    
    # --- НОВЫЙ ДИЗАЙН ---
    post_header = f"<b>🛡 {app_name} VPN</b>"
    
    info_block = (
        f"<b>🌍 Страна:</b> {flag} {country}\n"
        f"{data['limit_str']}\n"
        f"<b>⚡ Скорость:</b> {data['quality_emoji']} {data['quality_text']}\n"
        f"<b>📲 Приложение:</b> <a href='{dl_link}'>Скачать</a>\n\n"
        f"🔗 <b>Канал:</b> {CHANNEL_USERNAME}"
    )

    try:
        if data.get('is_file'):
            caption = f"{post_header}\n\n{info_block}"
            bot.send_document(CHANNEL_ID, data['file_id'], caption=caption, parse_mode="HTML")
        else:
            # Текстовый код
            full_text = f"{post_header}\n\n<code>{data['code']}</code>\n\n{info_block}"
            bot.send_message(CHANNEL_ID, full_text, parse_mode="HTML", disable_web_page_preview=True)
            
        bot.send_message(message.chat.id, "✅ Опубликовано!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

if __name__ == "__main__":
    # Локальный запуск не сработает корректно без туннеля, 
    # этот код для запуска на сервере через Gunicorn

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
