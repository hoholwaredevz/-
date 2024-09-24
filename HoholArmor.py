import discord
from discord.ext import commands, tasks
import sqlite3
import uuid
import datetime

# Настройки
DISCORD_TOKEN = 'MTI3ODc3MzIwMjY3OTYyNzc3Ng.Gsc7UM.DGHzFMimGWPbiqFE4kD5t1GblFjdGWQQnPbTIs'

# Настройка бота
bot = commands.Bot(command_prefix='!')

# Подключение к базе данных SQLite
def connect_db():
    conn = sqlite3.connect('whitelist.db')
    return conn

def setup_db():
    conn = connect_db()
    cursor = conn.cursor()
    
    # Таблица аккаунтов
    cursor.execute('''CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        discord_id TEXT NOT NULL,
        premium_end_date TEXT,
        hwid TEXT DEFAULT 'nothwided',
        recovery_key TEXT
    )''')
    
    # Таблица ключей
    cursor.execute('''CREATE TABLE IF NOT EXISTS keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key_value TEXT,
        days_valid INTEGER,
        uses INTEGER
    )''')
    
    conn.commit()
    conn.close()

setup_db()

def generate_uuid_v4():
    return str(uuid.uuid4())

def is_premium_active(premium_end_date):
    """Проверяет, активен ли премиум."""
    if premium_end_date == "None":
        return False  # Премиум истек
    current_date = datetime.datetime.now()
    try:
        end_date = datetime.datetime.strptime(premium_end_date, '%Y-%m-%d')
        return end_date > current_date
    except ValueError:
        return False

@tasks.loop(hours=24)
async def check_premium():
    """Периодическая проверка истечения срока премиума."""
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, discord_id, premium_end_date FROM accounts")
    accounts = cursor.fetchall()
    current_date = datetime.datetime.now()

    for account in accounts:
        account_id, discord_id, premium_end_date = account
        if is_premium_active(premium_end_date):
            print(f"Премиум активен для {discord_id}.")
        else:
            cursor.execute("UPDATE accounts SET premium_end_date = 'None' WHERE id = ?", (account_id,))
            print(f"Премиум истек для {discord_id}, дата премиума теперь None.")
    
    conn.commit()
    conn.close()

@bot.event
async def on_ready():
    print(f'Бот {bot.user.name} запущен и готов к работе')
    await bot.change_presence(activity=discord.Game(name=f'Бот запущен'))
    check_premium.start()  # Запуск задачи проверки истечения премиума

@bot.command(name="generate_key")
@commands.has_any_role(1285692238395084873, 1282539277758234727)
async def generate_key(ctx, days_valid: int, uses: int):
    """Генерация ключа с указанием количества дней действия и количества использований."""
    conn = connect_db()
    cursor = conn.cursor()

    new_uuid = generate_uuid_v4()
    cursor.execute("INSERT INTO keys (key_value, days_valid, uses) VALUES (?, ?, ?)",
                   (new_uuid, days_valid, uses))
    conn.commit()
    conn.close()

    await ctx.send(f'Новый ключ создан: {new_uuid}, действует {days_valid} дней, использований: {uses}')

@bot.command(name="create_account")
async def create_account(ctx):
    """Создание нового аккаунта с recovery ключом."""
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send('Эту команду можно использовать только в ЛС.')
        return

    conn = connect_db()
    cursor = conn.cursor()
    discord_id = str(ctx.author.id)

    # Проверяем, существует ли уже аккаунт для данного Discord ID
    cursor.execute("SELECT * FROM accounts WHERE discord_id = ?", (discord_id,))
    account = cursor.fetchone()

    if account:
        await ctx.send('У вас уже есть аккаунт.')
    else:
        recovery_key = generate_uuid_v4()
        cursor.execute("INSERT INTO accounts (discord_id, premium_end_date, hwid, recovery_key) VALUES (?, ?, ?, ?)",
                       (discord_id, "None", "nothwided", recovery_key))
        conn.commit()
        await ctx.send(f'Аккаунт успешно создан. Ваш recovery ключ: {recovery_key}. Сохраните его.')
    
    conn.close()

