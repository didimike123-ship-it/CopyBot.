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

# ရောင်းချမည့် Operator အလိုက် Plan များ စာရင်း
OPERATOR_PLANS = {
    "MYTEL": ["o15k plan", "o20k plan", "n15k plan", "n20k plan", "n25k plan", "n30k plan", "1gb", "1.6gb", "3gb", "5gb", "10gb", "on90", "on180", "on69", "on138", "any13", "any41", "any114"],
    "ATOM": ["15k plan", "25k plan", "870(3d)", "1gb(3d)", "1gb(1m)", "point(p)500", "any 150", "any 100", "on 150"],
    "OOREDOO": ["1gb", "830mb", "15k plan", "20k plan", "25k plan", "30k plan", "any 45", "any 91", "onnet 69"],
    "MPT": ["15k plan", "25k plan", "415mb", "870mb", "1735mb", "any 40", "any 85", "any 50", "on 60", "on 76", "on 130", "on270"]
}

@app.route('/')
def home():
    return "Bot is Running Live Without Channel Ads!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# Order စာသားထဲက Plan ကို ရှာဖွေပေးသည့် Function
def match_exact_plan(op_name, clean_text):
    if op_name not in OPERATOR_PLANS:
        return "Unknown Plan"
    text_lower = clean_text.lower()
    for plan in OPERATOR_PLANS[op_name]:
        if plan in text_lower:
            return plan.upper()
    return clean_text if clean_text else "General Data"

# မူရင်း Logic အတိုင်း ဖုန်းနံပါတ်နှင့် စာသားများကို စီစစ်သည့်အပိုင်း
def process_phone_logic(original_text):
    if not original_text:
        return None, None, None

    # ၁။ စာသားထဲမှာ Space တွေ ဘယ်လိုပဲ ခြားနေပါစေ ဖုန်းနံပါတ် Pattern ကို ရှာဖွေခြင်း
    match = re.search(r'(?:\+?95[\s*]*9|0[\s*]*9)[\d\s*]{6,20}', original_text)
    if not match:
        return None, None, None

    raw_matched_chunk = match.group(0)
    
    # ဂဏန်းသက်သက်ပဲ ထုတ်ယူစုစည်းခြင်း
    phone_digits = "".join(re.findall(r'\d+', raw_matched_chunk))
    
    # +959 ပါလာပါက 09 သို့ ပြောင်းလဲခြင်း
    if phone_digits.startswith('959'):
        phone_digits = "09" + phone_digits[3:]

    # ဖုန်းနံပါတ် အရှည်စစ်ဆေးခြင်း (၁၀ လုံး သို့မဟုတ် ၁၁ လုံး ဖြစ်ရမည်)
    if not (10 <= len(phone_digits) <= 11):
        return None, None, None

    # ဖုန်းနံပါတ်ကို ဖြတ်ထုတ်ပြီး ကျန်တဲ့ Order စာသားတွေကို သန့်စင်ခြင်း (Order ရှေ့/နောက် အကုန်ရစေရန်)
    clean_text = original_text.replace(raw_matched_chunk, ' ').strip()
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()

    final_copy_text = ""
    op_name = ""

    # ၂။ မူရင်း Operator အလိုက် ခွဲခြားသည့် Logic အပိုင်း
    # ATOM Logic - ရှေ့က 0 ဖြုတ်၊ 9 ကနေစယူ၊ နောက်က Order စာသား ဖြတ်ပစ်
    if phone_digits.startswith('097') and len(phone_digits) == 11:
        final_copy_text = phone_digits[1:]
        op_name = "ATOM"
        
    # MYTEL Logic - 09 အပြည့်အတိုင်းယူ၊ နောက်က Order စာသား ဖြတ်ပစ်
    elif phone_digits.startswith('096') and (len(phone_digits) == 10 or len(phone_digits) == 11):
        final_copy_text = phone_digits
        op_name = "MYTEL"
        
    # MPT Logic - ရှေ့က 09 ဖြုတ်၊ 2/4/8 ကနေစယူ၊ နောက်က Order စာသားပါ တွဲယူ
    elif phone_digits.startswith(('092', '094', '098')) and len(phone_digits) == 11:
        base_part = phone_digits[2:]
        final_copy_text = f"{base_part} {clean_text}" if clean_text else base_part
        op_name = "MPT"
        
    # OOREDOO Logic - ရှေ့က 0 ဖြုတ်၊ 99 ကနေစယူ၊ နောက်က Order စာသားပါ တွဲယူ
    elif phone_digits.startswith('099') and len(phone_digits) == 11:
        base_part = phone_digits[1:]
        final_copy_text = f"{base_part} {clean_text}" if clean_text else base_part
        op_name = "OOREDOO"
    else:
        return None, None, None

    matched_plan = match_exact_plan(op_name, clean_text)
    return f"`{final_copy_text.strip()}`", op_name, matched_plan

# မက်ဆေ့ချ်များ ဝင်လာပါက လုပ်ဆောင်ပေးမည့်အဆင့်
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not (update.message.text or update.message.caption):
        return
        
    incoming_text = update.message.text or update.message.caption
    reply_text, op_name, plan_name = process_phone_logic(incoming_text)
    
    # မူရင်း Logic အတိုင်း စာရင်းသွင်းပြီး ကွက်တိပြန်ထုတ်ပေးခြင်း (Channel Join Message လုံးဝမပါပါ)
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
        
        # ယူဇာက အလွယ်တကူ Copy ကူးနိုင်ရန် Code Block ပုံစံဖြင့်သာ ကွက်တိ ပြန်ပို့ပေးမည်
        await update.message.reply_text(text=reply_text, parse_mode="Markdown", disable_web_page_preview=True)

# စာရင်းကြည့်ရန် Command
async def get_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    report = group_sales_reports.get(chat_id)
    if not report or not report["data"]:
        await update.message.reply_text(text="📊 ယနေ့အတွက် ရောင်းချထားသော စာရင်းမရှိသေးပါခင်ဗျာ။")
        return
        
    report_msg = f"📊 *Sales Report* ({report['date']})\n\n"
    total_all = 0
    for op in ["ATOM", "MYTEL", "OOREDOO", "MPT"]:
        if op in report["data"]:
            plans = report["data"][op]
            report_msg += f"🔹 *{op}*\n"
            op_total = 0
            for plan, count in plans.items():
                report_msg += f"  ▫️ {plan} : {count} ကြိမ်\n"
                op_total += count
            report_msg += f"  🔻 Total: {op_total} ကြိမ်\n\n"
            total_all += op_total
            
    report_msg += f"📈 *Grand Total: {total_all} ကြိမ်*"
    await update.message.reply_text(text=report_msg, parse_mode="Markdown")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # စာရင်းကြည့်ရန် Command သက်သက်သာ ထားရှိခြင်း
    application.add_handler(CommandHandler("report", get_report))
    
    # Message ဖတ်သည့်အပိုင်းတွင် မလိုအပ်သော Channel Join ညွှန်ကြားချက်များ လုံးဝမပါဝင်စေဘဲ တိုက်ရိုက်အလုပ်လုပ်စေခြင်း
    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_message))
    
    Thread(target=run_web_server, daemon=True).start()
    print("Bot is running properly without advertisement popups...")
    application.run_polling()

if __name__ == '__main__':
    main()
