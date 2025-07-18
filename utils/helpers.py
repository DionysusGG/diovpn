from datetime import datetime
import re

def parse_date(date_str: str) -> datetime:
    """Парсит дату из разных форматов"""
    # Убираем микросекунды если они есть
    date_str = re.sub(r'\.\d+', '', date_str)
    # Заменяем 'T' на пробел
    date_str = date_str.replace('T', ' ')
    try:
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        try:
            return datetime.fromisoformat(date_str)
        except ValueError:
            # Если не удалось распарсить, возвращаем текущую дату
            return datetime.now()
