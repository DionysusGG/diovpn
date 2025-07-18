from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔑 Активные ключи", callback_data="admin_keys")],
        [InlineKeyboardButton(text="♻ Перезапуск", callback_data="admin_restart")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back")],
    ])

def get_restart_confirm():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data="admin_restart_confirm")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="admin_restart_cancel")],
    ])
