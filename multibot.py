import asyncio
import os
import sqlite3
import random
from aiohttp import web
from telethon import TelegramClient, events, functions, types, Button
from telethon.errors import UserNotParticipantError

# --- КОНФИГУРАЦИЯ (Заполни свои данные) ---
API_ID = 26241381
API_HASH = 'fe1046e04b4a0196b0e5efcbc4d62093'
BOT_TOKEN = '8536378324:AAGXYrbJE8JYBZVNKHVc220H40579qk7uvY'
ADMIN_ID = 6226140394 
REQUIRED_CHANNEL = 'tgflboost' # Канал без @
SESSIONS_DIR = './sessions'

user_states = {}

# --- БАЗА ДАННЫХ ---
conn = sqlite3.connect("flash_smm_final.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 1000)')
conn.commit()

def get_balance(user_id):
    cursor.execute("SELECT balance FROM users WHERE id=?", (user_id,))
    res = cursor.fetchone()
    if res: return res[0]
    cursor.execute("INSERT INTO users (id, balance) VALUES (?, 1000)", (user_id,))
    conn.commit()
    return 1000

def update_balance(user_id, amount):
    curr = get_balance(user_id)
    cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (curr + amount, user_id))
    conn.commit()

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER (АНТИ-СОН) ---
async def handle(request):
    return web.Response(text="Flashboost is running! 🚀")

async def run_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌐 Web server live on port {port}")

