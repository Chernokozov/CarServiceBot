import os
import logging
from datetime import datetime, timedelta
import psycopg2
from urllib.parse import urlparse


class Database:
    def __init__(self):
        self.connection = None
        self.init_database()

    def get_connection(self):
        """Создает соединение с PostgreSQL"""
        if self.connection is None:
            try:
                # Получаем DATABASE_URL от Railway
                database_url = os.getenv('DATABASE_URL')

                # Добавляем подробное логирование
                logging.info("=== DATABASE CONNECTION DEBUG ===")
                logging.info(f"DATABASE_URL exists: {bool(database_url)}")
                if database_url:
                    logging.info(f"DATABASE_URL length: {len(database_url)}")
                    # Не логируем полный URL для безопасности, но покажем начало
                    logging.info(f"DATABASE_URL starts with: {database_url[:20]}...")

                if database_url:
                    # Подключаемся к PostgreSQL
                    logging.info("Attempting PostgreSQL connection...")
                    self.connection = psycopg2.connect(
                        database_url,
                        sslmode='require'
                    )
                    logging.info("✅ Successfully connected to PostgreSQL")

                else:
                    # Локальная разработка - используем SQLite
                    logging.info("No DATABASE_URL, falling back to SQLite")
                    import sqlite3
                    self.connection = sqlite3.connect("car_service.db")
                    self.connection.row_factory = sqlite3.Row
                    logging.info("✅ Connected to SQLite (fallback)")

            except Exception as e:
                logging.error(f"❌ Database connection error: {e}")
                # Fallback на SQLite
                import sqlite3
                self.connection = sqlite3.connect("car_service.db")
                self.connection.row_factory = sqlite3.Row
                logging.info("✅ Fallback to SQLite successful")

        return self.connection

    def init_database(self):
        """Инициализирует таблицы в базе данных"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Проверяем тип базы данных по наличию метода (простой способ)
            is_postgres = hasattr(cursor, 'execute') and not hasattr(conn, 'row_factory')

            if is_postgres:
                logging.info("Initializing PostgreSQL tables")
                # Таблица пользователей
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
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
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS services (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        price_range TEXT
                    )
                ''')

                # Таблица записей
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS appointments (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT,
                        service_id INTEGER,
                        service_name TEXT,
                        appointment_date TEXT,
                        appointment_time TEXT,
                        car_brand TEXT,
                        car_model TEXT,
                        car_year INTEGER,
                        phone TEXT,
                        comment TEXT,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

            else:  # SQLite
                logging.info("Initializing SQLite tables")
                # Таблица пользователей
                cursor.execute('''
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
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS services (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,
                        price_range TEXT
                    )
                ''')

                # Таблица записей
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS appointments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        service_id INTEGER,
                        service_name TEXT,
                        appointment_date TEXT,
                        appointment_time TEXT,
                        car_brand TEXT,
                        car_model TEXT,
                        car_year INTEGER,
                        phone TEXT,
                        comment TEXT,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

            # Добавляем базовые услуги
            self._add_default_services(cursor, is_postgres)

            conn.commit()
            cursor.close()
            logging.info("Database initialized successfully")

        except Exception as e:
            logging.error(f"Ошибка инициализации БД: {e}")

    def _add_default_services(self, cursor, is_postgres):
        """Добавляет стандартные услуги в базу"""
        services = [
            ('🛢 Техническое обслуживание', 'Замена масла, фильтров, общее ТО', 'от 2000 руб'),
            ('🔧 Ремонт двигателя', 'Диагностика и ремонт двигателя', 'от 5000 руб'),
            ('🛞 Шиномонтаж', 'Замена и балансировка шин', 'от 1500 руб'),
            ('🎨 Кузовные работы', 'Покраска, ремонт вмятин', 'от 3000 руб'),
            ('⚡ Диагностика', 'Компьютерная диагностика авто', 'от 1000 руб')
        ]

        # Проверяем, есть ли уже услуги
        if is_postgres:
            cursor.execute("SELECT COUNT(*) FROM services")
        else:
            cursor.execute("SELECT COUNT(*) FROM services")

        existing = cursor.fetchone()[0]

        if existing == 0:
            logging.info("Adding default services to database")
            for service in services:
                try:
                    if is_postgres:
                        cursor.execute(
                            "INSERT INTO services (name, description, price_range) VALUES (%s, %s, %s)",
                            service
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO services (name, description, price_range) VALUES (?, ?, ?)",
                            service
                        )
                except Exception as e:
                    logging.error(f"Ошибка добавления услуги: {e}")

    def add_user(self, user_id, username, first_name):
        """Добавляет или обновляет пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            is_postgres = hasattr(cursor, 'execute') and not hasattr(conn, 'row_factory')

            if is_postgres:
                cursor.execute('''
                    INSERT INTO users (user_id, username, first_name) 
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name
                ''', (user_id, username, first_name))
            else:
                cursor.execute('''
                    INSERT OR REPLACE INTO users (user_id, username, first_name) 
                    VALUES (?, ?, ?)
                ''', (user_id, username, first_name))

            conn.commit()
            cursor.close()
            logging.info(f"User {user_id} added/updated")
        except Exception as e:
            logging.error(f"Ошибка добавления пользователя: {e}")

    def update_user_car_info(self, user_id, car_brand, car_model, car_year, phone):
        """Обновляет информацию об авто пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            is_postgres = hasattr(cursor, 'execute') and not hasattr(conn, 'row_factory')

            if is_postgres:
                cursor.execute('''
                    UPDATE users 
                    SET car_brand = %s, car_model = %s, car_year = %s, phone = %s
                    WHERE user_id = %s
                ''', (car_brand, car_model, car_year, phone, user_id))
            else:
                cursor.execute('''
                    UPDATE users 
                    SET car_brand = ?, car_model = ?, car_year = ?, phone = ?
                    WHERE user_id = ?
                ''', (car_brand, car_model, car_year, phone, user_id))

            conn.commit()
            cursor.close()
            logging.info(f"User {user_id} car info updated")
        except Exception as e:
            logging.error(f"Ошибка обновления авто: {e}")

    def get_services(self):
        """Возвращает список всех услуг"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT id, name, description, price_range FROM services')

            is_postgres = hasattr(cursor, 'execute') and not hasattr(conn, 'row_factory')

            if is_postgres:
                services = cursor.fetchall()
                result = []
                for service in services:
                    result.append({
                        'id': service[0],
                        'name': service[1],
                        'description': service[2],
                        'price_range': service[3]
                    })
            else:
                services = cursor.fetchall()
                result = [dict(service) for service in services]

            cursor.close()
            logging.info(f"Retrieved {len(result)} services")
            return result
        except Exception as e:
            logging.error(f"Ошибка получения услуг: {e}")
            return []

    def create_appointment(self, user_id, service_id, service_name, appointment_date,
                           appointment_time, car_brand, car_model, car_year, phone, comment=""):
        """Создает новую запись"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            is_postgres = hasattr(cursor, 'execute') and not hasattr(conn, 'row_factory')

            if is_postgres:
                cursor.execute('''
                    INSERT INTO appointments 
                    (user_id, service_id, service_name, appointment_date, appointment_time, 
                     car_brand, car_model, car_year, phone, comment)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                ''', (user_id, service_id, service_name, appointment_date, appointment_time,
                      car_brand, car_model, car_year, phone, comment))

                appointment_id = cursor.fetchone()[0]
            else:
                cursor.execute('''
                    INSERT INTO appointments 
                    (user_id, service_id, service_name, appointment_date, appointment_time, 
                     car_brand, car_model, car_year, phone, comment)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, service_id, service_name, appointment_date, appointment_time,
                      car_brand, car_model, car_year, phone, comment))

                appointment_id = cursor.lastrowid

            conn.commit()
            cursor.close()
            logging.info(f"Appointment created with ID: {appointment_id}")
            return appointment_id
        except Exception as e:
            logging.error(f"Ошибка создания записи: {e}")
            return None

    def get_user_appointments(self, user_id):
        """Возвращает записи пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            is_postgres = hasattr(cursor, 'execute') and not hasattr(conn, 'row_factory')

            if is_postgres:
                cursor.execute('''
                    SELECT * FROM appointments 
                    WHERE user_id = %s 
                    ORDER BY appointment_date DESC, appointment_time DESC
                ''', (user_id,))
                appointments = cursor.fetchall()
                result = []
                for appt in appointments:
                    result.append({
                        'id': appt[0], 'user_id': appt[1], 'service_id': appt[2],
                        'service_name': appt[3], 'appointment_date': appt[4],
                        'appointment_time': appt[5], 'car_brand': appt[6],
                        'car_model': appt[7], 'car_year': appt[8], 'phone': appt[9],
                        'comment': appt[10], 'status': appt[11], 'created_at': appt[12]
                    })
            else:
                cursor.execute('''
                    SELECT * FROM appointments 
                    WHERE user_id = ? 
                    ORDER BY appointment_date DESC, appointment_time DESC
                ''', (user_id,))
                appointments = cursor.fetchall()
                result = [dict(appt) for appt in appointments]

            cursor.close()
            logging.info(f"Retrieved {len(result)} appointments for user {user_id}")
            return result
        except Exception as e:
            logging.error(f"Ошибка получения записей: {e}")
            return []

    def get_appointments_by_date(self, date=None):
        """Возвращает записи на определенную дату"""
        try:
            if date is None:
                date = datetime.now().strftime("%d.%m.%Y")

            conn = self.get_connection()
            cursor = conn.cursor()

            is_postgres = hasattr(cursor, 'execute') and not hasattr(conn, 'row_factory')

            if is_postgres:
                cursor.execute('''
                    SELECT a.*, u.first_name, u.username 
                    FROM appointments a
                    LEFT JOIN users u ON a.user_id = u.user_id
                    WHERE a.appointment_date = %s AND a.status != 'cancelled'
                    ORDER BY a.appointment_time
                ''', (date,))
                appointments = cursor.fetchall()
                result = []
                for appt in appointments:
                    result.append({
                        'id': appt[0], 'user_id': appt[1], 'service_id': appt[2],
                        'service_name': appt[3], 'appointment_date': appt[4],
                        'appointment_time': appt[5], 'car_brand': appt[6],
                        'car_model': appt[7], 'car_year': appt[8], 'phone': appt[9],
                        'comment': appt[10], 'status': appt[11], 'created_at': appt[12],
                        'first_name': appt[13], 'username': appt[14]
                    })
            else:
                cursor.execute('''
                    SELECT a.*, u.first_name, u.username 
                    FROM appointments a
                    LEFT JOIN users u ON a.user_id = u.user_id
                    WHERE a.appointment_date = ? AND a.status != 'cancelled'
                    ORDER BY a.appointment_time
                ''', (date,))
                appointments = cursor.fetchall()
                result = [dict(appt) for appt in appointments]

            cursor.close()
            return result
        except Exception as e:
            logging.error(f"Ошибка получения записей на дату: {e}")
            return []

    def get_all_appointments(self, days=7):
        """Возвращает все записи за последние N дней"""
        try:
            start_date = (datetime.now() - timedelta(days=days)).strftime("%d.%m.%Y")

            conn = self.get_connection()
            cursor = conn.cursor()

            is_postgres = hasattr(cursor, 'execute') and not hasattr(conn, 'row_factory')

            if is_postgres:
                cursor.execute('''
                    SELECT a.*, u.first_name, u.username 
                    FROM appointments a
                    LEFT JOIN users u ON a.user_id = u.user_id
                    WHERE a.appointment_date >= %s 
                    ORDER BY a.appointment_date DESC, a.appointment_time DESC
                ''', (start_date,))
                appointments = cursor.fetchall()
                result = []
                for appt in appointments:
                    result.append({
                        'id': appt[0], 'user_id': appt[1], 'service_id': appt[2],
                        'service_name': appt[3], 'appointment_date': appt[4],
                        'appointment_time': appt[5], 'car_brand': appt[6],
                        'car_model': appt[7], 'car_year': appt[8], 'phone': appt[9],
                        'comment': appt[10], 'status': appt[11], 'created_at': appt[12],
                        'first_name': appt[13], 'username': appt[14]
                    })
            else:
                cursor.execute('''
                    SELECT a.*, u.first_name, u.username 
                    FROM appointments a
                    LEFT JOIN users u ON a.user_id = u.user_id
                    WHERE a.appointment_date >= ? 
                    ORDER BY a.appointment_date DESC, a.appointment_time DESC
                ''', (start_date,))
                appointments = cursor.fetchall()
                result = [dict(appt) for appt in appointments]

            cursor.close()
            return result
        except Exception as e:
            logging.error(f"Ошибка получения всех записей: {e}")
            return []

    def get_appointment(self, appointment_id):
        """Возвращает запись по ID"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            is_postgres = hasattr(cursor, 'execute') and not hasattr(conn, 'row_factory')

            if is_postgres:
                cursor.execute('''
                    SELECT a.*, u.first_name, u.username 
                    FROM appointments a
                    LEFT JOIN users u ON a.user_id = u.user_id
                    WHERE a.id = %s
                ''', (appointment_id,))
                appointment = cursor.fetchone()
                if appointment:
                    result = {
                        'id': appointment[0], 'user_id': appointment[1], 'service_id': appointment[2],
                        'service_name': appointment[3], 'appointment_date': appointment[4],
                        'appointment_time': appointment[5], 'car_brand': appointment[6],
                        'car_model': appointment[7], 'car_year': appointment[8], 'phone': appointment[9],
                        'comment': appointment[10], 'status': appointment[11], 'created_at': appointment[12],
                        'first_name': appointment[13], 'username': appointment[14]
                    }
                else:
                    result = None
            else:
                cursor.execute('''
                    SELECT a.*, u.first_name, u.username 
                    FROM appointments a
                    LEFT JOIN users u ON a.user_id = u.user_id
                    WHERE a.id = ?
                ''', (appointment_id,))
                appointment = cursor.fetchone()
                result = dict(appointment) if appointment else None

            cursor.close()
            return result
        except Exception as e:
            logging.error(f"Ошибка получения записи: {e}")
            return None

    def update_appointment_status(self, appointment_id, status):
        """Обновляет статус записи"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            is_postgres = hasattr(cursor, 'execute') and not hasattr(conn, 'row_factory')

            if is_postgres:
                cursor.execute('''
                    UPDATE appointments 
                    SET status = %s 
                    WHERE id = %s
                ''', (status, appointment_id))
            else:
                cursor.execute('''
                    UPDATE appointments 
                    SET status = ? 
                    WHERE id = ?
                ''', (status, appointment_id))

            conn.commit()
            cursor.close()
            logging.info(f"Appointment {appointment_id} status updated to {status}")
            return True
        except Exception as e:
            logging.error(f"Ошибка обновления статуса: {e}")
            return False

    def get_available_time_slots(self, date):
        """Возвращает доступные временные слоты на дату"""
        all_slots = ['09:00', '10:00', '11:00', '12:00', '14:00', '15:00', '16:00', '17:00']

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            is_postgres = hasattr(cursor, 'execute') and not hasattr(conn, 'row_factory')

            if is_postgres:
                cursor.execute('''
                    SELECT appointment_time FROM appointments 
                    WHERE appointment_date = %s AND status != 'cancelled'
                ''', (date,))
            else:
                cursor.execute('''
                    SELECT appointment_time FROM appointments 
                    WHERE appointment_date = ? AND status != 'cancelled'
                ''', (date,))

            booked_slots = cursor.fetchall()
            booked_times = [slot[0] for slot in booked_slots]
            available_slots = [slot for slot in all_slots if slot not in booked_times]

            cursor.close()
            return available_slots
        except Exception as e:
            logging.error(f"Ошибка получения слотов: {e}")
            return all_slots


# Создаем глобальный экземпляр базы данных
db = Database()