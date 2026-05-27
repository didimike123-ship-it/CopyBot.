import os
import re
from datetime import datetime
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

BOT_TOKEN = "8984373560:AAEApSz6JqW5toSTC8fHfQhbP13_7cJNlvY"

app = Flask(__name__)

group_sales_reports = {}

OPERATOR_PLANS = {
    "MYTEL": ["o15k plan", "o20k plan", "n15k plan", "n20k plan", "n25k plan", "n30k plan", "1gb", "1.6gb", "3gb", "5gb", "10gb", "on90", "on180", "on69", "on138", "any13", "any41", "any114"],
    "ATOM": ["15k plan", "25k plan", "870(3d)", "1gb(3d)", "1gb(1m)", "point(p)500", "any 150", "any 100", "on 150"],
    "OOREDOO": ["1gb", "830mb", "15k plan", "20k plan", "25k plan", "30k plan", "any 45", "any 91", "onnet 69"],
    "MPT": ["15k plan", "25k plan", "415mb", "870mb", "1735mb", "any 40", "any 85", "any 50", "on 60", "on 76", "on 130", "on270"]
}

@app.route('/')
def home():
    return "Bot is Running Live!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def match_exact_plan(op_name, clean_text):
    if op_name not in OPERATOR_PLANS:
        return "Unknown Plan"
    text_lower = clean_text.lower()
    for plan in OPERATOR_PLANS[op_name]:
        if plan in text_lower:
            return plan.upper()
    return clean_text if clean_text else "General Data"

def process_phone_logic(original_text):
    if not original_text:
        return None, None, None

    match = re.search(r'(?:\+?95[\s*]*9|0[\s*]*9)[\d\s*]{6,20}', original_text)
    if not match:
        return None, None, None

    raw_matched_chunk = match.group(0)
    
    phone_digits = "".join(re.findall(r'\d+', raw_matched_chunk))
    
    if phone_digits.startswith('959'):
        phone_digits = "09" + phone_digits[3:]

    if not (10 <= len(phone_digits) <= 11):
        return None, None, None

    actual_phone_len_in_raw = 0
    digit_count = 0
    clean_digits_for_check = "959" if raw_matched_chunk.strip().replace(" ","").startswith("+959") or raw_matched_chunk.strip().replace(" ","").startswith("959") else "09"
    target_len = 11 if clean_digits_for_check == "959" else (len(phone_digits) + 1 if "959" in raw_matched_chunk else len(phone_digits))
    
    for idx, char in enumerate(raw_matched_chunk):
        if char.isdigit():
            digit_count += 1
        actual_phone_len_in_raw = idx + 1
        if phone_digits.endswith("".join(re.findall(r'\d+', raw_matched_chunk[:idx+1]))[-5:] if len(phone_digits)>=5 else "???") and "".join(re.findall(r'\d+', raw_matched_chunk[:idx+1])) == ( "959"+phone_digits[2:] if clean_digits_for_check=="959" else phone_digits ):
            break

    exact_phone_raw = raw_matched_chunk[:actual_phone_len_in_raw]
    
    clean_text = original_text.replace(exact_phone_raw, ' ', 1).strip()
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()

    final_copy_text = ""
    op_name = ""

    if phone_digits.startswith('097') and len(phone_digits) == 11:
        final_copy_text = phone_digits[1:]
        op_name = "ATOM"
    elif phone_digits.startswith('096') and (len(phone_digits) == 10 or len(phone_digits) == 11):
        final_copy_text = phone_digits
        op_name = "MYTEL"
    elif phone_digits.startswith(('092', '094', '098')) and len(phone_digits) == 11:
        base_part = phone_digits[2:]
        final_copy_text = f"{base_part} {clean_text}" if clean_text else base_part
        op_name = "MPT"
    elif phone_digits.startswith('099') and len(phone_digits) == 11:
        base_part = phone_digits[1:]
        final_copy_text = f"{base_part} {clean_text}" if clean_text else base_part
        op_name = "OOREDOO"
    else:
        return None, None, None

    matched_plan = match_exact_plan(op_name, clean_text)
    return f"`{final_copy_text}`", op_name, matched_plan

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    incoming_text = update.message.text if update.message.text else update.message.caption
    if not incoming_text:
        return

    reply_text, op_name, plan_name = process_phone_logic(incoming_text)
    if reply_text:
        chat_id = update.message.chat_id
        current_date = datetime.now().strftime("%Y-%m-%d")

        if chat_id not in group_sales_reports:
            group_sales_reports[chat_id] = {"date": current_date, "data": {}}

        report = group_sales_reports[chat_id]
        if report["date"] != current_date:
            report["date"] = current_date
            report["data"] = {}

        if op_name not in report["data"]:
            report["data"][op_name] = {}
            
        report["data"][op_name][plan_name] = report["data"][op_name].get(plan_name, 0) + 1

        sent_msg = await update.message.reply_text(text=reply_text, parse_mode="Markdown", disable_web_page_preview=True)
        if "msg_map" not in context.user_data:
            context.user_data["msg_map"] = {}
        context.user_data["msg_map"][update.message.message_id] = sent_msg.message_id
        return