# --- СИСТЕМА КЛИЕНТОВ (БОТОВ) ---
clients = []
async def load_accounts():
    if not os.path.exists(SESSIONS_DIR): os.makedirs(SESSIONS_DIR)
    files = [f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')]
    print(f"📦 Загрузка {len(files)} аккаунтов...")
    for f in files:
        c = TelegramClient(os.path.join(SESSIONS_DIR, f.replace('.session','')), API_ID, API_HASH)
        try:
            await c.start()
            clients.append(c)
        except: pass
    print(f"✅ Готово: {len(clients)} ботов активно")

bot = TelegramClient('flash_manager_supreme', API_ID, API_HASH)

# --- ПРОВЕРКА ПОДПИСКИ ---
async def is_subscribed(user_id):
    if user_id == ADMIN_ID: return True
    try:
        await bot(functions.channels.GetParticipantRequest(channel=REQUIRED_CHANNEL, participant=user_id))
        return True
    except UserNotParticipantError: return False
    except: return True

def parse_link(link):
    try:
        clean = link.replace('https://t.me/', '').replace('@', '').split('/')
        if len(clean) < 2: return clean[0], None
        return clean[0], int(clean[1])
    except: return None, None

# --- ИНТЕРФЕЙС ---
@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    uid = event.sender_id
    if not await is_subscribed(uid):
        await event.respond(
            f"⚠️ **Доступ ограничен!**\n\nДля работы с ботом подпишись на @{REQUIRED_CHANNEL}",
            buttons=[[Button.url("🔗 Подписаться", f"https://t.me/{REQUIRED_CHANNEL}")],
                     [Button.inline("✅ Я подписался", "check_sub")]]
        )
        return

    bal = get_balance(uid)
    user_states[uid] = None
    text = (f"🚀 **FLASHBOOST SUPREME**\n\n"
            f"💰 Баланс: `{bal}` 💎\n"
            f"🤖 Ботов в сети: `{len(clients)}`")
    
    btns = [
        [Button.inline("🛒 Услуги", "services"), Button.inline("📊 Профиль", "info")],
        [Button.inline("💳 Пополнить", "buy")]
    ]
    if uid == ADMIN_ID: btns.append([Button.inline("🛠 Админка", "adm_main")])
    await event.respond(text, buttons=btns)

@bot.on(events.CallbackQuery())
async def callback(event):
    uid = event.sender_id
    data = event.data.decode('utf-8')

    if data == "check_sub":
        if await is_subscribed(uid): await start(event)
        else: await event.answer("❌ Подписка не найдена!", alert=True)
        return

    if not await is_subscribed(uid):
        await event.answer("⚠️ Сначала подпишись!", alert=True)
        return

    if data == "services":
        await event.edit("🛠 **Выберите услугу:**", buttons=[
            [Button.inline("👥 Подписчики", "srv_subs"), Button.inline("❤️ Реакции", "srv_react")],
            [Button.inline("💬 Комменты", "srv_comm"), Button.inline("🗳 Опросы", "srv_vote")],
            [Button.inline("⬅️ Назад", "back")]
        ])

    elif data == "srv_subs":
        user_states[uid] = {'action': 'sub', 'price': 150}
        await event.edit("🔗 **Пришли ссылку на канал.**\n(Публичная или приватная через `+`)")

    elif data == "srv_vote":
        user_states[uid] = {'action': 'vote', 'price': 100}
        await event.edit("🗳 **Пришли ссылку и номер варианта:**\nПример: `https://t.me/канал/1 0` (0 — первый вариант)")

    elif data == "srv_comm":
        user_states[uid] = {'action': 'comm', 'price': 250}
        await event.edit("💬 **Пришли ссылку и тексты:**\n1 строка: ссылка\nДалее: каждый коммент с новой строки.")

    elif data == "adm_main" and uid == ADMIN_ID:
        await event.edit("🛠 **Админ-панель**", buttons=[[Button.inline("💰 Дать монеты", "adm_give")], [Button.inline("⬅️ Назад", "back")]])

    elif data == "adm_give":
        user_states[uid] = {'action': 'adm_give'}
        await event.edit("💳 Формат: `ID сумма` ")

    elif data == "back": await start(event)

# --- ОБРАБОТКА ЗАКАЗОВ ---
@bot.on(events.NewMessage())
async def handle_input(event):
    uid = event.sender_id
    if event.text.startswith('/') or uid not in user_states or not user_states[uid]: return

    state = user_states[uid]
    text = event.text.strip()
    
    if state['action'] == 'adm_give' and uid == ADMIN_ID:
        try:
            tid, am = text.split(' ')
            update_balance(int(tid), int(am))
            await event.respond(f"✅ Пользователю `{tid}` начислено `{am}`")
        except: await event.respond("❌ Ошибка. Формат: `ID сумма` ")
        user_states[uid] = None
        return

    if get_balance(uid) < state.get('price', 0):
        await event.respond("❌ Недостаточно монет!")
        return

    update_balance(uid, -state['price'])
    status = await event.respond("⚙️ **Обработка...**")
    success = 0

    try:
        # Подписчики
        if state['action'] == 'sub':
            is_private = '+' in text or 'joinchat' in text
            h_code = text.split('/')[-1].replace('+', '') if is_private else None
            for c in clients:
                try:
                    if is_private: await c(functions.messages.ImportChatInviteRequest(hash=h_code))
                    else: await c(functions.channels.JoinChannelRequest(text))
                    success += 1
                except: success += 1 # Засчитываем заявки
            await status.edit(f"✅ Готово! Результат: {success}")

        # Опросы
        elif state['action'] == 'vote':
            link, opt = text.split(' ')
            ch, p_id = parse_link(link)
            for c in clients:
                try:
                    await c(functions.messages.SendVoteRequest(peer=ch, msg_id=p_id, options=[bytes([int(opt)])]))
                    success += 1
                except: pass
            await status.edit(f"✅ Голосов поставлено: {success}")

        # Комментарии
        elif state['action'] == 'comm':
            lines = text.split('\n')
            link, msgs = lines[0], lines[1:]
            ch, p_id = parse_link(link)
            for i, m in enumerate(msgs[:len(clients)]):
                try:
                    await clients[i](functions.channels.JoinChannelRequest(ch)) # Вступаем в чат
                    await clients[i].send_message(ch, m, reply_to=p_id)
                    success += 1
                    await asyncio.sleep(1)
                except: pass
            await status.edit(f"✅ Комментариев: {success}")

    except Exception as e:
        await event.respond(f"⚠️ Ошибка: {e}")
    
    user_states[uid] = None

async def main():
    await load_accounts()
    asyncio.create_task(run_web_server()) 
    await bot.start(bot_token=BOT_TOKEN)
    print("🚀 FLASHBOOST СИСТЕМА ЗАПУЩЕНА")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())