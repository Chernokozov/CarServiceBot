import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import re
import sqlite3

from config import BOT_TOKEN
from database import db
from states import AppointmentState, user_data_store

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


# ==================== ГЛАВНОЕ МЕНЮ ====================

def main_menu_keyboard():
    keyboard = [
        [KeyboardButton("✅ Записаться на услугу")],
        [KeyboardButton("📋 Мои записи"), KeyboardButton("ℹ️ Об услугах")],
        [KeyboardButton("📞 Контакты")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def start(update, context):
    """Обработчик команды /start"""
    user = update.message.from_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! 🚗\n"
        "Добро пожаловать в автосервис 'АвтоМастер'!\n\n"
        "Выберите действие из меню ниже:",
        reply_markup=main_menu_keyboard()
    )


async def handle_message(update, context):
    """Обработчик текстовых сообщений для главного меню"""
    text = update.message.text

    if text == "✅ Записаться на услугу":
        # Запись обрабатывается через ConversationHandler
        await update.message.reply_text("Пожалуйста, используйте кнопку 'Записаться на услугу' для начала записи.")
    elif text == "📋 Мои записи":
        await show_my_appointments(update, context)
    elif text == "ℹ️ Об услугах":
        await show_services_info(update, context)
    elif text == "📞 Контакты":
        await show_contacts(update, context)
    else:
        await update.message.reply_text("Пожалуйста, используйте меню ниже 👇", reply_markup=main_menu_keyboard())


async def show_my_appointments(update, context):
    """Показывает записи пользователя"""
    user_id = update.message.from_user.id
    appointments = db.get_user_appointments(user_id)

    if not appointments:
        await update.message.reply_text("📋 У вас пока нет активных записей.")
        return

    text = "📋 **Ваши записи:**\n\n"

    for appt in appointments[:5]:  # Показываем последние 5 записей
        status_icon = "✅" if appt['status'] == 'confirmed' else "⏳"
        status_icon = "❌" if appt['status'] == 'cancelled' else status_icon

        status_text = {
            'pending': 'Ожидает подтверждения',
            'confirmed': 'Подтверждена',
            'cancelled': 'Отменена'
        }

        text += f"{status_icon} **Запись #{appt['id']}**\n"
        text += f"🚗 Услуга: {appt['service_name']}\n"
        text += f"📅 Дата: {appt['appointment_date']}\n"
        text += f"🕒 Время: {appt['appointment_time']}\n"
        text += f"🎯 Статус: {status_text[appt['status']]}\n"

        if appt['comment']:
            text += f"💬 Комментарий: {appt['comment']}\n"

        text += "\n" + "─" * 30 + "\n\n"

    if len(appointments) > 5:
        text += f"📄 Показано 5 из {len(appointments)} записей"

    await update.message.reply_text(text, parse_mode='Markdown')


async def show_services_info(update, context):
    """Информация об услугах"""
    services_text = """
🛢 **Техническое обслуживание**:
- Замена масла и фильтров
- Проверка жидкостей
- Общий осмотр

🔧 **Ремонт двигателя**:
- Диагностика и ремонт
- Замена комплектующих
- Чип-тюнинг

🛞 **Шиномонтаж**:
- Сезонная замена шин
- Балансировка
- Ремонт проколов

🎨 **Кузовные работы**:
- Покраска
- Ремонт вмятин
- Полировка

⚡ **Диагностика**:
- Компьютерная диагностика
- Проверка электроники
- Тест-драйв
"""
    await update.message.reply_text(services_text, parse_mode='Markdown')


async def show_contacts(update, context):
    """Показывает контакты"""
    contacts_text = """
📞 **Контакты автосервиса**:

📍 Адрес: г. Москва, ул. Автомобильная, д. 15
📱 Телефон: +7 (495) 123-45-67
🕒 Время работы: Пн-Пт 9:00-20:00, Сб-Вс 10:00-18:00

🚗 Как нас найти:
- 5 минут от метро "Автозаводская"
- Есть парковка для клиентов
"""
    await update.message.reply_text(contacts_text, parse_mode='Markdown')


# ==================== СИСТЕМА ЗАПИСИ ====================

async def start_appointment(update, context):
    """Начинает процесс записи"""
    user = update.message.from_user
    user_id = user.id

    # Инициализируем данные пользователя
    user_data_store[user_id] = {
        'step': AppointmentState.SELECT_SERVICE,
        'user_info': {
            'user_id': user_id,
            'username': user.username,
            'first_name': user.first_name
        }
    }

    # Добавляем пользователя в БД
    db.add_user(user_id, user.username, user.first_name)

    # Показываем выбор услуги
    services = db.get_services()
    keyboard = []
    for service in services:
        keyboard.append([
            InlineKeyboardButton(
                f"{service['name']} ({service['price_range']})",
                callback_data=f"select_service_{service['id']}"
            )
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🚗 Выберите услугу:",
        reply_markup=reply_markup
    )

    return AppointmentState.SELECT_SERVICE


async def select_service(update, context):
    """Обработчик выбора услуги"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    service_id = int(query.data.replace("select_service_", ""))

    # Получаем информацию об услуге
    services = db.get_services()
    selected_service = next((s for s in services if s['id'] == service_id), None)

    if selected_service:
        user_data_store[user_id]['service'] = selected_service
        user_data_store[user_id]['step'] = AppointmentState.SELECT_DATE

        await query.edit_message_text(
            f"✅ Выбрана услуга: {selected_service['name']}\n"
            f"📝 {selected_service['description']}\n\n"
            "Теперь выберите дату:"
        )
        await show_date_selection(query.message, user_id)

    return AppointmentState.SELECT_DATE


async def show_date_selection(message, user_id):
    """Показывает выбор даты"""
    # Генерируем даты на ближайшие 7 дней
    dates = []
    keyboard = []

    for i in range(1, 8):
        date = datetime.now() + timedelta(days=i)
        if date.weekday() < 5:  # Только будни (0-4 = Пн-Пт)
            date_str = date.strftime("%d.%m.%Y")
            weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][date.weekday()]
            dates.append((date_str, f"{date_str} ({weekday})"))

    for i in range(0, len(dates), 2):
        row = []
        for j in range(2):
            if i + j < len(dates):
                date_str, display_text = dates[i + j]
                row.append(InlineKeyboardButton(display_text, callback_data=f"select_date_{date_str}"))
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text("📅 Выберите дату:", reply_markup=reply_markup)


async def select_date(update, context):
    """Обработчик выбора даты"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    date_str = query.data.replace("select_date_", "")

    user_data_store[user_id]['appointment_date'] = date_str
    user_data_store[user_id]['step'] = AppointmentState.SELECT_TIME

    await query.edit_message_text(f"📅 Выбрана дата: {date_str}")
    await show_time_selection(query.message, user_id, date_str)

    return AppointmentState.SELECT_TIME


async def show_time_selection(message, user_id, date_str):
    """Показывает выбор времени"""
    available_slots = db.get_available_time_slots(date_str)

    if not available_slots:
        await message.reply_text(
            "❌ На эту дату нет свободных слотов. Пожалуйста, выберите другую дату."
        )
        await show_date_selection(message, user_id)
        return AppointmentState.SELECT_DATE

    keyboard = []
    for i in range(0, len(available_slots), 3):
        row = []
        for j in range(3):
            if i + j < len(available_slots):
                time_slot = available_slots[i + j]
                row.append(InlineKeyboardButton(time_slot, callback_data=f"select_time_{time_slot}"))
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text("🕒 Выберите время:", reply_markup=reply_markup)


async def select_time(update, context):
    """Обработчик выбора времени"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    time_slot = query.data.replace("select_time_", "")

    user_data_store[user_id]['appointment_time'] = time_slot
    user_data_store[user_id]['step'] = AppointmentState.CAR_BRAND

    await query.edit_message_text(f"🕒 Выбрано время: {time_slot}")
    await query.message.reply_text("🚗 Введите марку вашего автомобиля:\n(Например: Toyota, BMW, Lada)")

    return AppointmentState.CAR_BRAND


async def get_car_brand(update, context):
    """Получает марку автомобиля"""
    user_id = update.message.from_user.id
    car_brand = update.message.text

    user_data_store[user_id]['car_brand'] = car_brand
    user_data_store[user_id]['step'] = AppointmentState.CAR_MODEL

    await update.message.reply_text("📝 Введите модель автомобиля:\n(Например: Camry, X5, Vesta)")

    return AppointmentState.CAR_MODEL


async def get_car_model(update, context):
    """Получает модель автомобиля"""
    user_id = update.message.from_user.id
    car_model = update.message.text

    user_data_store[user_id]['car_model'] = car_model
    user_data_store[user_id]['step'] = AppointmentState.CAR_YEAR

    await update.message.reply_text("📅 Введите год выпуска автомобиля:\n(Например: 2018)")

    return AppointmentState.CAR_YEAR


async def get_car_year(update, context):
    """Получает год выпуска автомобиля"""
    user_id = update.message.from_user.id
    car_year = update.message.text

    # Проверяем, что год введен корректно
    if not car_year.isdigit() or len(car_year) != 4 or int(car_year) < 1990 or int(car_year) > datetime.now().year + 1:
        await update.message.reply_text("❌ Пожалуйста, введите корректный год (4 цифры, например: 2018)")
        return AppointmentState.CAR_YEAR

    user_data_store[user_id]['car_year'] = int(car_year)
    user_data_store[user_id]['step'] = AppointmentState.PHONE

    await update.message.reply_text(
        "📱 Введите ваш номер телефона для связи:\n"
        "(Например: +79161234567 или 9161234567)"
    )

    return AppointmentState.PHONE


async def get_phone(update, context):
    """Получает номер телефона"""
    user_id = update.message.from_user.id
    phone = update.message.text

    # Простая валидация телефона
    phone_clean = re.sub(r'[^\d+]', '', phone)
    if len(phone_clean) < 10:
        await update.message.reply_text("❌ Пожалуйста, введите корректный номер телефона")
        return AppointmentState.PHONE

    user_data_store[user_id]['phone'] = phone_clean
    user_data_store[user_id]['step'] = AppointmentState.COMMENT

    await update.message.reply_text(
        "💬 Если есть дополнительные пожелания или комментарии, введите их:\n"
        "(Или отправьте '-' чтобы пропустить)"
    )

    return AppointmentState.COMMENT


async def get_comment(update, context):
    """Получает комментарий и показывает подтверждение"""
    user_id = update.message.from_user.id
    comment = update.message.text

    if comment == '-':
        comment = ""

    user_data_store[user_id]['comment'] = comment
    user_data_store[user_id]['step'] = AppointmentState.CONFIRM

    # Формируем сводку для подтверждения
    data = user_data_store[user_id]
    summary = f"""
📋 **Проверьте данные записи:**

🚗 Услуга: {data['service']['name']}
📅 Дата: {data['appointment_date']}
🕒 Время: {data['appointment_time']}
🎯 Автомобиль: {data['car_brand']} {data['car_model']} ({data['car_year']} г.)
📱 Телефон: {data['phone']}
"""
    if comment:
        summary += f"💬 Комментарий: {comment}"

    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить запись", callback_data="confirm_appointment")],
        [InlineKeyboardButton("❌ Отменить", callback_data="cancel_appointment")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(summary, reply_markup=reply_markup, parse_mode='Markdown')

    return AppointmentState.CONFIRM


async def confirm_appointment(update, context):
    """Подтверждает запись"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = user_data_store.get(user_id)

    if not data:
        await query.edit_message_text("❌ Произошла ошибка. Начните запись заново.")
        return ConversationHandler.END

    # Сохраняем запись в БД
    appointment_id = db.create_appointment(
        user_id=user_id,
        service_id=data['service']['id'],
        service_name=data['service']['name'],
        appointment_date=data['appointment_date'],
        appointment_time=data['appointment_time'],
        car_brand=data['car_brand'],
        car_model=data['car_model'],
        car_year=data['car_year'],
        phone=data['phone'],
        comment=data.get('comment', '')
    )

    if appointment_id:
        # Обновляем информацию об авто пользователя
        db.update_user_car_info(
            user_id, data['car_brand'], data['car_model'], data['car_year'], data['phone']
        )

        # Очищаем временные данные
        if user_id in user_data_store:
            del user_data_store[user_id]

        success_text = f"""
✅ **Запись успешно создана!**

Номер записи: #{appointment_id}
🚗 Услуга: {data['service']['name']}
📅 Дата: {data['appointment_date']}
🕒 Время: {data['appointment_time']}

Мы ждем вас в автосервисе!
📞 Для переноса или отмены звоните: +7 (495) 123-45-67
        """

        await query.edit_message_text(success_text, parse_mode='Markdown')
    else:
        await query.edit_message_text("❌ Произошла ошибка при создании записи. Попробуйте позже.")

    return ConversationHandler.END


async def cancel_appointment(update, context):
    """Отменяет процесс записи"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if user_id in user_data_store:
        del user_data_store[user_id]

    await query.edit_message_text("❌ Запись отменена.")
    return ConversationHandler.END


async def cancel_conversation(update, context):
    """Отменяет диалог по команде /cancel"""
    user_id = update.message.from_user.id
    if user_id in user_data_store:
        del user_data_store[user_id]

    await update.message.reply_text(
        "Диалог прерван.",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END


# Создаем ConversationHandler для системы записи
def create_appointment_handler():
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^✅ Записаться на услугу$"), start_appointment)],
        states={
            AppointmentState.SELECT_SERVICE: [CallbackQueryHandler(select_service, pattern="^select_service_")],
            AppointmentState.SELECT_DATE: [CallbackQueryHandler(select_date, pattern="^select_date_")],
            AppointmentState.SELECT_TIME: [CallbackQueryHandler(select_time, pattern="^select_time_")],
            AppointmentState.CAR_BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_car_brand)],
            AppointmentState.CAR_MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_car_model)],
            AppointmentState.CAR_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_car_year)],
            AppointmentState.PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            AppointmentState.COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_comment)],
            AppointmentState.CONFIRM: [
                CallbackQueryHandler(confirm_appointment, pattern="^confirm_appointment$"),
                CallbackQueryHandler(cancel_appointment, pattern="^cancel_appointment$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        map_to_parent={
            ConversationHandler.END: ConversationHandler.END
        }
    )


def test_database_connection():
    """Тестирует подключение к базе данных"""
    try:
        # Просто обращаемся к базе - это вызовет инициализацию
        services = db.get_services()
        logging.info(f"✅ Database test successful. Found {len(services)} services.")
        return True
    except Exception as e:
        logging.error(f"❌ Database test failed: {e}")
        return False

# ==================== ОБРАБОТЧИК INLINE-КНОПОК ====================
async def button_handler(update, context):
    """Обработчик нажатий на inline-кнопки"""
    query = update.callback_query
    await query.answer()

    # Игнорируем кнопки системы записи
    if query.data.startswith(
            ('select_service_', 'select_date_', 'select_time_', 'confirm_appointment', 'cancel_appointment')):
        return

    # Обработка админ-кнопок
    if query.data.startswith('admin_'):
        if query.data == 'admin_today':
            await admin_today(update, context)
        elif query.data == 'admin_all':
            await admin_all(update, context)
        elif query.data == 'admin_stats':
            await admin_stats(update, context)
        elif query.data == 'admin_back':
            await admin_back(update, context)
        elif query.data == 'admin_close':
            await admin_close(update, context)
        elif query.data == 'admin_manage':
            await admin_manage(update, context)
        elif query.data == 'admin_manage_id':
            await admin_manage_id(update, context)
        elif query.data == 'admin_today_manage':
            await admin_today_manage(update, context)
        return

    # Обработка кнопок управления
    if query.data.startswith(('confirm_', 'cancel_', 'manage_')):
        await handle_management_action(update, context)
        return

    await query.edit_message_text("Эта функция в разработке... 🛠")

# ==================== ПОЛУЧЕНИЕ ID ====================

async def get_id(update, context):
    """Показывает ID пользователя"""
    user_id = update.message.from_user.id
    await update.message.reply_text(
        f"🆔 Ваш ID: `{user_id}`\n\n"
        "Сообщите этот ID разработчику для добавления в админы.",
        parse_mode='Markdown'
    )


# ==================== АДМИН-ПАНЕЛЬ ====================

from config import ADMIN_IDS


def is_admin(user_id):
    return user_id in ADMIN_IDS
async def safe_send_message(chat_id, text, context, reply_markup=None, parse_mode='Markdown'):
    """Безопасная отправка сообщений с обработкой ошибок форматирования"""
    try:
        if parse_mode:
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup
            )
    except Exception as e:
        # Если ошибка форматирования, отправляем без Markdown
        if "Can't parse entities" in str(e):
            text_plain = text.replace('*', '').replace('_', '').replace('`', '')
            await context.bot.send_message(
                chat_id=chat_id,
                text=text_plain,
                reply_markup=reply_markup
            )
        else:
            raise e

async def admin_panel(update, context):
    """Показывает админ-панель"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет доступа к админ-панели.")
        return

    # Статистика
    today = datetime.now().strftime("%d.%m.%Y")
    today_appointments = db.get_appointments_by_date(today)
    today_count = len(today_appointments)

    keyboard = [
        [InlineKeyboardButton("📅 Записи на сегодня", callback_data="admin_today")],
        [InlineKeyboardButton("📋 Все записи", callback_data="admin_all")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("❌ Закрыть админку", callback_data="admin_close")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"""
👨‍💼 **Админ-панель**

📊 Сегодня записей: {today_count}

Выберите действие:
"""
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def admin_today(update, context):
    """Показывает записи на сегодня"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ У вас нет доступа.")
        return

    today = datetime.now().strftime("%d.%m.%Y")
    appointments = db.get_appointments_by_date(today)

    if not appointments:
        text = "📅 На сегодня записей нет."
    else:
        text = f"📅 **Записи на сегодня ({today})**\n\n"

        for i, appt in enumerate(appointments, 1):
            status_icon = "✅" if appt['status'] == 'confirmed' else "⏳"
            text += f"{i}. {status_icon} {appt['appointment_time']}\n"
            text += f"   🚗 {appt['service_name']}\n"
            text += f"   👤 {appt['car_brand']} {appt['car_model']}\n"
            text += f"   📞 {appt['phone']}\n"
            text += f"   📝 ID: #{appt['id']}\n\n"

    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin_today")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def admin_all(update, context):
    """Показывает все активные записи с кнопками управления"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ У вас нет доступа.")
        return

    appointments = db.get_all_appointments(days=7)
    active_appointments = [a for a in appointments if a['status'] != 'cancelled']

    if not active_appointments:
        text = "📋 Активных записей нет."
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="admin_all")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")]
        ]
    else:
        text = "📋 *Все активные записи (7 дней)*\n\n"

        current_date = None
        for appt in active_appointments:
            if appt['appointment_date'] != current_date:
                current_date = appt['appointment_date']
                weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][
                    datetime.strptime(current_date, "%d.%m.%Y").weekday()
                ]
                text += f"\n📅 *{current_date} ({weekday})*\n"

            status_icon = "✅" if appt['status'] == 'confirmed' else "⏳"
            text += f"{status_icon} *{appt['appointment_time']}* - {appt['service_name']}\n"
            text += f"   👤 {appt['first_name']} | 🚗 {appt['car_brand']} {appt['car_model']}\n"
            text += f"   📞 {appt['phone']} | ID: #{appt['id']}\n"

            # Добавляем кнопки управления (просто текст, не Markdown)
            if appt['status'] == 'pending':
                text += "   ⏳ Ожидает подтверждения\n"
            elif appt['status'] == 'confirmed':
                text += "   ✅ Подтверждена\n"

            text += "\n"

        keyboard = [
            [
                InlineKeyboardButton("🔄 Обновить", callback_data="admin_all"),
                InlineKeyboardButton("📋 Управление", callback_data="admin_manage")
            ],
            [InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def admin_manage(update, context):
    """Раздел управления записями"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ У вас нет доступа.")
        return

    text = """
🔧 **Управление записями**

Выберите действие:
"""
    keyboard = [
        [InlineKeyboardButton("📝 Управление по ID", callback_data="admin_manage_id")],
        [InlineKeyboardButton("📅 Записи на сегодня", callback_data="admin_today_manage")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def admin_manage_id(update, context):
    """Управление записью по ID"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ У вас нет доступа.")
        return

    # Сохраняем состояние поиска для управления
    context.user_data['admin_manage_search'] = True

    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="admin_manage")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🔧 **Управление записью**\n\n"
        "Введите ID записи для управления:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def admin_today_manage(update, context):
    """Управление записями на сегодня с кнопками"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ У вас нет доступа.")
        return

    today = datetime.now().strftime("%d.%m.%Y")
    appointments = db.get_appointments_by_date(today)

    if not appointments:
        text = "📅 На сегодня записей нет."
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="admin_manage")]]
    else:
        text = f"🔧 **Управление записями на сегодня ({today})**\n\n"

        for appt in appointments:
            status_icon = "✅" if appt['status'] == 'confirmed' else "⏳"
            text += f"{status_icon} **{appt['appointment_time']}** - {appt['service_name']}\n"
            text += f"   👤 {appt['first_name']} | 🚗 {appt['car_brand']}\n"
            text += f"   📞 {appt['phone']} | ID: #{appt['id']}\n"

            # Кнопки для каждой записи
            if appt['status'] == 'pending':
                text += "   ⏳ Ожидает подтверждения\n"
            elif appt['status'] == 'confirmed':
                text += "   ✅ Подтверждена\n"

            text += "\n"

        keyboard = []
        for appt in appointments:
            btn_text = f"#{appt['id']} {appt['appointment_time']} - {appt['first_name']}"
            keyboard.append([
                InlineKeyboardButton(btn_text, callback_data=f"manage_{appt['id']}")
            ])

        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="admin_manage")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def handle_manage_search(update, context):
    """Обработчик поиска записи для управления"""
    user_id = update.message.from_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет доступа.")
        return

    if not context.user_data.get('admin_manage_search'):
        return

    try:
        appointment_id = int(update.message.text.strip())
        await show_appointment_management(update.message, appointment_id, user_id)

        # Сбрасываем состояние поиска
        del context.user_data['admin_manage_search']

    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите корректный ID (число).")


async def show_appointment_management(message, appointment_id, admin_id):
    """Показывает управление конкретной записью"""
    appointment = db.get_appointment(appointment_id)

    if not appointment:
        await message.reply_text("❌ Запись с таким ID не найдена.")
        return

    status_text = {
        'pending': '⏳ Ожидает подтверждения',
        'confirmed': '✅ Подтверждена',
        'cancelled': '❌ Отменена'
    }

    # Упрощаем текст, убираем сложное форматирование
    text = f"""
