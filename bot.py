import os
import asyncio
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InputMediaPhoto, ReplyKeyboardMarkup, KeyboardButton
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
import db as dbmod

# ==========================================
# 📋 DIRECT CONFIGURATION (No .env file required)
# ==========================================
BOT_TOKEN = "8529228017:AAGJlXe8dy7bNveFnEsAt2TkC5pom72-jt0"
CHANNEL_ID = -1004338526659  # Added negative sign and prefix for private channels
ADMIN_ID = 7856418550
MEDIA_GROUP_DELAY = 3.5      # Gives slow connections enough time to group photos perfectly
DB_PATH = "bot.db"
# ==========================================

if not BOT_TOKEN or "AAGJlXe" not in BOT_TOKEN:
    raise RuntimeError('BOT_TOKEN has not been properly initialized.')

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
conn = dbmod.init_db(DB_PATH)

# In-memory buffers for media grouping and task cancellations
media_groups = {}
processing_tasks = {}

# Persistent Custom Keyboard Menu (Matches your screenshot style)
def get_student_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Dashboard Menu"), KeyboardButton(text="💰 Check Balance")],
            [KeyboardButton(text="📤 Withdraw Funds")]
        ],
        resize_keyboard=True,
        persistent=True
    )
    return keyboard

def compute_image_reward(count: int) -> int:
    if count >= 20:
        return 8000
    if count >= 10:
        return 5000
    if count >= 3:
        return 3000
    return 0

def compute_video_reward(duration_seconds: int) -> int:
    if duration_seconds >= 180:
        return 10000
    if duration_seconds >= 120:
        return 5000
    if duration_seconds >= 60:
        return 2000
    return 0

async def process_media_group(media_group_id: str):
    await asyncio.sleep(MEDIA_GROUP_DELAY)
    messages = media_groups.pop(media_group_id, [])
    processing_tasks.pop(media_group_id, None)
    
    if not messages:
        return
    
    photos = []
    for msg in messages:
        if msg.photo:
            photos.append(msg.photo[-1].file_id)
            
    count = len(photos)
    reward = compute_image_reward(count)
    
    if count == 0:
        return

    media = [InputMediaPhoto(media=f) for f in photos]
    try:
        sent = await bot.send_media_group(CHANNEL_ID, media)
        channel_msg_id = sent[0].message_id if sent else None
    except Exception as e:
        print(f"Failed forwarding album to channel: {e}")
        channel_msg_id = None
        
    user = messages[0].from_user
    dbmod.get_or_create_user(conn, user.id, user.username)
    
    if reward > 0:
        dbmod.add_balance(conn, user.id, reward)
        dbmod.log_submission(conn, user.id, 'images', count, reward, channel_msg_id)
        balance = dbmod.get_balance(conn, user.id)
        
        success_msg = (
            f"🎉 Wow! We received your submission. Great job! 👏\n"
            f"💰 Your balance has been updated: {reward:,} ETB\n"
            f"📈 Current Total Balance: {balance:,} ETB\n\n"
            f"📸 Rewards:\n"
            f"• 3 Photos = 3,000 ETB\n"
            f"• 10 Photos = 5,000 ETB\n"
            f"• 20 Photos = 8,000 ETB\n"
            f"• 🎥 1-Min Video = 2,000 ETB\n\n"
            f"📤 Upload more now and increase your earnings!"
        )
        try:
            await bot.send_message(user.id, success_msg, reply_markup=get_student_keyboard())
        except Exception:
            pass
    else:
        dbmod.log_submission(conn, user.id, 'images_unrewarded', count, 0, channel_msg_id)

# Simple tracking dictionary for active withdrawal sequences
awaiting_withdraw = {}

async def cmd_start(message: types.Message):
    dbmod.get_or_create_user(conn, message.from_user.id, message.from_user.username)
    await message.reply(
        'Welcome! Your account has been created. Use the custom menu buttons below or send your assignment images/videos to submit.\n\n'
        'የሚታይ ብርሃኑ አሪፍ የሆነ ፎቶ አስገቡ ፣ ተመሳሳይ ፎቶ አይቀበልም',
        reply_markup=get_student_keyboard()
    )

async def cmd_balance(message: types.Message):
    dbmod.get_or_create_user(conn, message.from_user.id, message.from_user.username)
    bal = dbmod.get_balance(conn, message.from_user.id)
    await message.reply(f'Your balance: {bal:,} ETB', reply_markup=get_student_keyboard())

async def cmd_withdraw(message: types.Message):
    dbmod.get_or_create_user(conn, message.from_user.id, message.from_user.username)
    bal = dbmod.get_balance(conn, message.from_user.id)
    if bal < 50000:
        await message.reply('❌ Withdrawal is only enabled when you reach 50,000 ETB.', reply_markup=get_student_keyboard())
        return
    awaiting_withdraw[message.from_user.id] = True
    await message.reply('Please send your payment details (e.g., account name, number, provider).')

