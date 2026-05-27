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

def is_pure_calculation(text):
    text_clean = text.strip().replace(' ', '')
    if any(op in text_clean for op in ['*', '/', '%']) and len(re.findall(r'\d+', text_clean)) > 2:
        return True
    if re.match(r'^[\d+\-*/().%]+$', text_clean):
        return True
    return False

def extract_and_calculate(text):
    clean_expr = re.sub(r'[^0-9+\-*/().%]', '', text)
    if not clean_expr or not any(c.isdigit() for c in clean_expr):
        return None

    try:
        pct_match = re.search(r'(\d+(?:\.\d+)?)([+\-])(\d+(?:\.\d+)?)%', clean_expr)
        if pct_match:
            base = float(pct_match.group(1))
            op = pct_match.group(2)
            pct = float(pct_match.group(3))
            val = base * (pct / 100.0)
            res = base + val if op == '+' else base - val
            return int(res) if res.is_integer() else round(res, 2)

        if '%' in clean_expr:
            clean_expr = clean_expr.replace('%', '/100')

        res = eval(clean_expr, {"__builtins__": None}, {})
        if isinstance(res, (int, float)):
            return int(res) if getattr(res, 'is_integer', lambda: False)() else round(res, 2)
    except:
        pass
    return None

def match_exact_plan(op_name, clean_text):
    if op_name not in OPERATOR_PLANS:
        return "Unknown Plan"
    text_lower = clean_text.lower()
    for plan in OPERATOR_PLANS[op_name]:
        if plan in text_lower:
            return plan.upper()
    return clean_text if clean_text else "General Data"

def process_phone_logic(original_text):
    if not original_text or is_pure_calculation(original_text):
        return None, None, None

    text_upper = original_text.upper()
    
    match_prefix = re.search(r'(\+?95\s*9\s*[246789]|\b0\s*9\s*[246789])', text_upper)
    if not match_prefix:
        return None, None, None
        
    start_idx = match_prefix.start()
    subset = text_upper[start_idx:]
    
    digits_list = []
    chars_seen = 0
    
    for char in subset:
        if char.isdigit():
            digits_list.append(char)
            chars_seen += 1
        elif char.isspace() or char == '+':
            if len(digits_list) > 0:
                pass
        else:
            break
            
    raw_num_extracted = subset[:chars_seen + len(re.findall(r'[\s+]', subset[:chars_seen+4]))]
    phone_digits = "".join(re.findall(r'\d+', raw_num_extracted))
    
    if phone_digits.startswith('959'):
        full_num = "09" + phone_digits[3:]
    elif phone_digits.startswith('09'):
        full_num = phone_digits
    elif phone_digits.startswith('9'):
        full_num = "09" + phone_digits[1:]
    else:
        full_num = "09" + phone_digits

    if len(full_num) < 9:
        return None, None, None

    clean_text = original_text.replace(original_text[start_idx:][:len(raw_num_extracted)], ' ').strip()
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()

    final_copy_text = ""
    op_name = ""

    if full_num.startswith('097'):
        final_copy_text = full_num[1:]
        op_name = "ATOM"
    elif full_num.startswith('096'):
        final_copy_text = full_num
        op_name = "MYTEL"
    elif full_num.startswith(('092', '094', '098')):
        base_part = full_num[2:]
        final_copy_text = f"{base_part} {clean_text}" if clean_text else base_part
        op_name = "MPT"
    elif full_num.startswith('099'):
        base_part = full_num[1:]
        final_copy_text = f"{base_part} {clean_text}" if clean_text else base_part
        op_name = "OOREDOO"
    else:
        final_copy_text = full_num
        op_name = "UNKNOWN"

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

    if is_pure_calculation(incoming_text):
        calc_res = extract_and_calculate(incoming_text)
        if calc_res is not None:
            await update.message.reply_text(text=f"`= {calc_res}`", parse_mode="Markdown")
            return

async def handle_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.edited_message:
        return

    user_msg_id = update.edited_message.message_id
    edited_text = update.edited_message.text if update.edited_message.text else update.edited_message.caption
    if not edited_text:
        return

    if is_pure_calculation(edited_text):
        calc_res = extract_and_calculate(edited_text)
        if calc_res is not None:
            await update.edited_message.reply_text(text=f"`= {calc_res}`", parse_mode="Markdown")
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
            
    if "UNKNOWN" in report["data"]:
        plans = report["data"]["UNKNOWN"]
        report_msg += f"🔹 *UNKNOWN*\n"
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
