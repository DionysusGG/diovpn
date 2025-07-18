from datetime import datetime
import asyncio
import logging
from database.db import DB_PATH, get_keys_expiring_soon
import sqlite3
from core.xray import remove_vless_key
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN
from bot.handlers import parse_date

# Настройка логирования
logger = logging.getLogger(__name__)

def get_days_word(days: int) -> str:
    """Возвращает правильное склонение слова 'дни'"""
    if days % 10 == 1 and days % 100 != 11:
        return "день"
    elif 2 <= days % 10 <= 4 and (days % 100 < 10 or days % 100 >= 20):
        return "дня"
    else:
        return "дней"

async def send_expiration_notice(bot: Bot, user_id: int, days_left: int, expires_at: str):
    """Отправляет уведомление о скором истечении ключа"""
    exp_date = parse_date(expires_at)
    formatted_date = exp_date.strftime('%d/%m/%Y %H:%M')
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="renew")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="main_back")]
    ])
    
    text = (f"⚠️ Ваш VPN ключ истекает через {days_left} {get_days_word(days_left)}!\n"
            f"Дата окончания: {formatted_date}\n\n"
            f"Нажмите кнопку ниже, чтобы продлить доступ:")
    try:
        await bot.send_message(user_id, text, reply_markup=keyboard)
    except Exception as e:
        print(f"Failed to send notification to {user_id}: {e}")

async def check_expired_keys():
    """Проверяет и удаляет просроченные ключи, отправляет уведомления"""
    session = AiohttpSession()
    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    try:
        while not asyncio.current_task().cancelled():
            try:
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Получаем и обрабатываем просроченные ключи
                with sqlite3.connect(DB_PATH) as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT telegram_id, uuid FROM keys 
                        WHERE expires_at < ?
                    """, (current_time,))
                    expired_keys = cur.fetchall()
                    
                    # Удаляем каждый просроченный ключ
                    for telegram_id, uuid in expired_keys:
                        try:
                            await remove_vless_key(uuid)
                            cur.execute("""
                                DELETE FROM keys 
                                WHERE telegram_id = ? AND uuid = ?
                            """, (telegram_id, uuid))
                        except Exception as e:
                            logger.error(f"Ошибка удаления ключа {uuid[:8]}: {e}")
                    conn.commit()
                
                # Проверяем ключи, которые скоро истекут
                expiring_keys = get_keys_expiring_soon(days_threshold=3)
                for telegram_id, uuid, expires_at in expiring_keys:
                    try:
                        days_left = (parse_date(expires_at) - datetime.now()).days
                        if days_left in [1, 3]:  # Уведомляем за 3 дня и за 1 день
                            formatted_date = parse_date(expires_at).strftime('%d/%m/%Y %H:%M')
                            await send_expiration_notice(bot, telegram_id, days_left, formatted_date)
                    except Exception as e:
                        logger.error(f"Ошибка отправки уведомления для ключа {uuid[:8]}: {e}")
                        
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Ошибка в планировщике: {e}")
            
            # Проверяем каждый час
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                raise
                
    finally:
        await bot.session.close()
