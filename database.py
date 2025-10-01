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
        if self.connection is None or self.connection.closed:
            try:
                # Получаем DATABASE_URL от Railway
                database_url = os.getenv('DATABASE_URL')

                if database_url:
                    # Парсим URL для подключения
                    result = urlparse(database_url)
                    self.connection = psycopg2.connect(
                        database=result.path[1:],
                        user=result.username,
                        password=result.password,
                        host=result.hostname,
                        port=result.port,
                        sslmode='require'
                    )
                else:
                    # Локальная разработка - используем SQLite
                    import sqlite3
                    self.connection = sqlite3.connect("car_service.db")
                    self.connection.row_factory = sqlite3.Row

            except Exception as e:
                logging.error(f"Ошибка подключения к БД: {e}")
                # Fallback на SQLite
                import sqlite3
                self.connection = sqlite3.connect("car_service.db")
                self.connection.row_factory = sqlite3.Row

        return self.connection

    def init_database(self):
        """Инициализирует таблицы в базе данных"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Проверяем тип базы данных
            if hasattr(conn, 'cursor'):  # PostgreSQL
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
                        appointment_date DATE,
                        appointment_time TIME,
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
            self._add_default_services(cursor, conn)

            conn.commit()
            cursor.close()

        except Exception as e:
            logging.error(f"Ошибка инициализации БД: {e}")

    def _add_default_services(self, cursor, conn):
        """Добавляет стандартные услуги в базу"""
        services = [
            ('🛢 Техническое обслуживание', 'Замена масла, фильтров, общее ТО', 'от 2000 руб'),
            ('🔧 Ремонт двигателя', 'Диагностика и ремонт двигателя', 'от 5000 руб'),
            ('🛞 Шиномонтаж', 'Замена и балансировка шин', 'от 1500 руб'),
            ('🎨 Кузовные работы', 'Покраска, ремонт вмятин', 'от 3000 руб'),
            ('⚡ Диагностика', 'Компьютерная диагностика авто', 'от 1000 руб')
        ]

        # Проверяем, есть ли уже услуги
        cursor.execute("SELECT COUNT(*) FROM services")
        existing = cursor.fetchone()[0]

        if existing == 0:
            for service in services:
                try:
                    cursor.execute(
                        "INSERT INTO services (name, description, price_range) VALUES (%s, %s, %s)",
                        service
                    )
                except Exception as e:
                    # Если ошибка, пробуем с SQLite синтаксисом
                    try:
                        cursor.execute(
                            "INSERT INTO services (name, description, price_range) VALUES (?, ?, ?)",
                            service
                        )
                    except:
                        logging.error(f"Ошибка добавления услуги: {e}")

    def add_user(self, user_id, username, first_name):
        """Добавляет или обновляет пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            if hasattr(conn, 'cursor'):  # PostgreSQL
                cursor.execute('''
                    INSERT INTO users (user_id, username, first_name) 
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name
                ''', (user_id, username, first_name))
            else:  # SQLite
                cursor.execute('''
                    INSERT OR REPLACE INTO users (user_id, username, first_name) 
                    VALUES (?, ?, ?)
                ''', (user_id, username, first_name))

            conn.commit()
            cursor.close()
        except Exception as e:
            logging.error(f"Ошибка добавления пользователя: {e}")

    def update_user_car_info(self, user_id, car_brand, car_model, car_year, phone):
        """Обновляет информацию об авто пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            if hasattr(conn, 'cursor'):  # PostgreSQL
                cursor.execute('''
                    UPDATE users 
                    SET car_brand = %s, car_model = %s, car_year = %s, phone = %s
                    WHERE user_id = %s
                ''', (car_brand, car_model, car_year, phone, user_id))
            else:  # SQLite
                cursor.execute('''
                    UPDATE users 
                    SET car_brand = ?, car_model = ?, car_year = ?, phone = ?
                    WHERE user_id = ?
                ''', (car_brand, car_model, car_year, phone, user_id))

            conn.commit()
            cursor.close()
        except Exception as e:
            logging.error(f"Ошибка обновления авто: {e}")

    def get_services(self):
        """Возвращает список всех услуг"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT id, name, description, price_range FROM services')

            if hasattr(conn, 'cursor'):  # PostgreSQL
                services = cursor.fetchall()
                result = []
                for service in services:
                    result.append({
                        'id': service[0],
                        'name': service[1],
                        'description': service[2],
                        'price_range': service[3]
                    })
            else:  # SQLite
                services = cursor.fetchall()
                result = [dict(service) for service in services]

            cursor.close()
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

            if hasattr(conn, 'cursor'):  # PostgreSQL
                cursor.execute('''
                    INSERT INTO appointments 
                    (user_id, service_id, service_name, appointment_date, appointment_time, 
                     car_brand, car_model, car_year, phone, comment)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                ''', (user_id, service_id, service_name, appointment_date, appointment_time,
                      car_brand, car_model, car_year, phone, comment))

                appointment_id = cursor.fetchone()[0]
            else:  # SQLite
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
            return appointment_id
        except Exception as e:
            logging.error(f"Ошибка создания записи: {e}")
            return None

    # Остальные методы (get_user_appointments, get_available_time_slots, etc.)
    # остаются аналогичными, но с проверкой типа БД

    def get_user_appointments(self, user_id):
        """Возвращает записи пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            if hasattr(conn, 'cursor'):  # PostgreSQL
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
            else:  # SQLite
                cursor.execute('''
                    SELECT * FROM appointments 
                    WHERE user_id = ? 
                    ORDER BY appointment_date DESC, appointment_time DESC
                ''', (user_id,))
                appointments = cursor.fetchall()
                result = [dict(appt) for appt in appointments]

            cursor.close()
            return result
        except Exception as e:
            logging.error(f"Ошибка получения записей: {e}")
            return []


# Создаем глобальный экземпляр базы данных
db = Database()