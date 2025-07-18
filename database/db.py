import sqlite3
import logging
from database.models import DB_PATH, init_db
from datetime import datetime, timedelta

init_db()

def _get_db():
    return sqlite3.connect(DB_PATH)

def get_trial_users_info():
    with _get_db() as conn:
        return conn.execute(
            "SELECT telegram_id, subscription_start, subscription_end FROM users WHERE used_trial=1"
        ).fetchall()

def get_trial_users_count():
    with _get_db() as conn:
        result = conn.execute("SELECT COUNT(*) FROM users WHERE used_trial=1").fetchone()
        return result[0] if result else 0

def clear_all_cache():
    with _get_db() as conn:
        conn.executescript("""
            DELETE FROM referral_bonuses;
            DELETE FROM users;
            DELETE FROM keys;
        """)

def add_user(telegram_id, referrer_id=None):
    with _get_db() as conn:
        # Проверяем, существует ли пользователь
        exists = conn.execute(
            "SELECT 1 FROM users WHERE telegram_id = ?",
            (telegram_id,)
        ).fetchone()
        
        if not exists:
            # Если пользователь новый, добавляем его с referrer_id
            conn.execute(
                "INSERT INTO users (telegram_id, referrer_id) VALUES (?, ?)",
                (telegram_id, referrer_id)
            )
        elif referrer_id:
            # Если пользователь существует и у нас есть referrer_id, 
            # обновляем его только если он ещё не был установлен
            conn.execute("""
                UPDATE users 
                SET referrer_id = ?
                WHERE telegram_id = ? 
                AND (referrer_id IS NULL OR referrer_id = 0)
            """, (referrer_id, telegram_id))

