import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [5874381142]  # Замените на ваш ID телеграм

# Чтобы узнать свой ID:
# 1. Напишите @userinfobot в Telegram
# 2. Или добавьте эту команду в бота:
async def get_my_id(update, context):
    await update.message.reply_text(f"Ваш ID: {update.message.from_user.id}")