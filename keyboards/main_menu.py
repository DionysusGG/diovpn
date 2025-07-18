from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Получить пробный доступ", callback_data="get_trial")],
        [InlineKeyboardButton(text="💳 Купить", callback_data="buy_menu")],
        [InlineKeyboardButton(text="📊 Мой ключ", callback_data="my_key")],
        [InlineKeyboardButton(text="🔁 Продлить", callback_data="renew")],
        [InlineKeyboardButton(text="👥 Пригласить друга", callback_data="invite_friend")],
        [InlineKeyboardButton(text=" Инструкция", url=get_guide_link())],
        [InlineKeyboardButton(text="🛠️ Поддержка", url="tg://user?id=7975271183")],
    ])

def get_buy_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 месяц — 99⭐", callback_data="buy_1m")],
        [InlineKeyboardButton(text="3 месяца — 249⭐", callback_data="buy_3m")],
        [InlineKeyboardButton(text="6 месяцев — 449⭐", callback_data="buy_6m")],
        [InlineKeyboardButton(text="1 год — 799⭐", callback_data="buy_12m")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_back")],
    ])

def get_guide_link():
    try:
        with open("static/guide_link.txt", "r") as f:
            return f.read().strip()
    except Exception:
        return "https://example.com/guide"

def get_referral_menu(referral_link: str, referral_count: int):
    """Создает меню реферальной системы с кнопками копирования и шеринга"""
    share_text = "Привет! Хочу поделиться с тобой крутым VPN сервисом. Получи 3 дня бесплатно по моей реферальной ссылке 😊"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📋 Скопировать ссылку",
            callback_data="copy_ref_link"
        )],
        [InlineKeyboardButton(
            text="📤 Поделиться в Telegram",
            url=f"https://t.me/share/url?text={share_text}&url={referral_link}"
        )],
        [InlineKeyboardButton(text=f"👥 Приглашено друзей: {referral_count}", callback_data="ref_stats")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="main_back")],
    ])

def get_instruction_menu():
    """Создает меню с кнопкой инструкции"""
    guide_link = get_guide_link()
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Инструкция по настройке", url=guide_link)],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="main_back")],
    ])