def has_used_trial(telegram_id):
    with _get_db() as conn:
        row = conn.execute("SELECT used_trial FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
        return bool(row and row[0])

def set_trial_period(telegram_id, start, end):
    with _get_db() as conn:
        conn.execute("""
            UPDATE users 
            SET used_trial=1, subscription_start=?, subscription_end=? 
            WHERE telegram_id=?
        """, (start, end, telegram_id))

def save_vless_key(telegram_id, uuid, expires_at):
    with _get_db() as conn:
        conn.execute(
            "REPLACE INTO keys (telegram_id, uuid, expires_at) VALUES (?, ?, ?)",
            (telegram_id, uuid, expires_at)
        )

def get_vless_key(telegram_id):
    with _get_db() as conn:
        row = conn.execute(
            "SELECT uuid, expires_at FROM keys WHERE telegram_id=?",
            (telegram_id,)
        ).fetchone()
        return (row[0], row[1]) if row else (None, None)

def get_all_active_keys():
    """Получить все активные ключи с информацией о пользователях"""
    with _get_db() as conn:
        return conn.execute("""
            SELECT keys.telegram_id, keys.uuid, keys.expires_at 
            FROM keys
            WHERE keys.expires_at > datetime('now')
            ORDER BY keys.expires_at ASC
        """).fetchall()

def get_keys_expiring_soon(days_threshold=3):
    """Получить ключи, которые истекают в ближайшие дни"""
    with _get_db() as conn:
        return conn.execute("""
            SELECT telegram_id, uuid, expires_at 
            FROM keys 
            WHERE expires_at > datetime('now')
            AND expires_at <= datetime('now', '+' || ? || ' days')
        """, (days_threshold,)).fetchall()

def extend_key_period(telegram_id, uuid, days):
    """Продлить срок действия ключа"""
    with _get_db() as conn:
        try:
            # Находим неиспользованный бонус
            unused_bonus = conn.execute("""
                SELECT id FROM referral_bonuses
                WHERE referrer_id = ? AND bonus_given_at IS NULL
                LIMIT 1
            """, (telegram_id,)).fetchone()
            
            if unused_bonus:
                # Помечаем бонус как использованный
                conn.execute("""
                    UPDATE referral_bonuses
                    SET bonus_given_at = datetime('now')
                    WHERE id = ?
                """, (unused_bonus[0],))
                
            # Продлеваем срок действия ключа
            conn.execute("""
                UPDATE keys 
                SET expires_at = datetime(expires_at, '+' || ? || ' days')
                WHERE telegram_id = ? AND uuid = ?
            """, (days, telegram_id, uuid))
            
            # Получаем новую дату окончания
            result = conn.execute("""
                SELECT expires_at FROM keys
                WHERE telegram_id = ? AND uuid = ?
            """, (telegram_id, uuid)).fetchone()
            
            if result:
                return result[0]
        except Exception as e:
            logging.error(f"Error extending key period: {e}")
        return None

def get_user_active_key(telegram_id):
    """Получить активный ключ пользователя"""
    with _get_db() as conn:
        return conn.execute("""
            SELECT uuid, expires_at FROM keys
            WHERE telegram_id = ? AND expires_at > datetime('now')
        """, (telegram_id,)).fetchone()

def save_referrer(user_id: int, referrer_id: int):
    """Сохраняет ID пригласившего пользователя"""
    if user_id == referrer_id:  # Защита от самореферальства
        return False
        
    with _get_db() as conn:
        # Проверяем существование реферера
        if not conn.execute("SELECT 1 FROM users WHERE telegram_id = ?", (referrer_id,)).fetchone():
            return False
            
        conn.execute(
            "UPDATE users SET referrer_id = ? WHERE telegram_id = ?",
            (referrer_id, user_id)
        )
        return True

def check_and_give_referral_bonus(referred_id: int):
    """Проверяет и выдает бонус пригласившему пользователю"""
    logging.info(f"Checking referral bonus for user {referred_id}")
    
    with _get_db() as conn:
        # Получаем информацию о пользователе и его реферере
        user_info = conn.execute("""
            SELECT referrer_id, used_trial 
            FROM users 
            WHERE telegram_id = ?
        """, (referred_id,)).fetchone()
        
        if not user_info or not user_info[0]:
            logging.warning(f"No referrer found for user {referred_id}")
            return None

        referrer_id = user_info[0]
        used_trial = user_info[1]
        
        logging.info(f"Found referrer {referrer_id} for user {referred_id}, trial used: {used_trial}")
        
        # Проверяем, использовал ли пользователь пробный период
        if not used_trial:
            logging.info(f"User {referred_id} hasn't used trial yet, no bonus")
            return None
        
        # Проверяем, не был ли уже выдан бонус
        bonus_exists = conn.execute("""
            SELECT 1 FROM referral_bonuses 
            WHERE referrer_id = ? AND referred_id = ?
        """, (referrer_id, referred_id)).fetchone()
        
        if bonus_exists:
            logging.info(f"Bonus already exists for referrer {referrer_id} and user {referred_id}")
            return None
            
        # Выдаем бонус
        try:
            conn.execute("""
                INSERT INTO referral_bonuses (referrer_id, referred_id, bonus_given_at) 
                VALUES (?, ?, datetime('now'))
            """, (referrer_id, referred_id))
            logging.info(f"Successfully added bonus for referrer {referrer_id} from user {referred_id}")
            return referrer_id
        except Exception as e:
            logging.error(f"Error giving bonus to referrer {referrer_id}: {e}")
            return None

def get_referral_count(user_id: int) -> int:
    """Возвращает количество успешных рефералов пользователя"""
    logging.info(f"Getting referral count for user {user_id}")
    
    with _get_db() as conn:
        # Сначала проверяем по таблице referral_bonuses (успешные активации)
        bonus_result = conn.execute("""
            SELECT COUNT(*) FROM referral_bonuses 
            WHERE referrer_id = ?
        """, (user_id,)).fetchone()
        bonus_count = bonus_result[0] if bonus_result else 0
        logging.info(f"Found {bonus_count} bonus records for user {user_id}")
        
        # Также проверяем просто приглашенных пользователей
        users_result = conn.execute("""
            SELECT COUNT(*) FROM users 
            WHERE referrer_id = ?
        """, (user_id,)).fetchone()
        users_count = users_result[0] if users_result else 0
        logging.info(f"Found {users_count} referred users for user {user_id}")
        
        # Проверяем детали каждого реферала
        referred_users = conn.execute("""
            SELECT telegram_id, used_trial FROM users 
            WHERE referrer_id = ?
        """, (user_id,)).fetchall()
        if referred_users:
            logging.info(f"Referred users details for {user_id}:")
            for ref_id, used_trial in referred_users:
                logging.info(f"- User {ref_id}: trial used: {used_trial}")
        
        final_count = max(bonus_count, users_count)
        logging.info(f"Final referral count for user {user_id}: {final_count}")
        return final_count

def get_referral_link(user_id: int, bot_username: str) -> str:
    """Генерирует реферальную ссылку"""
    return f"https://t.me/{bot_username}?start=ref_{user_id}"
