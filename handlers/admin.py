import logging
from datetime import datetime, timedelta
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler, MessageHandler, filters
from database import db
from config import ADMIN_IDS


# Проверка прав администратора
def is_admin(user_id):
    return user_id in ADMIN_IDS


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает админ-панель"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет доступа к этой команде.")
        return

    # Статистика на сегодня
    today = datetime.now().strftime("%d.%m.%Y")
    today_appointments = db.get_appointments_by_date(today)
    today_count = len(today_appointments)

    # Общая статистика
    total_appointments = len(db.get_all_appointments(days=30))

    keyboard = [
        [InlineKeyboardButton("📅 Записи на сегодня", callback_data="admin_today")],
        [InlineKeyboardButton("📋 Все записи (7 дней)", callback_data="admin_all")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("🔍 Найти запись", callback_data="admin_search")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"""
👨‍💼 **Админ-панель**

📊 Статистика:
• Записей на сегодня: {today_count}
• Всего записей (30 дней): {total_appointments}

Выберите действие:
"""
    await update.message.reply_text(text, reply_markup=reply_markup,)


async def admin_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")]]
    else:
        text = f"📅 **Записи на сегодня ({today})**\n\n"

        for i, appt in enumerate(appointments, 1):
            status_icon = "✅" if appt['status'] == 'confirmed' else "⏳"
            text += f"{i}. {status_icon} {appt['appointment_time']} - {appt['service_name']}\n"
            text += f"   🚗 {appt['car_brand']} {appt['car_model']}\n"
            text += f"   👤 {appt['first_name']} ({appt['phone']})\n"
            text += f"   📝 ID: #{appt['id']}\n\n"

        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="admin_today")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup,)


async def admin_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает все записи за 7 дней"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ У вас нет доступа.")
        return

    appointments = db.get_all_appointments(days=7)

    if not appointments:
        text = "📋 За последние 7 дней записей нет."
    else:
        text = "📋 **Все записи (7 дней)**\n\n"

        current_date = None
        for appt in appointments:
            if appt['appointment_date'] != current_date:
                current_date = appt['appointment_date']
                weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][
                    datetime.strptime(current_date, "%d.%m.%Y").weekday()
                ]
                text += f"\n📅 **{current_date} ({weekday})**\n"

            status_icon = "✅" if appt['status'] == 'confirmed' else "⏳"
            status_icon = "❌" if appt['status'] == 'cancelled' else status_icon

            text += f"{status_icon} {appt['appointment_time']} - {appt['service_name']}\n"
            text += f"   🚗 {appt['car_brand']} {appt['car_model']} | 👤 {appt['first_name']}\n"
            text += f"   📝 ID: #{appt['id']}\n"

            # Кнопки управления для каждой записи
            if appt['status'] == 'pending':
                text += f"   [Подтвердить](tg://btn?admin_confirm_{appt['id']}) | [Отменить](tg://btn?admin_cancel_{appt['id']})\n"
            elif appt['status'] == 'confirmed':
                text += f"   [Отменить](tg://btn?admin_cancel_{appt['id']})\n"

            text += "\n"

    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin_all")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup,)


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ У вас нет доступа.")
        return

    # Статистика по услугам (последние 30 дней)
    appointments = db.get_all_appointments(days=30)

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
    await query.edit_message_text(text, reply_markup=reply_markup,)


async def admin_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск записи по ID"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ У вас нет доступа.")
        return

    # Сохраняем состояние поиска
    context.user_data['admin_search'] = True

    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🔍 **Поиск записи**\n\nВведите ID записи (например: 1):",
        reply_markup=reply_markup,
       
    )


