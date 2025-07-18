import sqlite3

DB_PATH = "database/vless_bot.db"

CREATE_TABLES = {
    'keys': """
    CREATE TABLE IF NOT EXISTS keys (
        telegram_id INTEGER PRIMARY KEY,
        uuid TEXT NOT NULL,
        expires_at TEXT NOT NULL
    );""",
    'users': """
    CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY,
        subscription_start TEXT,
        subscription_end TEXT,
        used_trial BOOLEAN DEFAULT 0,
        referrer_id INTEGER,
        FOREIGN KEY(referrer_id) REFERENCES users(telegram_id)
    )""",
    'users_index': """
    CREATE INDEX IF NOT EXISTS idx_users_referrer ON users(referrer_id)
    """,
    'referral_bonuses': """
    CREATE TABLE IF NOT EXISTS referral_bonuses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER NOT NULL,
        referred_id INTEGER NOT NULL,
        bonus_days INTEGER DEFAULT 3,
        bonus_given_at TEXT DEFAULT NULL,
        UNIQUE(referrer_id, referred_id),
        FOREIGN KEY(referrer_id) REFERENCES users(telegram_id),
        FOREIGN KEY(referred_id) REFERENCES users(telegram_id)
    );"""
}

def reset_db():
    """Удаляет базу данных полностью"""
    import os
    try:
        os.remove(DB_PATH)
        print(f"База данных {DB_PATH} успешно удалена")
    except FileNotFoundError:
        print(f"База данных {DB_PATH} не существует")
    init_db()
    print("База данных создана заново")

def init_db():
    """Инициализация базы данных с миграциями"""
    print(f"Инициализация базы данных {DB_PATH}...")
    
    # Создаем директорию для базы если её нет
    import os
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    with sqlite3.connect(DB_PATH) as conn:
        # Создаем основные таблицы
        for name, table_sql in CREATE_TABLES.items():
            print(f"Создание таблицы {name}...")
            conn.execute(table_sql)
            
    print("Инициализация базы данных завершена")
