import sqlite3
import logging
from datetime import datetime, timedelta


class Database:
    def __init__(self, db_name="car_service.db"):
        self.db_name = db_name
        self.init_database()

    def get_connection(self):
        """Создает соединение с базой данных"""
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row  # Чтобы получать данные как словарь
        return conn

    def init_database(self):
        """Инициализирует таблицы в базе данных"""
        try:
            with self.get_connection() as conn:
                # Таблица пользователей
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        phone TEXT,
                        car_brand TEXT,
                        car_model TEXT,
                        car_year INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Таблица услуг
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS services (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,
                        price_range TEXT
                    )
                ''')

                # Таблица записей
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS appointments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        service_id INTEGER,
                        service_name TEXT,
                        appointment_date DATE,
                        appointment_time TIME,
                        car_brand TEXT,
                        car_model TEXT,
                        car_year INTEGER,
                        phone TEXT,
                        comment TEXT,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id),
                        FOREIGN KEY (service_id) REFERENCES services (id)
                    )
                ''')

                # Добавляем базовые услуги
                self._add_default_services(conn)

        except Exception as e:
            logging.error(f"Ошибка инициализации БД: {e}")

    def _add_default_services(self, conn):
        """Добавляет стандартные услуги в базу"""
        services = [
            ('🛢 Техническое обслуживание', 'Замена масла, фильтров, общее ТО', 'от 2000 руб'),
            ('🔧 Ремонт двигателя', 'Диагностика и ремонт двигателя', 'от 5000 руб'),
            ('🛞 Шиномонтаж', 'Замена и балансировка шин', 'от 1500 руб'),
            ('🎨 Кузовные работы', 'Покраска, ремонт вмятин', 'от 3000 руб'),
            ('⚡ Диагностика', 'Компьютерная диагностика авто', 'от 1000 руб')
        ]

        # Проверяем, есть ли уже услуги
        existing = conn.execute("SELECT COUNT(*) FROM services").fetchone()[0]
        if existing == 0:
            conn.executemany(
                "INSERT INTO services (name, description, price_range) VALUES (?, ?, ?)",
                services
            )

    def add_user(self, user_id, username, first_name):
        """Добавляет или обновляет пользователя"""
        try:
            with self.get_connection() as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO users (user_id, username, first_name) 
                    VALUES (?, ?, ?)
                ''', (user_id, username, first_name))
        except Exception as e:
            logging.error(f"Ошибка добавления пользователя: {e}")

    def update_user_car_info(self, user_id, car_brand, car_model, car_year, phone):
        """Обновляет информацию об авто пользователя"""
        try:
            with self.get_connection() as conn:
                conn.execute('''
                    UPDATE users 
                    SET car_brand = ?, car_model = ?, car_year = ?, phone = ?
                    WHERE user_id = ?
                ''', (car_brand, car_model, car_year, phone, user_id))
        except Exception as e:
            logging.error(f"Ошибка обновления авто: {e}")

    def get_services(self):
        """Возвращает список всех услуг"""
        try:
            with self.get_connection() as conn:
                services = conn.execute('''
                    SELECT id, name, description, price_range FROM services
                ''').fetchall()
                return [dict(service) for service in services]
        except Exception as e:
            logging.error(f"Ошибка получения услуг: {e}")
            return []

    def create_appointment(self, user_id, service_id, service_name, appointment_date,
                           appointment_time, car_brand, car_model, car_year, phone, comment=""):
        """Создает новую запись"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute('''
                    INSERT INTO appointments 
                    (user_id, service_id, service_name, appointment_date, appointment_time, 
                     car_brand, car_model, car_year, phone, comment)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, service_id, service_name, appointment_date, appointment_time,
                      car_brand, car_model, car_year, phone, comment))
                return cursor.lastrowid
        except Exception as e:
            logging.error(f"Ошибка создания записи: {e}")
            return None

    def get_user_appointments(self, user_id):
        """Возвращает записи пользователя"""
        try:
            with self.get_connection() as conn:
                appointments = conn.execute('''
                    SELECT * FROM appointments 
                    WHERE user_id = ? 
                    ORDER BY appointment_date DESC, appointment_time DESC
                ''', (user_id,)).fetchall()
                return [dict(appt) for appt in appointments]
        except Exception as e:
            logging.error(f"Ошибка получения записей: {e}")
            return []

    def get_available_time_slots(self, date):
        """Возвращает доступные временные слоты на дату"""
        # Базовые слоты времени (можно настроить)
        all_slots = ['09:00', '10:00', '11:00', '12:00', '14:00', '15:00', '16:00', '17:00']

        try:
            with self.get_connection() as conn:
                # Получаем занятые слоты на эту дату
                booked_slots = conn.execute('''
                    SELECT appointment_time FROM appointments 
                    WHERE appointment_date = ? AND status != 'cancelled'
                ''', (date,)).fetchall()

                booked_times = [slot['appointment_time'] for slot in booked_slots]
                available_slots = [slot for slot in all_slots if slot not in booked_times]

                return available_slots
        except Exception as e:
            logging.error(f"Ошибка получения слотов: {e}")
            return all_slots

    # ========== ДОБАВЛЯЕМ НОВЫЕ МЕТОДЫ ДЛЯ АДМИН-ПАНЕЛИ ==========

    def get_appointments_by_date(self, date=None):
        """Возвращает записи на определенную дату (сегодня по умолчанию)"""
        try:
            with self.get_connection() as conn:
                if date is None:
                    date = datetime.now().strftime("%d.%m.%Y")

                appointments = conn.execute('''
                    SELECT a.*, u.first_name, u.username 
                    FROM appointments a
                    LEFT JOIN users u ON a.user_id = u.user_id
                    WHERE a.appointment_date = ? AND a.status != 'cancelled'
                    ORDER BY a.appointment_time
                ''', (date,)).fetchall()
                return [dict(appt) for appt in appointments]
        except Exception as e:
            logging.error(f"Ошибка получения записей на дату: {e}")
            return []

    def get_all_appointments(self, days=7):
        """Возвращает все записи за последние N дней"""
        try:
            with self.get_connection() as conn:
                # Вычисляем дату начала (сегодня - days дней)
                start_date_obj = datetime.now() - timedelta(days=days)
                start_date = start_date_obj.strftime("%d.%m.%Y")

                appointments = conn.execute('''
                    SELECT a.*, u.first_name, u.username 
                    FROM appointments a
                    LEFT JOIN users u ON a.user_id = u.user_id
                    WHERE a.appointment_date >= ? 
                    ORDER BY a.appointment_date DESC, a.appointment_time DESC
                ''', (start_date,)).fetchall()
                return [dict(appt) for appt in appointments]
        except Exception as e:
            logging.error(f"Ошибка получения всех записей: {e}")
            return []

    def get_appointment(self, appointment_id):
        """Возвращает запись по ID"""
        try:
            with self.get_connection() as conn:
                appointment = conn.execute('''
                    SELECT a.*, u.first_name, u.username 
                    FROM appointments a
                    LEFT JOIN users u ON a.user_id = u.user_id
                    WHERE a.id = ?
                ''', (appointment_id,)).fetchone()
                return dict(appointment) if appointment else None
        except Exception as e:
            logging.error(f"Ошибка получения записи: {e}")
            return None

    def update_appointment_status(self, appointment_id, status):
        """Обновляет статус записи"""
        try:
            with self.get_connection() as conn:
                conn.execute('''
                    UPDATE appointments 
                    SET status = ? 
                    WHERE id = ?
                ''', (status, appointment_id))
                return True
        except Exception as e:
            logging.error(f"Ошибка обновления статуса: {e}")
            return False

    def get_today_appointments_count(self):
        """Возвращает количество записей на сегодня"""
        try:
            with self.get_connection() as conn:
                today = datetime.now().strftime("%d.%m.%Y")
                count = conn.execute('''
                    SELECT COUNT(*) FROM appointments 
                    WHERE appointment_date = ? AND status != 'cancelled'
                ''', (today,)).fetchone()[0]
                return count
        except Exception as e:
            logging.error(f"Ошибка получения количества записей: {e}")
            return 0

    def get_appointment_stats(self, days=30):
        """Возвращает статистику по записям"""
        try:
            with self.get_connection() as conn:
                start_date = (datetime.now() - timedelta(days=days)).strftime("%d.%m.%Y")

                # Общее количество записей
                total = conn.execute('''
                    SELECT COUNT(*) FROM appointments 
                    WHERE appointment_date >= ?
                ''', (start_date,)).fetchone()[0]

                # По статусам
                status_stats = conn.execute('''
                    SELECT status, COUNT(*) as count 
                    FROM appointments 
                    WHERE appointment_date >= ?
                    GROUP BY status
                ''', (start_date,)).fetchall()

                # По услугам
                service_stats = conn.execute('''
                    SELECT service_name, COUNT(*) as count 
                    FROM appointments 
                    WHERE appointment_date >= ?
                    GROUP BY service_name
                ''', (start_date,)).fetchall()

                return {
                    'total': total,
                    'status_stats': {row['status']: row['count'] for row in status_stats},
                    'service_stats': {row['service_name']: row['count'] for row in service_stats}
                }
        except Exception as e:
            logging.error(f"Ошибка получения статистики: {e}")
            return {'total': 0, 'status_stats': {}, 'service_stats': {}}


# Создаем глобальный экземпляр базы данных
db = Database()