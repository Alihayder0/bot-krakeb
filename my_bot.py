# -*- coding: utf-8 -*-
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes




# --- الإعدادات الرئيسية ---
# --- الإعدادات الرئيسية ---

load_dotenv()  # تحميل متغيرات البيئة من ملف .env


TOKEN = os.getenv("TOKEN")
ADMIN_USER_ID = int(os.getenv("ADMIN_ID"))
if not TOKEN or not ADMIN_USER_ID:
    raise ValueError("يجب تعريف متغيرات TOKEN و ADMIN_ID في ملف .env")

ADMIN_USER_ID = int(ADMIN_USER_ID)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "time_data.json")

# نقرأ الـ ID كنص ثم نحوله إلى رقم صحيح (integer)

USER_NAMES = ["علي", "فهد", "حميد", "حيدر", "رامي"]
WORK_TYPES = ["طباعة", "عمل يدوي"]

# **تعديل جديد: تعريف أسعار مختلفة لكل عمل**
RATES_PER_HOUR = {
    "طباعة": 2000,    # 2000 دينار لكل ساعة طباعة
    "عمل يدوي": 2000  # 2500 دينار لكل ساعة عمل يدوي (كمثال)
}

# --- متغيرات لحفظ الحالة الحالية ---
active_timers = {}

# --- دوال التعامل مع البيانات (تم تعديلها لتناسب الهيكل الجديد) ---
def load_data():
    """تحميل البيانات مع مزامنتها مع الهيكل الجديد للبيانات."""
    # الهيكل الافتراضي الجديد: لكل مستخدم قاموس بأنواع الأعمال
    default_structure = {user: {work_type: 0 for work_type in WORK_TYPES} for user in USER_NAMES}
    
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            # دمج البيانات لضمان توافق الهيكل
            for user, work_times in default_structure.items():
                if user in saved_data and isinstance(saved_data[user], dict):
                    work_times.update(saved_data[user])
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    save_data(default_structure)
    return default_structure

def save_data(data):
    """حفظ البيانات في ملف JSON."""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- دالة مساعدة لتقريب المبلغ ---
def round_to_nearest_250(amount):
    """تقريب المبلغ لأقرب 250 دينار."""
    return round(amount / 250) * 250