async def cmd_menu(message: types.Message):
    dbmod.get_or_create_user(conn, message.from_user.id, message.from_user.username)
    bal = dbmod.get_balance(conn, message.from_user.id)
    
    target = 50000
    remaining = target - bal
    
    if remaining > 0:
        progress_status = f"📉 Steps Left: You need {remaining:,} ETB more to unlock withdrawals."
        date_status = "🔒 Locked (Unlocks automatically at 50,000 ETB)"
    else:
        progress_status = "🎉 Milestone Reached! You have unlocked withdrawals."
        date_status = "✅ Available Now! Use the withdrawal options to submit your request."

    menu_text = (
        f"👤 Student Dashboard\n"
        f"════════════════════════\n"
        f"💰 Current Balance: {bal:,} ETB\n"
        f"🎯 Target Milestone: 50,000 ETB\n\n"
        f"{progress_status}\n\n"
        f"📅 Withdrawal Availability:\n"
        f"   ┗ {date_status}\n"
        f"════════════════════════\n"
        f"ℹ️ Tip: Keep submitting photo batches (3, 10, 20) or videos to fast-track your progress!"
    )
    await message.reply(menu_text, reply_markup=get_student_keyboard())

async def text_handler(message: types.Message):
    uid = message.from_user.id
    
    # Check if text matches menu button inputs alternative to commands
    if message.text == "👤 Dashboard Menu":
        await cmd_menu(message)
        return
    elif message.text == "💰 Check Balance":
        await cmd_balance(message)
        return
    elif message.text == "📤 Withdraw Funds":
        await cmd_withdraw(message)
        return
        
    if awaiting_withdraw.pop(uid, None):
        details = message.text.strip()
        amount = dbmod.get_balance(conn, uid)
        wid = dbmod.create_withdrawal(conn, uid, amount, details)
        await message.reply('⏳ Your request has been received. Please wait 24 hours for processing.', reply_markup=get_student_keyboard())
        
        try:
            await bot.send_message(ADMIN_ID, f'🔔 New withdrawal request #{wid}\nUser: {message.from_user.full_name} ({uid})\nAmount: {amount} ETB\nDetails: {details}')
        except Exception as e:
            print(f"Failed sending admin notification: {e}")
    else:
        await message.reply("Please use the menu layout or send images/videos directly to update assignments.", reply_markup=get_student_keyboard())

async def media_handler(message: types.Message):
    dbmod.get_or_create_user(conn, message.from_user.id, message.from_user.username)
    
    mgid = getattr(message, 'media_group_id', None)
    if mgid:
        if mgid not in media_groups:
            media_groups[mgid] = []
        
        media_groups[mgid].append(message)
        
        if mgid in processing_tasks:
            processing_tasks[mgid].cancel()
            
        processing_tasks[mgid] = asyncio.create_task(process_media_group(mgid))
        return

    # Handle single standalone photo (Quiet Forwarding - NO AUTO MESSAGE SENT)
    if message.photo:
        file_id = message.photo[-1].file_id
        try:
            await bot.send_photo(CHANNEL_ID, file_id, caption=f'Submission from {message.from_user.full_name}')
        except Exception:
            pass
            
        dbmod.log_submission(conn, message.from_user.id, 'image_single', 1, 0, None)
        return

    # Handle video submissions
    if message.video:
        duration = message.video.duration or 0
        reward = compute_video_reward(duration)
        try:
            sent = await bot.send_video(CHANNEL_ID, message.video.file_id, caption=f'Submission from {message.from_user.full_name}')
            channel_msg_id = sent.message_id
        except Exception:
            channel_msg_id = None
            
        if reward > 0:
            dbmod.add_balance(conn, message.from_user.id, reward)
            dbmod.log_submission(conn, message.from_user.id, 'video', 1, reward, channel_msg_id)
            balance = dbmod.get_balance(conn, message.from_user.id)
            
            video_success = (
                f"🎉 Wow! We received your submission. Great job! 👏\n"
                f"💰 Your balance has been updated: {reward:,} ETB\n"
                f"📈 Current Total Balance: {balance:,} ETB\n\n"
                f"📸 Rewards:\n"
                f"• 3 Photos = 3,000 ETB\n"
                f"• 10 Photos = 5,000 ETB\n"
                f"• 20 Photos = 8,000 ETB\n"
                f"• 🎥 1-Min Video = 2,000 ETB\n\n"
                f"📤 Upload more now and increase your earnings!"
            )
            await message.reply(video_success, reply_markup=get_student_keyboard())
        else:
            dbmod.log_submission(conn, message.from_user.id, 'video', 1, 0, channel_msg_id)

# Registering Handlers securely using aiogram v3 style
dp.message.register(cmd_start, Command(commands=['start']))
dp.message.register(cmd_balance, Command(commands=['balance']))
dp.message.register(cmd_withdraw, Command(commands=['withdraw']))
dp.message.register(cmd_menu, Command(commands=['menu']))

# Content Type filters fixed for aiogram v3 
dp.message.register(text_handler, F.text)
dp.message.register(media_handler, F.photo | F.video)

async def main():
    try:
        print('🚀 Bot core is running smoothly without environment dependencies...')
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())