🔧 *Управление записью #{appointment['id']}*

🚗 *Услуга:* {appointment['service_name']}
📅 *Дата:* {appointment['appointment_date']}
🕒 *Время:* {appointment['appointment_time']}
🎯 *Статус:* {status_text[appointment['status']]}

👤 *Клиент:*
• Имя: {appointment['first_name']}
• Username: @{appointment['username'] or 'не указан'}
• Телефон: {appointment['phone']}

🚙 *Автомобиль:*
• Марка: {appointment['car_brand']}
• Модель: {appointment['car_model']}
• Год: {appointment['car_year']}

💬 *Комментарий:* {appointment['comment'] or 'нет'}
"""
    # Кнопки управления в зависимости от статуса
    keyboard = []
    if appointment['status'] == 'pending':
        keyboard.append([
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{appointment_id}"),
            InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{appointment_id}")
        ])
    elif appointment['status'] == 'confirmed':
        keyboard.append([InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{appointment_id}")])


    keyboard.append([InlineKeyboardButton("⬅️ Назад к управлению", callback_data="admin_manage")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем сообщение с более простым форматированием
    try:
        await message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        # Если все равно ошибка, отправляем без форматирования
        text_plain = text.replace('*', '').replace('_', '')
        await message.reply_text(text_plain, reply_markup=reply_markup)


async def handle_management_action(update, context):
    """Обработчик действий управления"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ У вас нет доступа.")
        return

    data = query.data
    appointment_id = int(data.split('_')[-1])

    if data.startswith('confirm_'):
        success = db.update_appointment_status(appointment_id, 'confirmed')
        action_text = "✅ Запись подтверждена!"
    elif data.startswith('cancel_'):
        success = db.update_appointment_status(appointment_id, 'cancelled')
        action_text = "❌ Запись отменена!"
    elif data.startswith('manage_'):
        # Просто показываем управление записью
        await show_appointment_management(query.message, appointment_id, query.from_user.id)
        return
    else:
        return

    if success:
        await query.answer(action_text)

        # Обновляем сообщение
        appointment = db.get_appointment(appointment_id)
        if appointment:
            status_text = {
                'pending': '⏳ Ожидает подтверждения',
                'confirmed': '✅ Подтверждена',
                'cancelled': '❌ Отменена'
            }

            # Упрощенный текст без сложного форматирования
            text = f"""
🔧 Запись #{appointment['id']} - {action_text}

🚗 Услуга: {appointment['service_name']}
📅 Дата: {appointment['appointment_date']}
🕒 Время: {appointment['appointment_time']}
🎯 Статус: {status_text[appointment['status']]}

👤 Клиент: {appointment['first_name']}
📱 Телефон: {appointment['phone']}
🚙 Авто: {appointment['car_brand']} {appointment['car_model']}
"""
            keyboard = [
                [InlineKeyboardButton("⬅️ Назад к управлению", callback_data="admin_manage")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            try:
                await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            except:
                await query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await query.answer("❌ Ошибка при обновлении статуса!")

async def admin_stats(update, context):
    """Показывает статистику"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ У вас нет доступа.")
        return

    # Получаем все записи за 30 дней для статистики
    appointments = db.get_all_appointments(days=30)

    # Считаем статистику вручную
    service_stats = {}
    status_stats = {'pending': 0, 'confirmed': 0, 'cancelled': 0}

    for appt in appointments:
        service_name = appt['service_name']
        service_stats[service_name] = service_stats.get(service_name, 0) + 1
        status_stats[appt['status']] = status_stats.get(appt['status'], 0) + 1

    text = "📊 **Статистика (30 дней)**\n\n"

    text += "📈 **По услугам:**\n"
    for service, count in service_stats.items():
        text += f"• {service}: {count}\n"

    text += "\n🎯 **По статусам:**\n"
    text += f"• ⏳ Ожидают: {status_stats['pending']}\n"
    text += f"• ✅ Подтверждены: {status_stats['confirmed']}\n"
    text += f"• ❌ Отменены: {status_stats['cancelled']}\n"

    text += f"\n📅 **Всего записей:** {len(appointments)}"

    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def admin_back(update, context):
    """Возврат в главное меню админки"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ У вас нет доступа.")
        return

    # Показываем админ-панель
    today = datetime.now().strftime("%d.%m.%Y")
    today_appointments = db.get_appointments_by_date(today)
    today_count = len(today_appointments)

    keyboard = [
        [InlineKeyboardButton("📅 Записи на сегодня", callback_data="admin_today")],
        [InlineKeyboardButton("📋 Все записи", callback_data="admin_all")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("❌ Закрыть админку", callback_data="admin_close")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"""
👨‍💼 **Админ-панель**

📊 Сегодня записей: {today_count}

Выберите действие:
"""
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def admin_close(update, context):
    """Закрывает админ-панель"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text("👨‍💼 Админ-панель закрыта.")

# ==================== ЗАПУСК БОТА ====================

def main():
    """Основная функция запуска бота"""
    try:
        # Тестируем базу данных перед запуском
        logging.info("Testing database connection...")
        if not test_database_connection():
            logging.error("Database connection test failed!")
            return

        # Создаем приложение
        application = Application.builder().token(BOT_TOKEN).build()

        # ... остальной код без изменений ...

        # Запускаем бота
        print("Бот запущен...")
        application.bot.delete_webhook(drop_pending_updates=True)
        application.run_polling(
            allowed_updates=['message', 'callback_query'],
            timeout=30
        )

    except Exception as e:
        print(f"Критическая ошибка: {e}")
        import time
        time.sleep(10)

if __name__ == '__main__':
    main()