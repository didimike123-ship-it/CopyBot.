import os
import re
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8984373560:AAEApSz6JqW5toSTC8fHfQhbP13_7cJNlvY"

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running Live!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def process_phone_logic(original_text):
    if not original_text:
        return None

    clean_original = re.sub(r'[^a-zA-Z0-9\u1000-\u109f\s]', ' ', original_text)
    clean_original = re.sub(r'\s+', ' ', clean_original).strip()

    all_digits = "".join(re.findall(r'\d+', clean_original))
    phone_match = re.search(r'(959\d{7,9}|09\d{7,9}|9\d{7,9})', all_digits)

    if phone_match:
        raw_num = phone_match.group(1)
        
        if raw_num.startswith('959'):
            base_num = raw_num[3:]
        elif raw_num.startswith('09'):
            base_num = raw_num[2:]
        elif raw_num.startswith('9') and not raw_num.startswith('09'):
            base_num = raw_num[1:]
        else:
            base_num = raw_num

        if not (7 <= len(base_num) <= 9):
            return None

        spaced_digits_pattern = r'\s*'.join(list(raw_num))
        text_parts = re.sub(spaced_digits_pattern, '', clean_original, count=1)
        text_parts = re.sub(r'\+?959|09', '', text_parts, count=1)
        
        clean_text = re.sub(r'[^a-zA-Z0-9\u1000-\u109f\s]', '', text_parts)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        final_copy_text = ""
        standard_num = "09" + base_num

        if standard_num.startswith(('096', '0975', '0976', '0977', '0978', '0979')):
            final_copy_text = standard_num
            
        elif standard_num.startswith(('0974', '0973', '0972', '091', '0925')):
            final_copy_text = standard_num[1:]
            
        elif standard_num.startswith(('092', '094', '095', '0971', '098')):
            formatted_num = base_num
            final_copy_text = f"{formatted_num} {clean_text}" if clean_text else formatted_num
            
        elif standard_num.startswith('099'):
            formatted_num = standard_num
            final_copy_text = f"{formatted_num} {clean_text}" if clean_text else formatted_num
            
        else:
            final_copy_text = standard_num

        return f"`{final_copy_text}`"
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    incoming_text = update.message.text if update.message.text else update.message.caption
    if not incoming_text:
        return

    reply_text = process_phone_logic(incoming_text)
    if reply_text:
        sent_msg = await update.message.reply_text(
            text=reply_text, 
            parse_mode="Markdown", 
            disable_web_page_preview=True
        )
        if "msg_map" not in context.user_data:
            context.user_data["msg_map"] = {}
        context.user_data["msg_map"][update.message.message_id] = sent_msg.message_id

async def handle_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.edited_message:
        return

    user_msg_id = update.edited_message.message_id
    edited_text = update.edited_message.text if update.edited_message.text else update.edited_message.caption
    if not edited_text:
        return

    new_reply_text = process_phone_logic(edited_text)
    if not new_reply_text:
        return

    msg_map = context.user_data.get("msg_map", {})
    bot_msg_id = msg_map.get(user_msg_id)

    if bot_msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=update.edited_message.chat_id,
                message_id=bot_msg_id,
                text=new_reply_text,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        except Exception:
            await update.edited_message.reply_text(
                text=new_reply_text, 
                parse_mode="Markdown", 
                disable_web_page_preview=True
            )
    else:
        sent_msg = await update.edited_message.reply_text(
            text=new_reply_text, 
            parse_mode="Markdown", 
            disable_web_page_preview=True
        )
        if "msg_map" not in context.user_data:
            context.user_data["msg_map"] = {}
        context.user_data["msg_map"][user_msg_id] = sent_msg.message_id

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler((filters.UpdateType.EDITED_MESSAGE) & (filters.TEXT | filters.PHOTO), handle_edited_message))

    server_thread = Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()

    print("Bot is polling successfully...")
    application.run_polling()

if __name__ == '__main__':
    main()