async def admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню админки"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ У вас нет доступа.")
        return

    # Очищаем состояние поиска
    if 'admin_search' in context.user_data:
        del context.user_data['admin_search']

    # Показываем админ-панель
    today = datetime.now().strftime("%d.%m.%Y")
    today_appointments = db.get_appointments_by_date(today)
    today_count = len(today_appointments)
    total_appointments = len(db.get_all_appointments(days=30))

    keyboard = [
        [InlineKeyboardButton("📅 Записи на сегодня", callback_data="admin_today")],
        [InlineKeyboardButton("📋 Все записи (7 дней)", callback_data="admin_all")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("🔍 Найти запись", callback_data="admin_search")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"""
👨‍💼 **Админ-панель**

📊 Статистика:
• Записей на сегодня: {today_count}
• Всего записей (30 дней): {total_appointments}

Выберите действие:
"""
    await query.edit_message_text(text, reply_markup=reply_markup)


async def handle_admin_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода ID для поиска"""
    user_id = update.message.from_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет доступа.")
        return

    if not context.user_data.get('admin_search'):
        return

    try:
        appointment_id = int(update.message.text.strip())
        appointment = db.get_appointment(appointment_id)

        if not appointment:
            await update.message.reply_text("❌ Запись с таким ID не найдена.")
            return

        # Форматируем информацию о записи
        status_text = {
            'pending': '⏳ Ожидает подтверждения',
            'confirmed': '✅ Подтверждена',
            'cancelled': '❌ Отменена'
        }

        text = f"""
🔍 **Запись #{appointment['id']}**

🚗 **Услуга:** {appointment['service_name']}
📅 **Дата:** {appointment['appointment_date']}
🕒 **Время:** {appointment['appointment_time']}
🎯 **Статус:** {status_text[appointment['status']]}

👤 **Клиент:**
• Имя: {appointment['first_name']}
• Username: @{appointment['username'] or 'не указан'}
• Телефон: {appointment['phone']}

🚙 **Автомобиль:**
• Марка: {appointment['car_brand']}
• Модель: {appointment['car_model']}
• Год: {appointment['car_year']}

💬 **Комментарий:** {appointment['comment'] or 'нет'}
"""
        # Кнопки управления
        keyboard = []
        if appointment['status'] == 'pending':
            keyboard.append([
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"admin_confirm_{appointment_id}"),
                InlineKeyboardButton("❌ Отменить", callback_data=f"admin_cancel_{appointment_id}")
            ])
        elif appointment['status'] == 'confirmed':
            keyboard.append([InlineKeyboardButton("❌ Отменить", callback_data=f"admin_cancel_{appointment_id}")])

        keyboard.append([InlineKeyboardButton("⬅️ Назад в админку", callback_data="admin_back")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)

        # Сбрасываем состояние поиска
        del context.user_data['admin_search']

    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите корректный ID (число).")


async def handle_appointment_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик действий с записями (подтвердить/отменить)"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ У вас нет доступа.")
        return

    data = query.data
    appointment_id = int(data.split('_')[-1])

    if data.startswith('admin_confirm_'):
        success = db.update_appointment_status(appointment_id, 'confirmed')
        action_text = "подтверждена"
    elif data.startswith('admin_cancel_'):
        success = db.update_appointment_status(appointment_id, 'cancelled')
        action_text = "отменена"
    else:
        return

    if success:
        await query.answer(f"✅ Запись {action_text}!")

        # Обновляем сообщение
        appointment = db.get_appointment(appointment_id)
        if appointment:
            status_text = {
                'pending': '⏳ Ожидает подтверждения',
                'confirmed': '✅ Подтверждена',
                'cancelled': '❌ Отменена'
            }

            text = f"""
🔍 **Запись #{appointment['id']}**

🚗 **Услуга:** {appointment['service_name']}
📅 **Дата:** {appointment['appointment_date']}
🕒 **Время:** {appointment['appointment_time']}
🎯 **Статус:** {status_text[appointment['status']]}

👤 **Клиент:** {appointment['first_name']}
📱 **Телефон:** {appointment['phone']}
🚙 **Авто:** {appointment['car_brand']} {appointment['car_model']}
"""
            keyboard = [[InlineKeyboardButton("⬅️ Назад в админку", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(text, reply_markup=reply_markup,)
    else:
        await query.answer("❌ Ошибка при обновлении статуса!")


# Регистрация обработчиков
def register_admin_handlers(application):
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(admin_today, pattern="^admin_today$"))
    application.add_handler(CallbackQueryHandler(admin_all, pattern="^admin_all$"))
    application.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    application.add_handler(CallbackQueryHandler(admin_search, pattern="^admin_search$"))
    application.add_handler(CallbackQueryHandler(admin_back, pattern="^admin_back$"))
    application.add_handler(CallbackQueryHandler(handle_appointment_action, pattern="^admin_(confirm|cancel)_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_search))