async def handle_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.edited_message:
        return

    user_msg_id = update.edited_message.message_id
    edited_text = update.edited_message.text if update.edited_message.text else update.edited_message.caption
    if not edited_text:
        return

    new_reply_text, _, _ = process_phone_logic(edited_text)
    if new_reply_text:
        msg_map = context.user_data.get("msg_map", {})
        bot_msg_id = msg_map.get(user_msg_id)

        if bot_msg_id:
            try:
                await context.bot.edit_message_text(chat_id=update.edited_message.chat_id, message_id=bot_msg_id, text=new_reply_text, parse_mode="Markdown", disable_web_page_preview=True)
            except Exception:
                await update.edited_message.reply_text(text=new_reply_text, parse_mode="Markdown", disable_web_page_preview=True)
        else:
            sent_msg = await update.edited_message.reply_text(text=new_reply_text, parse_mode="Markdown", disable_web_page_preview=True)
            if "msg_map" not in context.user_data:
                context.user_data["msg_map"] = {}
            context.user_data["msg_map"][user_msg_id] = sent_msg.message_id
        return

async def get_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    report = group_sales_reports.get(chat_id)

    if not report or not report["data"]:
        await update.message.reply_text(text="📊 ယနေ့အတွက် ဤ Group တွင် ရောင်းချထားသော စာရင်းမရှိသေးပါခင်ဗျာ။")
        return

    report_msg = f"📊 *Group Sales Report*\n📅 Date: {report['date']}\n\n"
    total_all = 0
    for op in ["ATOM", "MYTEL", "OOREDOO", "MPT"]:
        if op in report["data"]:
            plans = report["data"][op]
            report_msg += f"🔹 *{op}*\n"
            op_total = 0
            for plan, count in plans.items():
                report_msg += f"  ▫️ {plan} : {count} ကြိမ်\n"
                op_total += count
            report_msg += f"  🔻 Subtotal: {op_total} ကြိမ်\n\n"
            total_all += op_total
            
    report_msg += f"---------------------------\n📈 *Group Total Sales: {total_all} ကြိမ်*"
    await update.message.reply_text(text=report_msg, parse_mode="Markdown")

async def clear_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id in group_sales_reports:
        group_sales_reports[chat_id]["data"] = {}
    await update.message.reply_text(text="✅ ဤ Group အတွက် တစ်နေ့တာ စာရင်းများကို 0 သို့ ပြန်ပြင်ဆင်ပြီးပါပြီ။")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("report", get_report))
    application.add_handler(CommandHandler("clear", clear_report))
    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler((filters.UpdateType.EDITED_MESSAGE) & (filters.TEXT | filters.PHOTO), handle_edited_message))
    server_thread = Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()
    print("Bot is polling successfully...")
    application.run_polling()

if __name__ == '__main__':
    main()
