from fastapi import FastAPI, Request
import os
import json
import asyncio
import datetime
import requests
from telebot.async_telebot import AsyncTeleBot
import firebase_admin
from firebase_admin import credentials, firestore, storage
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# Initialize FastAPI app
app = FastAPI()

# Initialize the bot
BOT_TOKEN = os.getenv("8113117364:AAEBZZZQrX2RfmvrKcNfntkvIsgnt-OrTw")
bot = AsyncTeleBot(BOT_TOKEN)

# Firebase setup
firebase_config = json.loads(os.getenv("FIREBASE_CONFIG"))
cred = credentials.Certificate(firebase_config)
firebase_admin.initialize_app(cred, {'storageBucket': 'orblix-15f00.appspot.com'})
db = firestore.client()
bucket = storage.bucket()

# Generate keyboard
def generate_start_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Open Orblix App", web_app=WebAppInfo(url="https://orblix.netlify.app/")))
    return keyboard

# Bot commands
@bot.message_handler(commands=['start'])
async def start(message):
    try:
        user_id = str(message.from_user.id)
        user_first_name = str(message.from_user.first_name)
        user_last_name = message.from_user.last_name
        user_username = message.from_user.username
        user_language_code = str(message.from_user.language_code)
        is_premium = message.from_user.is_premium
        text = message.text.split()

        welcome_message = (
            f"Hi, {user_first_name}!👋\n\n"
            f"Welcome to Orblix!\n\n"
            f"Here you can earn tokens by mining them!\n\n"
            f"Airdrop date coming soon!\n\n"
            f"Invite friends to earn more tokens, and level up fast!\n\n"
        )

        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            # Download and upload user profile photo to Firebase Storage
            photos = await bot.get_user_profile_photos(user_id, limit=1)
            user_image = None
            if photos.total_count > 0:
                file_id = photos.photos[0][-1].file_id
                file_info = await bot.get_file(file_id)
                file_path = file_info.file_path
                file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

                response = requests.get(file_url)
                if response.status_code == 200:
                    blob = bucket.blob(f"user_images/{user_id}.jpg")
                    blob.upload_from_string(response.content, content_type='image/jpeg')
                    user_image = blob.generate_signed_url(datetime.timedelta(days=365), method='GET')

            user_data = {
                'userImage': user_image,
                'firstName': user_first_name,
                'lastName': user_last_name,
                'username': user_username,
                'languageCode': user_language_code,
                'isPremium': is_premium,
                'referrals': {},
                'balance': 0,
                'mineRate': 0.001,
                'isMining': False,
                'miningStartedTime': None,
                'daily': {'claimedTime': None, 'claimedDay': 0},
                'links': None,
            }

            # Handle referral logic
            if len(text) > 1 and text[1].startswith('ref_'):
                referrer_id = text[1][4:]
                referrer_ref = db.collection('users').document(referrer_id)
                referrer_doc = referrer_ref.get()
                if referrer_doc.exists:
                    user_data['referredBy'] = referrer_id
                    referrer_data = referrer_doc.to_dict()

                    bonus_amount = 500 if is_premium else 300
                    current_balance = referrer_data.get('balance', 0)
                    new_balance = current_balance + bonus_amount

                    referrals = referrer_data.get('referrals', {})
                    referrals[user_id] = {
                        'addedValue': bonus_amount,
                        'firstName': user_first_name,
                        'lastName': user_last_name,
                        'userImage': user_image,
                    }

                    referrer_ref.update({
                        'balance': new_balance,
                        'referrals': referrals
                    })
            else:
                user_data['referredBy'] = None

            user_ref.set(user_data)

        keyboard = generate_start_keyboard()
        await bot.reply_to(message, welcome_message, reply_markup=keyboard)

    except Exception as e:
        error_message = "Error. Please try again!"
        await bot.reply_to(message, error_message)
        print(f"Error: {str(e)}")

# FastAPI endpoint for Telegram webhook
@app.post("/webhook")
async def process_webhook(request: Request):
    update_dict = await request.json()
    update = types.Update.de_json(update_dict)
    await bot.process_new_updates([update])
    return {"status": "ok"}

# FastAPI health check endpoint
@app.get("/")
async def health_check():
    return {"status": "Bot is running"}
