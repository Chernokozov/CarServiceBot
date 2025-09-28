from enum import Enum

class AppointmentState(Enum):
    """Состояния процесса записи"""
    SELECT_SERVICE = 1
    SELECT_DATE = 2
    SELECT_TIME = 3
    CAR_BRAND = 4
    CAR_MODEL = 5
    CAR_YEAR = 6
    PHONE = 7
    COMMENT = 8
    CONFIRM = 9

# Временное хранилище данных записи (в продакшене используйте Redis)
user_data_store = {}