# --- معالج الأمر الرئيسي ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال القائمة الرئيسية."""
    keyboard = [
        [InlineKeyboardButton("⏱️ بدء وقت العمل", callback_data="timer_start_select_user")],
        [InlineKeyboardButton("🛑 إيقاف وقت العمل", callback_data="timer_stop_select_user")],
        [InlineKeyboardButton("📊 عرض إجمالي الأوقات", callback_data="view_totals")],
        [InlineKeyboardButton("💰 حساب المال", callback_data="calculate_money_select_user")],
        [InlineKeyboardButton("⚙️ قائمة المدير", callback_data="admin_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text("القائمة الرئيسية:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("أهلاً بك في بوت تسجيل أوقات العمل. اختر أحد الخيارات:", reply_markup=reply_markup)


# --- معالج الضغط على الأزرار ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception as e:
        # نتجاهل الخطأ إذا كان بسبب انتهاء وقت الرد على الـ callback query
        if "Query is too old" in str(e) or "query id is invalid" in str(e):
            pass
        else:
            raise

    data = query.data
    parts = data.split(':')
    action = parts[0]

    # ... باقي الكود كما هو بدون تعديل
    if action == "select_work":
        user_name, work_type = parts[1], parts[2]
        if user_name in active_timers:
            # ... الكود كما هو
            return
        active_timers[user_name] = {'start_time': datetime.now(), 'work_type': work_type}
        keyboard = [[InlineKeyboardButton("إنهاء الوقت ⏹️", callback_data="timer_stop_select_user")]]
        await query.edit_message_text(f"✅ تم بدء عداد الوقت لـ '{user_name}' في مهمة '{work_type}' الساعة {datetime.now().strftime('%H:%M:%S')}.", reply_markup=InlineKeyboardMarkup(keyboard))
    # **تعديل جوهري: منطق إيقاف العداد ليحفظ البيانات حسب النوع**
    elif action == "stop_timer_for":
        user_name = parts[1]
        if user_name not in active_timers:
            return

        start_info = active_timers.pop(user_name)
        work_type = start_info['work_type']
        end_time = datetime.now()
        start_time = start_info['start_time']
        duration_in_minutes = round((end_time - start_time).total_seconds() / 60)
        
        times = load_data()
        # إضافة الدقائق إلى نوع العمل الصحيح
        times[user_name][work_type] = times[user_name].get(work_type, 0) + duration_in_minutes
        save_data(times)
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]]
        await query.edit_message_text(
            f"✅ تم إيقاف عداد '{work_type}' لـ '{user_name}'.\n"
            f"مدة العمل: {duration_in_minutes} دقيقة.\n"
            f"إجمالي دقائق '{work_type}' الآن: {times[user_name][work_type]} دقيقة.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # **تعديل جوهري: منطق إيقاف جميع العدادات**
    elif action == "stop_timer_all":
        if not active_timers:
            await query.edit_message_text("لا توجد أي عدادات وقت نشطة لإيقافها.")
            return
        times = load_data()
        report_message = "✅ تم إيقاف جميع العدادات النشطة:\n\n"
        for user_name in list(active_timers.keys()):
            start_info = active_timers.pop(user_name)
            work_type = start_info['work_type']
            end_time = datetime.now()
            start_time = start_info['start_time']
            duration_in_minutes = round((end_time - start_time).total_seconds() / 60)
            
            times[user_name][work_type] = times[user_name].get(work_type, 0) + duration_in_minutes
            report_message += f"👤 {user_name} ({work_type}): +{duration_in_minutes} دقيقة\n"
        
        save_data(times)
        keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]]
        await query.edit_message_text(report_message, reply_markup=InlineKeyboardMarkup(keyboard))

    # **تعديل جوهري: عرض الإجماليات بشكل مفصل**
    elif action == "view_totals":
        times = load_data()
        message = "📊 إجمالي الدقائق المسجلة لكل شخص:\n\n"
        for name, work_times in times.items():
            message += f"👤 **{name}**:\n"
            total_minutes = 0
            for work_type, minutes in work_times.items():
                message += f"  - {work_type}: {minutes} دقيقة\n"
                total_minutes += minutes
            total_hours = total_minutes // 60
            remaining_minutes = total_minutes % 60
            message += f"  - **المجموع**: {total_minutes} دقيقة ({total_hours} س و {remaining_minutes} د)\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]]
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    # **تعديل جوهري: حساب المال بشكل مفصل**
    elif action == "calculate_for":
        user_name = parts[1]
        times = load_data()
        user_times = times.get(user_name, {})
        
        message = f"💰 حساب المستحقات لـ **{user_name}**:\n\n"
        total_earnings_raw = 0

        for work_type, minutes in user_times.items():
            rate = RATES_PER_HOUR.get(work_type, 0)
            hours = minutes / 60
            earnings = hours * rate
            total_earnings_raw += earnings
            
            message += (
                f"*{work_type}*:\n"
                f"  - الوقت: {minutes} دقيقة ({hours:.2f} ساعة)\n"
                f"  - المستحق: **{round_to_nearest_250(earnings):,.0f}** دينار\n"
            )
        
        message += (
            f"\n-----------------------------------\n"
            f"💰 **إجمالي المستحقات**: **{round_to_nearest_250(total_earnings_raw):,.0f}** دينار عراقي"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]]
        await query.edit_message_text(text=message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # ... (باقي الأجزاء مثل قائمة المدير وتصفير العدادات تحتاج أيضاً لتعديل طفيف)
    
    elif action == "reset_user_confirm":
        user_name = parts[1]
        times = load_data()
        # تصفير جميع أنواع العمل للمستخدم المحدد
        times[user_name] = {work_type: 0 for work_type in WORK_TYPES}
        save_data(times)
        keyboard = [[InlineKeyboardButton("🔙 رجوع لقائمة المدير", callback_data="admin_menu")]]
        await query.edit_message_text(f"✅ تم تصفير إجمالي وقت العمل للمستخدم '{user_name}'.", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif action == "reset_all_execute":
        if query.from_user.id == ADMIN_USER_ID:
            # تصفير بيانات الجميع
            times = {user: {work_type: 0 for work_type in WORK_TYPES} for user in USER_NAMES}
            save_data(times)
            keyboard = [[InlineKeyboardButton("🔙 رجوع لقائمة المدير", callback_data="admin_menu")]]
            await query.edit_message_text("✅ تم تصفير عدادات جميع المستخدمين بنجاح.", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.answer("عذراً، هذا الخيار متاح للمدير فقط.", show_alert=True)
            
    # --- باقي منطق الأزرار (مثل قائمة المدير واختيار المستخدم) يبقى كما هو ---
    elif action == "calculate_money_select_user":
        keyboard = [[InlineKeyboardButton(name, callback_data=f"calculate_for:{name}")] for name in USER_NAMES]
        keyboard.append([InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")])
        await query.edit_message_text("اختر الشخص لحساب مستحقاته المالية:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif action == "admin_menu":
        if query.from_user.id == ADMIN_USER_ID:
            keyboard = [
                [InlineKeyboardButton("♻️ تصفير عداد الجميع", callback_data="reset_all_confirm")],
                *[[InlineKeyboardButton(f"❌ صفّر عداد {name}", callback_data=f"reset_user_confirm:{name}")] for name in USER_NAMES],
                [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]
            ]
            await query.edit_message_text("قائمة المدير (يرجى الحذر):", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.answer("عذراً، هذا الخيار متاح للمدير فقط.", show_alert=True)
    elif action == "reset_all_confirm":
        if query.from_user.id == ADMIN_USER_ID:
            keyboard = [
                [InlineKeyboardButton("✅ نعم، قم بالتصفير", callback_data="reset_all_execute")],
                [InlineKeyboardButton("❌ لا، الغاء", callback_data="admin_menu")]
            ]
            await query.edit_message_text(
                "⚠️ هل أنت متأكد أنك تريد تصفير عداد الجميع؟\nهذا الإجراء لا يمكن التراجع عنه.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.answer("عذراً، هذا الخيار متاح للمدير فقط.", show_alert=True)
    elif action == "main_menu":
        await start_command(update, context)

    # --- هذا الجزء يغطي الأزرار التي لم يتم تعديلها ---
    elif action == "timer_start_select_user":
        keyboard = [[InlineKeyboardButton(name, callback_data=f"select_user:{name}")] for name in USER_NAMES]
        keyboard.append([InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")])
        await query.edit_message_text("من أنت؟ اختر اسمك من القائمة:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif action == "select_user":
        user_name = parts[1]
        keyboard = [[InlineKeyboardButton(work, callback_data=f"select_work:{user_name}:{work}")] for work in WORK_TYPES]
        keyboard.append([InlineKeyboardButton("🔙 رجوع لاختيار الاسم", callback_data="timer_start_select_user")])
        await query.edit_message_text(f"أهلاً {user_name}. ما هو نوع العمل؟", reply_markup=InlineKeyboardMarkup(keyboard))
    elif action == "timer_stop_select_user":
        active_users = list(active_timers.keys())
        if not active_users:
            keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]]
            await query.edit_message_text("لا توجد أي عدادات وقت نشطة حالياً.", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        keyboard = [[InlineKeyboardButton(name, callback_data=f"stop_timer_for:{name}")] for name in active_users]
        keyboard.append([InlineKeyboardButton("⏹️ إنهاء للجميع", callback_data="stop_timer_all")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")])
        await query.edit_message_text("اختر المستخدم الذي تريد إيقاف عداده:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- دالة رئيسية لتشغيل البوت ---
def main():
    print("Bot is starting...")
    load_data()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Polling...")
    app.run_polling()

if __name__ == '__main__':
    main()