@bot.command(name="use_key")
async def use_key(ctx, key: str):
    """Активация премиума для существующего аккаунта и выдача роли."""
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send('Эту команду можно использовать только в ЛС.')
        return

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM keys WHERE key_value = ?", (key,))
    key_data = cursor.fetchone()

    if not key_data:
        await ctx.send('Ключ не найден.')
        return

    key_id, key_value, days_valid, uses_left = key_data

    if uses_left <= 0:
        await ctx.send('Ключ больше не может быть использован.')
        return

    discord_id = str(ctx.author.id)

    cursor.execute("SELECT * FROM accounts WHERE discord_id = ?", (discord_id,))
    account = cursor.fetchone()

    if account:
        account_id, discord_id, premium_end_date, hwid, recovery_key = account

        if premium_end_date == "None" or premium_end_date == "":
            premium_end_date = datetime.datetime.now() + datetime.timedelta(days=days_valid)
        else:
            premium_end_date = datetime.datetime.strptime(premium_end_date, '%Y-%m-%d') + datetime.timedelta(days=days_valid)

        premium_end_date_str = premium_end_date.strftime('%Y-%m-%d')
        cursor.execute("UPDATE accounts SET premium_end_date = ? WHERE id = ?", (premium_end_date_str, account_id))
        cursor.execute("UPDATE keys SET uses = ? WHERE id = ?", (uses_left - 1, key_id))
        
        conn.commit()
        await ctx.send(f'Ваш премиум активирован/продлён до {premium_end_date_str}.')
    else:
        await ctx.send('Аккаунт не найден. Сначала создайте аккаунт с помощью команды `!create_account`.')

    conn.close()

@bot.command(name='sethwid')
async def sethwid(ctx, hwid: str):
    """Команда для установки HWID. Работает только в личных сообщениях."""
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send('Эту команду можно использовать только в ЛС.')
        return
    
    conn = connect_db()
    cursor = conn.cursor()
    discord_id = str(ctx.author.id)

    cursor.execute("SELECT * FROM accounts WHERE discord_id = ?", (discord_id,))
    account = cursor.fetchone()

    if account and is_premium_active(account[2]):
        cursor.execute("UPDATE accounts SET hwid = ? WHERE discord_id = ?", (hwid, discord_id))
        conn.commit()
        await ctx.send('HWID успешно установлен.')
    else:
        await ctx.send('Не найден активный премиум аккаунт.')

    conn.close()

@bot.command(name="resethwid")
async def reset_hwid(ctx):
    """Команда для сброса HWID. Работает только в личных сообщениях."""
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send('Эту команду можно использовать только в ЛС.')
        return

    conn = connect_db()
    cursor = conn.cursor()
    discord_id = str(ctx.author.id)

    cursor.execute("SELECT * FROM accounts WHERE discord_id = ?", (discord_id,))
    account = cursor.fetchone()

    if account and is_premium_active(account[2]):
        cursor.execute("UPDATE accounts SET hwid = 'nothwided' WHERE discord_id = ?", (discord_id,))
        conn.commit()
        await ctx.send('HWID успешно сброшен. Теперь вы можете установить его снова с помощью команды `sethwid`.')
    else:
        await ctx.send('Не найден активный премиум аккаунт.')

    conn.close()

@bot.command(name="recover_account")
async def recover_account(ctx, recovery_key: str):
    """Восстановление аккаунта по recovery ключу."""
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send('Эту команду можно использовать только в ЛС.')
        return

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM accounts WHERE recovery_key = ?", (recovery_key,))
    account = cursor.fetchone()

    if account:
        cursor.execute("UPDATE accounts SET discord_id = ? WHERE recovery_key = ?", (str(ctx.author.id), recovery_key))
        conn.commit()
        await ctx.send('Ваш аккаунт успешно восстановлен.')
    else:
        await ctx.send('Аккаунт с указанным recovery ключом не найден.')

    conn.close()

@bot.command(name="info")
async def info(ctx):
    """Команда для получения информации о количестве оставшихся дней премиума."""
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send('Эту команду можно использовать только в ЛС.')
        return

    conn = connect_db()
    cursor = conn.cursor()
    discord_id = str(ctx.author.id)

    cursor.execute("SELECT premium_end_date FROM accounts WHERE discord_id = ?", (discord_id,))
    account = cursor.fetchone()

    if account:
        premium_end_date = account[0]
        if premium_end_date == "None" or premium_end_date == "":
            await ctx.send('Ваш премиум закончился.')
        else:
            end_date = datetime.datetime.strptime(premium_end_date, '%Y-%m-%d')
            days_left = (end_date - datetime.datetime.now()).days
            if days_left > 0:
                await ctx.send(f'Осталось {days_left} дней до окончания премиума.')
            else:
                await ctx.send('Ваш премиум закончился.')
    else:
        await ctx.send('У вас нет активного аккаунта.')

    conn.close()

@bot.command(name="script")
async def script(ctx):
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send('Эту команду можно использовать только в ЛС.')
        return
    
    conn = connect_db()
    cursor = conn.cursor()
    discord_id = str(ctx.author.id)

    cursor.execute("SELECT premium_end_date FROM accounts WHERE discord_id = ?", (discord_id,))
    account = cursor.fetchone()

    if account:
        premium_end_date = account[0]
        if premium_end_date == "None" or premium_end_date == "":
            await ctx.send('Ваш премиум закончился.')
        else:
            await ctx.send('Script', file=discord.File("Script.lua"))

bot.run(DISCORD_TOKEN)
