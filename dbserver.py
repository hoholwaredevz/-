import sqlite3

# Подключаемся к базе данных
conn = sqlite3.connect('whitelist.db')
cursor = conn.cursor()

# Создаем таблицу для аккаунтов
cursor.execute('''CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT NOT NULL,
    premium_end_date TEXT,
    hwid TEXT DEFAULT 'nothwided',
    recovery_key TEXT
)''')

# Создаем таблицу для ключей
cursor.execute('''CREATE TABLE IF NOT EXISTS keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_value TEXT,
    days_valid INTEGER,
    uses INTEGER
)''')

conn.commit()
conn.close()
