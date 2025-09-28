# Добавляем в bot.py в функцию show_my_appointments:

async def show_my_appointments(update, context):
    """Показывает записи пользователя"""
    user_id = update.message.from_user.id
    appointments = db.get_user_appointments(user_id)

    if not appointments:
        await update.message.reply_text("📋 У вас пока нет активных записей.")
        return

    text = "📋 **Ваши записи:**\n\n"

    for appt in appointments[:10]:  # Показываем последние 10 записей
        status_icon = "✅" if appt['status'] == 'confirmed' else "⏳"
        status_icon = "❌" if appt['status'] == 'cancelled' else status_icon

        text += f"{status_icon} **Запись #{appt['id']}**\n"
        text += f"🚗 Услуга: {appt['service_name']}\n"
        text += f"📅 Дата: {appt['appointment_date']}\n"
        text += f"🕒 Время: {appt['appointment_time']}\n"
        text += f"🎯 Статус: {appt['status']}\n"

        if appt['comment']:
            text += f"💬 Комментарий: {appt['comment']}\n"

        text += "\n" + "─" * 30 + "\n\n"

    if len(appointments) > 10:
        text += f"📄 Показано 10 из {len(appointments)} записей"

    await update.message.reply_text(text, parse_mode='Markdown')