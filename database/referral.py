from datetime import datetime, timedelta
import logging
import sqlite3
from database.models import DB_PATH

def _get_db():
    return sqlite3.connect(DB_PATH)

def save_referrer(user_id: int, referrer_id: int) -> bool:
    """Сохраняет информацию о реферере"""
    with _get_db() as conn:
        try:
            conn.execute(
                "UPDATE users SET referrer_id = ? WHERE telegram_id = ? AND (referrer_id IS NULL OR referrer_id = 0)",
                (referrer_id, user_id)
            )
            return True
        except Exception as e:
            logging.error(f"Error saving referrer: {e}")
            return False

def get_referral_link(user_id: int, bot_username: str) -> str:
    """Генерирует реферальную ссылку"""
    return f"https://t.me/{bot_username}?start=ref{user_id}"

def check_and_give_referral_bonus(referred_id: int) -> int | None:
    """Проверяет и выдает бонус пригласившему пользователю"""
    with _get_db() as conn:
        try:
            # Получаем реферера и проверяем использование пробного периода
            user_info = conn.execute("""
                SELECT referrer_id, used_trial 
                FROM users 
                WHERE telegram_id = ?
            """, (referred_id,)).fetchone()
            
            if not user_info or not user_info[0] or not user_info[1]:
                return None

            referrer_id = user_info[0]
            
            # Добавляем запись о бонусе
            conn.execute("""
                INSERT INTO referral_bonuses (referrer_id, referred_id)
                VALUES (?, ?)
            """, (referrer_id, referred_id))
            
            return referrer_id
            
        except sqlite3.IntegrityError:
            # Бонус уже был выдан
            return None
        except Exception as e:
            logging.error(f"Error giving bonus: {e}")
            return None

def get_referral_stats(user_id: int) -> tuple[int, int, int]:
    """Возвращает статистику рефералов: (количество_рефералов, доступные_бонусы, использованные_бонусы)"""
    with _get_db() as conn:
        # Получаем всю статистику одним запросом
        stats = conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN bonus_given_at IS NULL THEN 3 ELSE 0 END) as available,
                SUM(CASE WHEN bonus_given_at IS NOT NULL THEN 3 ELSE 0 END) as used
            FROM referral_bonuses 
            WHERE referrer_id = ?
        """, (user_id,)).fetchone()
        
        return (
            stats[0] or 0,  # total referrals
            stats[1] or 0,  # available bonus days
            stats[2] or 0   # used bonus days
        )

def use_referral_bonus(user_id: int, days_to_use: int = 3) -> int:
    """Использует реферальный бонус. Возвращает количество использованных дней."""
    with _get_db() as conn:
        # Находим неиспользованный бонус
        unused_bonus = conn.execute("""
            SELECT id
            FROM referral_bonuses
            WHERE referrer_id = ? AND bonus_given_at IS NULL
            LIMIT 1
        """, (user_id,)).fetchone()
        
        if not unused_bonus:
            return 0
            
        # Помечаем бонус как использованный
        conn.execute("""
            UPDATE referral_bonuses
            SET bonus_given_at = datetime('now')
            WHERE id = ?
        """, (unused_bonus[0],))
        
        return days_to_use

def get_referral_count(user_id: int) -> int:
    """Возвращает количество рефералов пользователя"""
    with _get_db() as conn:
        result = conn.execute(
            "SELECT COUNT(*) FROM referral_bonuses WHERE referrer_id = ?",
            (user_id,)
        ).fetchone()
        return result[0] if result else 0
