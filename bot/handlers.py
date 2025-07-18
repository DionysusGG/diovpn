from database.db import (
    add_user, get_vless_key, extend_key_period, _get_db
)
from database.referral import (
    save_referrer, get_referral_link, get_referral_stats,
    get_referral_count
)
from aiogram import Router, types, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, PreCheckoutQuery, CallbackQuery
from keyboards.main_menu import get_main_menu, get_buy_menu, get_referral_menu
from keyboards.admin_menu import get_admin_menu
from config import ADMIN_IDS
from bot.texts import (
    WELCOME_TEXT, REFERRAL_MENU_TEXT,
    REFERRAL_INVALID, SELF_REFERRAL_ERROR
)
from datetime import datetime, timedelta
import re
import logging

router = Router()

from utils.helpers import parse_date

def get_pay_menu(period, price, callback_back):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💸 Оплатить {price}⭐", callback_data=f"pay_{period}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=callback_back)],
    ])

@router.callback_query(lambda c: c.data == "admin_back")
async def admin_back(call: types.CallbackQuery):
    await call.message.delete()

@router.callback_query(lambda c: c.data == "buy_menu")
async def buy_menu(call: types.CallbackQuery):
    await call.message.edit_text(
        "Выберите период подписки:",
        reply_markup=get_buy_menu()
    )

@router.callback_query(lambda c: c.data.startswith("buy_"))
async def buy_period(call: types.CallbackQuery):
    periods = {
        "buy_1m": ("1 месяц", "99"),
        "buy_3m": ("3 месяца", "249"),
        "buy_6m": ("6 месяцев", "449"),
        "buy_12m": ("1 год", "799"),
    }
    period_key = call.data
    period, price = periods.get(period_key, (None, None))
    if not period:
        await call.answer("Ошибка выбора периода", show_alert=True)
        return
    text = f"Вы выбрали: <b>{period}</b>\nСтоимость: <b>{price}⭐</b>\n\nДля оплаты нажмите кнопку ниже."
    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_pay_menu(period_key, price, "buy_menu")
    )

@router.callback_query(lambda c: c.data.startswith("pay_"))
async def pay_period(call: types.CallbackQuery):
    periods = {
        "pay_buy_1m": ("1 месяц", "99", 30),
        "pay_buy_3m": ("3 месяца", "249", 90),
        "pay_buy_6m": ("6 месяцев", "449", 180),
        "pay_buy_12m": ("1 год", "799", 365),
    }
    period_key = call.data.replace("pay_", "buy_")
    period_info = periods.get(call.data)
    if not period_info:
        await call.answer("Ошибка оплаты", show_alert=True)
        return
    
    period, price, days = period_info
    
    await call.bot.send_invoice(
        chat_id=call.from_user.id,
        title=f"VPN на {period}",
        description=f"Подписка на VPN сервис на {period}",
        payload=f"{call.from_user.id}:{days}",  # Сохраняем ID пользователя и количество дней
        provider_token="",  # Замените на реальный токен Stars
        currency="XTR",
        prices=[{"label": f"VPN на {period}", "amount": int(price)}],
        start_parameter="vpn_subscription",
        photo_url="",  # URL изображения
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        is_flexible=False
    )
    await call.message.delete()

@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@router.message(lambda message: message.successful_payment)
async def process_successful_payment(message: Message):
    # Получаем информацию о платеже
    payment = message.successful_payment
    payload = payment.invoice_payload
    user_id, days = map(int, payload.split(":"))
    
    # Создаем новый ключ VPN для пользователя
    from core.xray import create_vless_key
    from database.db import save_vless_key
    
    # Генерируем дату окончания подписки
    end_date = datetime.now() + timedelta(days=days)
    
    # Создаем новый ключ
    uuid = await create_vless_key()
    if uuid:
        # Сохраняем ключ в базу
        save_vless_key(user_id, uuid, end_date)
        
        # Сначала отправляем сообщение об успешной оплате
        await message.answer(
            f"✅ Оплата успешно получена!\n\n"
            f"Ваш VPN ключ создан и действует до: {end_date.strftime('%d.%m.%Y')}\n\n"
            f"Для просмотра ключа нажмите на кнопку 'Мой ключ' в главном меню."
        )
        
        # Затем отправляем сообщение с инструкцией
        from keyboards.main_menu import get_instruction_menu
        await message.answer(
            "📱 Чтобы начать пользоваться VPN, установите приложение и настройте его, следуя инструкции:",
            reply_markup=get_instruction_menu()
        )
    else:
        await message.answer(
            "❌ Произошла ошибка при создании ключа.\n"
            "Пожалуйста, обратитесь в поддержку.",
            reply_markup=get_main_menu()
        )

