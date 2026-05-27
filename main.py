import os
import re
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8984373560:AAEApSz6JqW5toSTC8fHfQhbP13_7cJNlvY"

# --- ၁။ Render အတွက် Web Server တည်ဆောက်ခြင်း ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running Live!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --- ၂။ ဖုန်းနံပါတ်နှင့် စာသားများကို သန့်စင်ပေးသည့် Logic Function ---
def process_phone_logic(original_text):
    if not original_text:
        return None

    # စာသားထဲမှ ဂဏန်းများကိုသာ သန့်စင်ပြီး စုထုတ်ခြင်း
    all_digits = "".join(re.findall(r'\d+', original_text))
    
    # ဖုန်းနံပါတ် ပုံစံ ရှာဖွေခြင်း
    phone_match = re.search(r'(959\d{7,11}|09\d{7,11}|9\d{7,11})', all_digits)

    if phone_match:
        raw_num = phone_match.group(1)
        
        # ရှေ့က 959 သို့မဟုတ် 09 များကို ဖယ်ရှားပြီး သန့်စင်သော "ကိုယ်ထည်နံပါတ်" ကို ယူခြင်း
        if raw_num.startswith('959'):
            base_num = raw_num[3:]
        elif raw_num.startswith('09'):
            base_num = raw_num[2:]
        elif raw_num.startswith('9') and not raw_num.startswith('09'):
            base_num = raw_num[1:]
        else:
            base_num = raw_num

        prefix = base_num[0] if len(base_num) > 0 else ""
        final_copy_text = ""

        # ဖုန်းနံပါတ် မဟုတ်သော ကျန်ရှိသည့် စာသားများကို ဖယ်ထုတ်ခြင်း
        clean_pattern = r'\+?959\s?\d+[-.\s]?\d+[-.\s]?\d+|09\s?\d+[-.\s]?\d+[-.\s]?\d+|\b\d{9,11}\b'
        remaining_text = re.sub(clean_pattern, '', original_text).strip()
        
        # --- [အသစ်ထည့်သွင်းချက်] Symbol များနှင့် Emoji များကို ဖြုတ်ချခြင်း ---
        # အင်္ဂလိပ်စာလုံး၊ ဗမာစာလုံး၊ ဂဏန်းများနှင့် space မဟုတ်သော ကျန်တဲ့ Symbol တွေအကုန်လုံးကို ဖျက်ပစ်ပါမည်
        # Myanmar Unicode Range: \u1000-\u109f
        remaining_text = re.sub(r'[^a-zA-Z0-9\u1000-\u109f\s]', '', remaining_text)
        
        # ဇယားကွက် သို့မဟုတ် စာကြောင်းအသစ် (Line Break) များကို Space တစ်ခုတည်းအဖြစ် ပြောင်းလဲခြင်း
        remaining_text = re.sub(r'\s+', ' ', remaining_text).strip()

        # --- လူကြီးမင်း၏ Operator အလိုက် စည်းမျဉ်းများ သတ်မှတ်ခြင်း ---
        
        if prefix in ['2', '4', '8']:  # MPT
            formatted_num = base_num
            final_copy_text = f"{formatted_num} {remaining_text}" if remaining_text else formatted_num
            
        elif prefix == '9':  # Ooredoo
            formatted_num = "09" + base_num
            final_copy_text = f"{formatted_num} {remaining_text}" if remaining_text else formatted_num
            
        elif prefix == '7':  # ATOM
            final_copy_text = "9" + base_num
            
        elif prefix == '6':  # Mytel
            final_copy_text = "09" + base_num
            
        else:
            final_copy_text = original_text

        return f"`{final_copy_text}`"
    return None

# --- ၃။ Message (Text သို့မဟုတ် Photo) ဝင်လာလျှင် တုံ့ပြန်မည့် Logic ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    incoming_text = update.message.text if update.message.text else update.message.caption
    
    if not incoming_text:
        return

    reply_text = process_phone_logic(incoming_text)
    
    if reply_text:
        await update.message.reply_text(text=reply_text, parse_mode="Markdown")

# --- ၄။ User က Message ကို Edit လုပ်လိုက်လျှင် လိုက်ပြင်မည့် Logic ---
async def handle_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.edited_message:
        return

    edited_text = update.edited_message.text if update.edited_message.text else update.edited_message.caption

    if not edited_text:
        return

    new_reply_text = process_phone_logic(edited_text)

    if new_reply_text:
        try:
            await update.edited_message.reply_text(
                text=f"🔄 **Updated Format:**\n{new_reply_text}", 
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Error handling edited message: {e}")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Text Message နှင့် Photo Message နှစ်ခုလုံးကို ဖမ်းရန်
    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_message))
    
    # Edited Message များအတွက်
    application.add_handler(MessageHandler((filters.UpdateType.EDITED_MESSAGE) & (filters.TEXT | filters.PHOTO), handle_edited_message))

    server_thread = Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()

    print("Bot is polling with Symbol Cleaner...")
    application.run_polling()

if __name__ == '__main__':
    main()
