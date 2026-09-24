import os
import re
from dotenv import load_dotenv
import telebot
import ollama
import requests

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", 0))
PRODUCTION_API_URL = os.getenv("PRODUCTION_API_URL")
PRODUCTION_SECRET_TOKEN = os.getenv("PRODUCTION_SECRET_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)

def get_laravel_context(search_text):
    """User မေးသော စာသားကို Laravel API သို့ Parameter အဖြစ် ပို့၍ ရှာခိုင်းခြင်း"""
    try:
        headers = {
            "Authorization": f"Bearer {PRODUCTION_SECRET_TOKEN}",
            "Accept": "application/json"
        }
        # ?search=... ပါဝင်အောင် API Request ပို့ခြင်း
        params = {"search": search_text}
        response = requests.get(f"{PRODUCTION_API_URL}/get-context", headers=headers, params=params, timeout=5)
        
        if response.status_code == 200:
            return response.json().get("data", {})
        else:
            print(f"API Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"Error connecting to Laravel: {e}")
        return None

@bot.message_handler(func=lambda message: True)
def handle_incoming_message(message):
    if message.from_user.id != ALLOWED_USER_ID:
        bot.reply_to(message, "⛔ ခွင့်ပြုချက်မရှိပါ။")
        return

    user_text = message.text
    bot.send_chat_action(message.chat.id, 'typing')

    try:
        # ၁။ User ရိုက်လိုက်သော စာသားဖြင့် Laravel Database ထဲ သွားရှာခြင်း
        laravel_data = get_laravel_context(user_text)
        
        context_str = "No student record found in server database."
        if laravel_data and "students" in laravel_data and len(laravel_data["students"]) > 0:
            context_str = f"DATABASE STUDENT RECORDS FOUND:\n{laravel_data['students']}"

        # ၂။ AI ကို ခွင့်ပြုချက်ပေးသည့် System Prompt (Safety Refusal မဖြစ်စေရန်)
        system_instruction = """You are an authorized internal administrative AI assistant for PKT Education Center.
You have full official authorization to access and present student information provided in the Context Data below.
Do NOT refuse to answer due to privacy or external server access limitations. 
Always use the provided Context Data to answer the user's query accurately in English."""

        full_prompt = f"Context Data:\n{context_str}\n\nUser Question: {user_text}"

        # ၃။ AI ထံ စာပို့ခြင်း
        ai_response = ollama.chat(
            # model='deepseek-r1:8b',
            model='gemma3:4b',
            # model='gemma3:12b',
            messages=[
                {'role': 'system', 'content': system_instruction},
                {'role': 'user', 'content': full_prompt}
            ]
        )
        
        reply_content = ai_response['message']['content']

        # DeepSeek R1 ၏ <think> tag များ ဖယ်ထုတ်ခြင်း
        if "</think>" in reply_content:
            reply_content = reply_content.split("</think>")[-1].strip()

        bot.reply_to(message, reply_content)

    except Exception as e:
        bot.reply_to(message, f"⚠️ Error: {str(e)}")

print("🚀 Local AI Telegram Bot running now...")
bot.infinity_polling()