@router.callback_query(lambda c: c.data == "main_back")
async def main_back(call: types.CallbackQuery):
    await call.message.edit_text(
        WELCOME_TEXT,
        reply_markup=get_main_menu()
    )

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработка команды /start"""
    user_id = message.from_user.id
    logging.info(f"Start command from user {user_id}: {message.text}")
    
    # Проверяем на наличие реферальной ссылки
    if len(message.text.split()) > 1:
        ref_arg = message.text.split()[1]
        if ref_arg.startswith('ref_'):
            try:
                referrer_id = int(ref_arg[4:])
                logging.info(f"Referral detected: user {user_id} invited by {referrer_id}")
                
                # Проверяем на самореферальство
                if referrer_id == user_id:
                    logging.warning(f"Self-referral attempt by user {user_id}")
                    await message.answer(SELF_REFERRAL_ERROR)
                    add_user(user_id)  # Добавляем без реферера
                    return

                # Добавляем пользователя с реферером
                add_user(user_id, referrer_id)
                
                # Проверяем что реферер сохранился
                from database.db import _get_db
                with _get_db() as conn:
                    saved_referrer = conn.execute(
                        "SELECT referrer_id FROM users WHERE telegram_id = ?",
                        (user_id,)
                    ).fetchone()
                logging.info(f"Saved referrer for user {user_id}: {saved_referrer}")
                
            except ValueError as e:
                logging.error(f"Invalid referral format: {ref_arg}, error: {e}")
                await message.answer(REFERRAL_INVALID)
                add_user(user_id)
                return
    else:
        # Обычный старт без реферальной ссылки
        add_user(user_id)
    
    await message.answer(WELCOME_TEXT, reply_markup=get_main_menu())

@router.message(Command("admin"))
async def admin_menu(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔️ Нет доступа")
        return
    await message.answer("Админ-панель:", reply_markup=get_admin_menu())

@router.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats(call: types.CallbackQuery):
    from database.db import get_trial_users_info
    users = get_trial_users_info()
    if not users:
        text = "Нет пользователей с пробным периодом."
    else:
        lines = ["Пробный период:"]
        for uid, start, end in users:
            # Форматируем даты
            start_date = parse_date(start).strftime('%d/%m/%Y %H:%M')
            end_date = parse_date(end).strftime('%d/%m/%Y %H:%M')
            lines.append(f"ID: {uid}\nПолучен: {start_date}\nОкончание: {end_date}")
        text = "\n\n".join(lines)
    await call.message.edit_text(text, reply_markup=get_admin_menu())

@router.callback_query(lambda c: c.data == "admin_keys")
async def admin_keys(call: types.CallbackQuery):
    from database.db import get_all_active_keys
    keys = get_all_active_keys()
    if not keys:
        text = "Нет активных ключей."
    else:
        lines = ["Активные ключи:"]
        for user_id, uuid, expires_at in keys:
            exp_date = parse_date(expires_at)
            days_left = (exp_date - datetime.now()).days
            lines.append(
                f"ID: {user_id}\n"
                f"Ключ: {uuid}\n"
                f"Осталось дней: {days_left}\n"
                f"Истекает: {exp_date.strftime('%d/%m/%Y %H:%M')}"
            )
        text = "\n\n".join(lines)
    await call.message.edit_text(text, reply_markup=get_admin_menu())

@router.callback_query(lambda c: c.data == "renew")
async def renew_subscription(call: types.CallbackQuery):
    from database.db import get_user_active_key
    key_info = get_user_active_key(call.from_user.id)
    
    if not key_info:
        await call.message.edit_text(
            "У вас нет активных ключей для продления.\n"
            "Вы можете приобрести новый ключ, нажав кнопку 'Купить'.",
            reply_markup=get_main_menu()
        )
        return
    
    uuid, expires_at = key_info
    exp_date = parse_date(expires_at)
    days_left = (exp_date - datetime.now()).days
    
    await call.message.edit_text(
        f"Ваш текущий ключ действует ещё {days_left} дней (до {exp_date.strftime('%d.%m.%Y %H:%M')}).\n\n"
        f"Выберите период продления:",
        reply_markup=get_buy_menu()  # Используем то же меню, что и для покупки
    )

@router.message(CommandStart(deep_link=True))
async def cmd_start_ref(message: Message):
    """Обработка старта с реферальной ссылкой"""
    logging.info(f"Start command with args from user {message.from_user.id}: {message.text}")
    
    referral_arg = message.text.split()[1]
    if referral_arg.startswith('ref_'):
        try:
            referrer_id = int(referral_arg[4:])
            logging.info(f"Parsed referrer_id: {referrer_id}")
            
            # Проверяем самореферальство
            if referrer_id == message.from_user.id:
                logging.warning(f"Self-referral attempt by user {message.from_user.id}")
                await message.answer(SELF_REFERRAL_ERROR)
                add_user(message.from_user.id)  # Добавляем пользователя без реферера
                return

            # Добавляем пользователя с реферером
            logging.info(f"Adding user {message.from_user.id} with referrer {referrer_id}")
            add_user(message.from_user.id, referrer_id)
            
            # Проверяем успешность добавления
            from database.db import _get_db
            with _get_db() as conn:
                result = conn.execute(
                    "SELECT referrer_id FROM users WHERE telegram_id = ?",
                    (message.from_user.id,)
                ).fetchone()
                logging.info(f"Database check after add_user: {result}")
            
        except ValueError as e:
            logging.error(f"Invalid referral format: {referral_arg}, error: {e}")
            await message.answer(REFERRAL_INVALID)
            add_user(message.from_user.id)  # Добавляем пользователя без реферера
            return
        except Exception as e:
            logging.error(f"Unexpected error in cmd_start_ref: {e}")
            await message.answer(REFERRAL_INVALID)
            add_user(message.from_user.id)
            return
    else:
        logging.info(f"Regular start without referral for user {message.from_user.id}")
        add_user(message.from_user.id)
    
    await cmd_start(message)

@router.callback_query(lambda c: c.data == "invite_friend")
async def invite_friend(call: CallbackQuery):
    """Показывает реферальную ссылку"""
    user_id = call.from_user.id
    logging.info(f"Showing referral menu for user {user_id}")
    
    # Получаем информацию о рефералах
    bot = await call.bot.get_me()
    referral_link = get_referral_link(user_id, bot.username)
    logging.info(f"Generated referral link: {referral_link}")
    
    # Получаем статистику рефералов
    referral_count, available_bonus_days, used_bonus_days = get_referral_stats(user_id)
    logging.info(f"Referral stats for user {user_id}: count={referral_count}, available={available_bonus_days}, used={used_bonus_days}")
    
    try:
        # Получаем информацию о ключе пользователя
        uuid_str, expires_at = get_vless_key(user_id)
        remaining_days = 0
        if expires_at:
            try:
                remaining_days = (datetime.fromisoformat(expires_at) - datetime.now()).days
                if remaining_days < 0:
                    remaining_days = 0
            except Exception as e:
                logging.error(f"Error calculating remaining days: {e}")
                
        total_days = remaining_days + available_bonus_days
        
        await call.message.edit_text(
            REFERRAL_MENU_TEXT.format(
                invited=referral_count,
                days=available_bonus_days,
                remaining_days=remaining_days,
                total_days=total_days
            ),
            reply_markup=get_referral_menu(referral_link, referral_count),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Error showing referral menu to user {user_id}: {e}")
        try:
            await call.answer("Произошла ошибка при показе меню", show_alert=True)
        except:
            pass

@router.callback_query(lambda c: c.data == "copy_ref_link")
async def copy_ref_link(call: CallbackQuery):
    """Отправляет ссылку в виде текста для копирования"""
    try:
        bot = await call.bot.get_me()
        referral_link = get_referral_link(call.from_user.id, bot.username)
        
        # Отправляем ссылку отдельным сообщением для копирования
        await call.message.answer(
            f"<code>{referral_link}</code>",
            parse_mode="HTML"
        )
        
        try:
            await call.answer("Ссылка отправлена в чат", show_alert=False)
        except:
            pass  # Игнорируем ошибку устаревшего callback
            
    except Exception as e:
        logging.error(f"Error in copy_ref_link: {e}")
        try:
            await call.answer("Произошла ошибка", show_alert=True)
        except:
            pass
    
@router.callback_query(lambda c: c.data == "ref_stats")
async def ref_stats(call: CallbackQuery):
    """Показывает подробную статистику рефералов"""
    try:
        referral_count = get_referral_count(call.from_user.id)
        days_earned = referral_count * 3
        
        try:
            await call.answer(
                f"Вы пригласили {referral_count} друзей\n"
                f"Заработано дней: {days_earned}",
                show_alert=True
            )
        except:
            await call.message.answer(
                f"📊 Статистика рефералов:\n"
                f"👥 Приглашено друзей: {referral_count}\n"
                f"⏰ Заработано дней: {days_earned}"
            )
            
    except Exception as e:
        logging.error(f"Error in ref_stats: {e}")
        try:
            await call.answer("Произошла ошибка", show_alert=True)
        except:
            pass

def register_handlers(dp):
    dp.include_router(router)
