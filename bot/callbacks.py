from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from keyboards.admin_menu import get_restart_confirm
from config import ADMIN_IDS
from core.xray import reset_all_remote, create_vless_key
from database.db import (
    clear_all_cache, has_used_trial, set_trial_period, save_vless_key, 
    get_vless_key, check_and_give_referral_bonus, extend_key_period
)
from database.referral import get_referral_stats
from bot.texts import (
    TRIAL_ALREADY_USED_TEXT, TRIAL_SUCCESS_TEXT, MY_KEY_TEXT,
    REFERRAL_BONUS_RECEIVED
)
from datetime import datetime, timedelta
import uuid as uuidlib
import logging

logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(lambda c: c.data == "admin_restart_confirm")
async def admin_restart_confirm(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("⛔️ Нет доступа", show_alert=True)
        return
    
    await call.message.edit_text("⏳ Перезапуск...")
    try:
        # Сбрасываем базу данных
        from database.models import reset_db
        reset_db()
        
        # Сбрасываем удаленный сервер
        result = reset_all_remote()
        clear_all_cache()
        
        result_text = "✅ База данных сброшена\n" + result
        
    except Exception as e:
        result_text = f"Ошибка: {e}"
        logger.error(f"Restart error: {e}")
    
    for admin_id in ADMIN_IDS:
        await call.bot.send_message(admin_id, f"♻ Перезапуск выполнен:\n{result_text}")
    await call.message.edit_text(f"♻ Перезапуск выполнен:\n{result_text}")
from keyboards.admin_menu import get_restart_confirm
from config import ADMIN_IDS
from core.xray import reset_all_remote, create_vless_key
from database.db import (
    clear_all_cache, has_used_trial, set_trial_period, save_vless_key, 
    get_vless_key, check_and_give_referral_bonus, extend_key_period
)
from bot.texts import (
    TRIAL_ALREADY_USED_TEXT, TRIAL_SUCCESS_TEXT, MY_KEY_TEXT,
    REFERRAL_BONUS_RECEIVED
)
from datetime import datetime, timedelta
import uuid as uuidlib
import logging

logger = logging.getLogger(__name__)

router = Router()
@router.callback_query(lambda c: c.data == "admin_restart")
async def admin_restart(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("⛔️ Нет доступа", show_alert=True)
        return
    await call.message.answer("Вы уверены, что хотите выполнить полный сброс и перезапуск?", reply_markup=get_restart_confirm())

@router.callback_query(lambda c: c.data == "admin_restart_cancel")
async def admin_restart_cancel(call: CallbackQuery):
    await call.message.answer("Операция отменена.")

@router.callback_query(lambda c: c.data == "admin_restart_confirm")
async def admin_restart_confirm(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("⛔️ Нет доступа", show_alert=True)
        return
    
    await call.message.edit_text("⏳ Перезапуск...")
    try:
        result = reset_all_remote()
        clear_all_cache()
    except Exception as e:
        result = f"Ошибка: {e}"
        logger.error(f"Restart error: {e}")
    
    for admin_id in ADMIN_IDS:
        await call.bot.send_message(admin_id, f"♻ Перезапуск выполнен:\n{result}")
    await call.message.edit_text(f"♻ Перезапуск выполнен:\n{result}")


@router.callback_query(lambda c: c.data == "get_trial")
async def get_trial_callback(call: CallbackQuery):
    user_id = call.from_user.id
    logging.info(f"Trial request from user {user_id}")
    
    if has_used_trial(user_id):
        logging.info(f"User {user_id} already used trial")
        await call.answer(TRIAL_ALREADY_USED_TEXT, show_alert=True)
    else:
        now = datetime.now()
        end = now + timedelta(days=3)
        uuid_str = str(uuidlib.uuid4())
        
        # Генерируем ключ через xray_manager
        try:
            logging.info(f"Creating VLESS key for user {user_id}")
            create_vless_key(uuid_str, 3, user_id)
        except Exception as e:
            logging.error(f"Error creating key for user {user_id}: {e}")
            import html
            await call.message.answer(f"Ошибка выдачи ключа: {html.escape(str(e))}", parse_mode=None)
            return
            
        # Сохраняем информацию о пробном периоде
        logging.info(f"Setting trial period for user {user_id}")
        set_trial_period(user_id, now.isoformat(), end.isoformat())
        save_vless_key(user_id, uuid_str, end.isoformat())
        
        # Проверяем и выдаем бонус пригласившему
        logging.info(f"Checking referral bonus for trial activation by user {user_id}")
        referrer_id = check_and_give_referral_bonus(user_id)
        if referrer_id:
            logging.info(f"Found referrer {referrer_id} for user {user_id}, extending subscription")
            # Продлеваем подписку реферера на 3 дня
            key_info = get_vless_key(referrer_id)
            if key_info[0]:  # если есть активный ключ
                try:
                    # Создаем клавиатуру с кнопкой получения бонуса
                    bonus_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🎁 Получить 3 дня", callback_data=f"claim_bonus_{key_info[0]}")],
                    ])
                    await call.bot.send_message(
                        referrer_id,
                        REFERRAL_BONUS_RECEIVED,
                        reply_markup=bonus_keyboard,
                        parse_mode="HTML"
                    )
                    logging.info(f"Sent bonus notification to referrer {referrer_id}")
                except Exception as e:
                    logging.error(f"Error extending key for referrer {referrer_id}: {e}")
        
        # Отправляем ключ пользователю
        vless_url = f"vless://{uuid_str}@213.218.238.165:443?security=reality&type=tcp&flow=xtls-rprx-vision&sni=www.microsoft.com&fp=chrome&pbk=hUmvvDrvaA64rmZMO4fINNi9LQR2MfUjV0XChO9-sWM&sid=9591ef292fb31c63#{call.from_user.first_name}"
        logging.info(f"Generated VLESS URL for user {user_id}")
        try:
            # Отправляем ключ
            await call.message.edit_text(TRIAL_SUCCESS_TEXT.format(key=vless_url))
            
            # Отправляем инструкцию
            from keyboards.main_menu import get_instruction_menu
            await call.message.answer(
                "📱 Чтобы начать пользоваться VPN, установите приложение и настройте его, следуя инструкции:",
                reply_markup=get_instruction_menu()
            )
        except:
            # В случае ошибки редактирования, отправляем новыми сообщениями
            await call.message.answer(TRIAL_SUCCESS_TEXT.format(key=vless_url))
            
            from keyboards.main_menu import get_instruction_menu
            await call.message.answer(
                "📱 Чтобы начать пользоваться VPN, установите приложение и настройте его, следуя инструкции:",
                reply_markup=get_instruction_menu()
            )
        
        try:
            await call.answer()
        except:
            pass  # Игнорируем ошибку устаревшего callback

@router.callback_query(lambda c: c.data == "my_key")
async def my_key_callback(call: CallbackQuery):
    user_id = call.from_user.id
    uuid_str, expires_at = get_vless_key(user_id)
    if not uuid_str:
        await call.answer("У вас нет активного ключа.", show_alert=True)
        return
    
    # Считаем сколько дней осталось
    try:
        days_left = (datetime.fromisoformat(expires_at) - datetime.now()).days
        if days_left < 0:
            days_left = 0
    except Exception:
        days_left = 0
        
    # Создаем клавиатуру с кнопками
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="main_back")]
    ])
    
    # Получаем статистику рефералов
    referral_count, available_bonus_days, used_bonus_days = get_referral_stats(user_id)
    total_days = days_left + available_bonus_days
    
    vless_url = f"vless://{uuid_str}@213.218.238.165:443?security=reality&type=tcp&flow=xtls-rprx-vision&sni=www.microsoft.com&fp=chrome&pbk=hUmvvDrvaA64rmZMO4fINNi9LQR2MfUjV0XChO9-sWM&sid=9591ef292fb31c63#{call.from_user.first_name}"
    await call.message.edit_text(
        MY_KEY_TEXT.format(
            key=vless_url,
            days=days_left,
            bonus_days=available_bonus_days,
            total_days=days_left + available_bonus_days
        ),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await call.answer()

@router.callback_query(lambda c: c.data.startswith("claim_bonus_"))
async def claim_bonus(call: CallbackQuery):
    """Обработчик получения реферального бонуса"""
    user_id = call.from_user.id
    key_uuid = call.data.replace("claim_bonus_", "")
    logging.info(f"User {user_id} claiming bonus for key {key_uuid}")
    
    try:
        # Продлеваем ключ на 3 дня
        new_expiry = extend_key_period(user_id, key_uuid, 3)
        if new_expiry:
            # Форматируем дату для вывода
            from datetime import datetime
            exp_date = datetime.fromisoformat(new_expiry).strftime('%d.%m.%Y')
            
            await call.message.edit_text(
                f"✅ <b>Бонус успешно начислен!</b>\n\n"
                f"Ваша подписка продлена на 3 дня\n"
                f"Действует до: {exp_date}",
                parse_mode="HTML"
            )
            logging.info(f"Successfully extended key for user {user_id} until {new_expiry}")
        else:
            await call.answer("❌ Не удалось применить бонус", show_alert=True)
            logging.error(f"Failed to extend key for user {user_id}")
    except Exception as e:
        logging.error(f"Error claiming bonus for user {user_id}: {e}")
        await call.answer("❌ Произошла ошибка при начислении бонуса", show_alert=True)

def register_callbacks(dp):
    dp.include_router(router)
