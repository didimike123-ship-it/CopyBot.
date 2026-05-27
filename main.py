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

    # စာသားထဲမှ ဂဏန်းများကိုသာ သန့်စင်ပြီး သီးသန့်စုထုတ်ခြင်း
    all_digits = "".join(re.findall(r'\d+', original_text))
    
    # မြန်မာ့ဖုန်းနံပါတ် ပုံစံများကို တိကျစွာ အရင်ဆုံး ရှာဖွေခြင်း
    phone_match = re.search(r'(959\d{7,9}|09\d{7,9}|9\d{7,9})', all_digits)

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

        # မြန်မာ့ဖုန်းကိုယ်ထည်သည် ဂဏန်း ၇ လုံးမှ ၉ လုံးကြားသာ ရှိရမည်ဖြစ်၍ စစ်ဆေးခြင်း
        if not (7 <= len(base_num) <= 9):
            return None

        # --- [အသစ်ပြင်ဆင်ချက်] ကျန်ရှိသော စာသား (Remaining Text) ကို ရှာဖွေပုံစံသစ် ---
        # မူရင်းစာသားထဲက ဖုန်းနံပါတ်ဖြစ်စေနိုင်တဲ့ ဂဏန်းတွဲကို ဖယ်ထုတ်ပြီး ကျန်တဲ့ စာသား/ဂဏန်းများကို ယူခြင်း
        text_parts = original_text.replace(raw_num, '', 1)
        # အကယ်၍ ရှေ့တွင် 959 သို့မဟုတ် +959 ကျန်ခဲ့ပါကလည်း ထပ်မံ ဖယ်ထုတ်ရန်
        text_parts = re.sub(r'\+?959|09', '', text_parts, count=1)
        
        # Symbol များနှင့် Emoji များကို အကုန်ဖြုတ်ချခြင်း
        clean_text = re.sub(r'[^a-zA-Z0-9\u1000-\u109f\s]', '', text_parts)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        final_copy_text = ""
        standard_num = "09" + base_num

        # --- Operator အလိုက် စည်းမျဉ်းများ တိကျစွာ ခွဲခြားခြင်း ---
        
        # ၁။ MYTEL (နံပါတ်သက်သက် ၀၉ ကနေစပြီး)
        if standard_num.startswith(('096', '0975', '0976', '0977', '0978', '0979')):
            final_copy_text = standard_num
            
        # ၂။ ATOM (နံပါတ်သက်သက် ၉ ကနေစပြီး)
        elif standard_num.startswith(('0974', '0973', '0972', '091', '0925')):
            final_copy_text = standard_num[1:]
            
        # 🔵 ၃။ MPT (ဖုန်းနံပါတ်အရှေ့ 09 ဖြုတ် + ကျန်တာအနောက်)
        elif standard_num.startswith(('092', '094', '095', '0971', '098')):
            formatted_num = base_num  # 09 ဖြုတ်ထားသော ကိုယ်ထည်
            final_copy_text = f"{formatted_num} {clean_text}" if clean_text else formatted_num
            
        # 🟢 ၄။ OOREDOO (ဖုန်းနံပါတ်အရှေ့ 09 တပ် + ကျန်တာအနောက်)
        elif standard_num.startswith('099'):
            formatted_num = standard_num  # 09 အပြည့်တပ်ထားသောနံပါတ်
            final_copy_text = f"{formatted_num} {clean_text}" if clean_text else formatted_num
            
        else:
            final_copy_text = standard_num

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
        await update.message.reply_text(text=reply_text, parse_mode="Markdown", disable_web_page_preview=True)

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
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        except Exception as e:
            print(f"Error handling edited message: {e}")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler((filters.UpdateType.EDITED_MESSAGE) & (filters.TEXT | filters.PHOTO), handle_edited_message))

    server_thread = Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()

    print("Bot is polling with MPT/Ooredoo fix...")
    application.run_polling()

if __name__ == '__main__':
    main()
