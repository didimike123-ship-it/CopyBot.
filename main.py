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

    clean_text = original_text.replace(raw_matched_chunk, ' ', 1).strip()
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
    if not update.message or not (update.message.text or update.message.caption):
        return
    incoming_text = update.message.text or update.message.caption
    reply_text, op_name, plan_name = process_phone_logic(incoming_text)
    if reply_text:
        chat_id = update.message.chat_id
        current_date = datetime.now().strftime("%Y-%m-%d")
        if chat_id not in group_sales_reports:
            group_sales_reports[chat_id] = {"date": current_date, "data": {}}
        report = group_sales_reports[chat_id]
        if report["date"] != current_date:
            report["date"], report["data"] = current_date, {}
        if op_name not in report["data"]:
            report["data"][op_name] = {}
        report["data"][op_name][plan_name] = report["data"][op_name].get(plan_name, 0) + 1
        sent_msg = await update.message.reply_text(text=reply_text, parse_mode="Markdown", disable_web_page_preview=True)
        if "msg_map" not in context.user_data: context.user_data["msg_map"] = {}
        context.user_data["msg_map"][update.message.message_id] = sent_msg.message_id

async def get_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    report = group_sales_reports.get(chat_id)
    if not report or not report["data"]:
        await update.message.reply_text(text="📊 ယနေ့အတွက် စာရင်းမရှိသေးပါ။")
        return
    report_msg = f"📊 *Sales Report* ({report['date']})\n\n"
    total_all = 0
    for op in ["ATOM", "MYTEL", "OOREDOO", "MPT"]:
        if op in report["data"]:
            plans = report["data"][op]
            report_msg += f"🔹 *{op}*\n"
            op_total = 0
            for plan, count in plans.items():
                report_msg += f"  ▫️ {plan} : {count}\n"
                op_total += count
            report_msg += f"  🔻 Total: {op_total}\n\n"
            total_all += op_total
    report_msg += f"📈 *Grand Total: {total_all}*"
    await update.message.reply_text(text=report_msg, parse_mode="Markdown")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("report", get_report))
    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_message))
    Thread(target=run_web_server, daemon=True).start()
    application.run_polling()

if __name__ == '__main__':
    main()
