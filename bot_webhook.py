import os
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from config import BOT_TOKEN
from database import db

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Импортируем все обработчики из bot.py
from bot import (
    start, get_id, admin_panel, handle_message, button_handler,
    handle_manage_search, create_appointment_handler,
    main_menu_keyboard
)


def create_application():
    """Создает и настраивает приложение"""
    application = Application.builder().token(BOT_TOKEN).build()

    # Добавляем обработчики (такой же порядок как в bot.py)
    application.add_handler(create_appointment_handler())
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("id", get_id))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manage_search))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return application


def main():
    """Запуск бота с вебхуками"""
    try:
        application = create_application()

        # Получаем URL от Railway
        railway_url = os.getenv('RAILWAY_STATIC_URL')
        if railway_url:
            # Используем вебхуки на Railway
            port = int(os.getenv('PORT', 8000))
            webhook_url = f"{railway_url}/webhook"

            print(f"Setting webhook to: {webhook_url}")
            application.run_webhook(
                listen="0.0.0.0",
                port=port,
                url_path=BOT_TOKEN,
                webhook_url=f"{webhook_url}/{BOT_TOKEN}",
                allowed_updates=['message', 'callback_query']
            )
        else:
            # Локальная разработка - используем polling
            print("Using polling (local development)")
            application.bot.delete_webhook(drop_pending_updates=True)
            application.run_polling(
                allowed_updates=['message', 'callback_query'],
                timeout=30
            )

    except Exception as e:
        print(f"Ошибка: {e}")
        # Перезапуск через 10 секунд
        import time
        time.sleep(10)
        main()


if __name__ == '__main__':
    main()