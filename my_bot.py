import os
import json
import subprocess
import asyncio # <-- تم استيراد المكتبة المطلوبة للقفل
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- الإعدادات الرئيسية ---
load_dotenv()

# تأكد من أن ملف .env موجود في نفس المجلد ويحتوي على TOKEN و ADMIN_ID
TOKEN = os.getenv("TOKEN")
ADMIN_USER_ID = int(os.getenv("ADMIN_ID"))
if not TOKEN or not ADMIN_USER_ID:
    raise ValueError("يجب تعريف متغيرات TOKEN و ADMIN_ID في ملف .env")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")

USER_NAMES = ["علي", "فهد", "حميد", "حيدر", "رامي", "سارة", "زيد", "بسمة", "هاشم"]
WORK_TYPES = ["طباعة", "عمل يدوي"]

RATES_PER_HOUR = {
    "طباعة": 2000,
    "عمل يدوي": 2000
}

# --- متغيرات لحفظ الحالة العامة للتطبيق ---
all_data = {}
active_timers = {}
lock = asyncio.Lock() # <-- تم إنشاء القفل هنا

# --- دوال التعامل مع البيانات ---

def load_app_state():
    """
    تحميل حالة التطبيق الكاملة (بيانات المستخدمين والعدادات النشطة) من ملف data.json.
    """
    global all_data, active_timers
    
    default_structure = {
        "users": {user: {work_type: 0 for work_type in WORK_TYPES} for user in USER_NAMES},
        "active_timers": {}
    }
    
    if not os.path.exists(DATA_FILE):
        all_data = default_structure
        save_app_state()
        return

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
            
        if "users" not in all_data:
            all_data["users"] = {}
        if "active_timers" not in all_data:
            all_data["active_timers"] = {}

        for user in USER_NAMES:
            all_data["users"].setdefault(user, {work_type: 0 for work_type in WORK_TYPES})

        active_timers.clear()
        for user, timer_data in all_data.get("active_timers", {}).items():
            active_timers[user] = {
                'start_time': datetime.fromisoformat(timer_data['start_time']),
                'work_type': timer_data['work_type']
            }
        print(f"✅ تم تحميل الحالة. {len(active_timers)} عداد نشط تم استعادته.")

    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"⚠️ خطأ في تحميل ملف البيانات، سيتم البدء بحالة جديدة. الخطأ: {e}")
        all_data = default_structure
        active_timers = {}
        save_app_state()

def save_app_state():
    """
    حفظ الحالة الكاملة للتطبيق في ملف data.json وعمل commit + push إلى GitHub.
    """
    json_safe_timers = {}
    for user, timer_data in active_timers.items():
        json_safe_timers[user] = {
            'start_time': timer_data['start_time'].isoformat(),
            'work_type': timer_data['work_type']
        }
    
    all_data['active_timers'] = json_safe_timers

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=4)

    try:
        result = subprocess.run(["git", "status", "--porcelain", DATA_FILE], capture_output=True, text=True, check=True)
        if result.stdout.strip():
            print(f"تغييرات مكتشفة في {DATA_FILE}. بدء النسخ الاحتياطي...")
            subprocess.run(["git", "add", DATA_FILE], check=True)
            commit_message = f"Auto backup: {datetime.now().isoformat()}"
            subprocess.run(["git", "commit", "-m", commit_message], check=True)
            subprocess.run(["git", "push", "origin", "main"], check=True)
            print("✅ تم النسخ الاحتياطي بنجاح إلى GitHub.")
        else:
            print("لا توجد تغييرات في البيانات. تم تخطي النسخ الاحتياطي.")
    except subprocess.CalledProcessError as e:
        print(f"❌ فشل أمر Git: {e}")
    except Exception as e:
        print(f"❌ فشل النسخ الاحتياطي التلقائي إلى GitHub: {e}")

def round_to_nearest_250(amount):
    """تقريب المبلغ لأقرب 250"""
    return round(amount / 250) * 250

# --- معالجات الأوامر والأزرار ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """المعالج الخاص بأمر /start والقائمة الرئيسية."""
    keyboard = [
        [InlineKeyboardButton("⏱️ بدء وقت العمل", callback_data="timer_start_select_user")],
        [InlineKeyboardButton("🛑 إيقاف وقت العمل", callback_data="timer_stop_select_user")],
        [InlineKeyboardButton("📊 عرض إجمالي الأوقات", callback_data="view_totals")],
        [InlineKeyboardButton("💰 حساب المال", callback_data="calculate_money_select_user")],
        [InlineKeyboardButton("⚙️ قائمة المدير", callback_data="admin_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = "أهلاً بك. اختر أحد الخيارات:"
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
        except Exception as e:
            print(f"لم يتمكن من تعديل الرسالة: {e}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=message_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """المعالج الرئيسي لجميع ضغطات الأزرار."""
    query = update.callback_query
    # الاستجابة الفورية للزر خارج القفل لتحسين تجربة المستخدم
    await query.answer()

    # استخدام قفل لضمان عدم حدوث تضارب عند تحديث الحالة من عدة مستخدمين بنفس الوقت
    async with lock:
        data = query.data
        user_id = query.from_user.id

        parts = data.split(':')
        action = parts[0]

        # --- جميع العمليات التي تعدل البيانات تتم الآن داخل هذا القفل ---

        if action == "stop_timer_for":
            user_name = parts[1]
            if user_name not in active_timers:
                # لا حاجة لإرسال رسالة هنا لأن query.answer بالأسفل ستقوم بذلك
                pass
            else:
                start_info = active_timers.pop(user_name)
                work_type = start_info['work_type']
                duration = round((datetime.now() - start_info['start_time']).total_seconds() / 60)

                all_data["users"][user_name][work_type] += duration
                save_app_state()

                keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]]
                await query.edit_message_text(
                    f"✅ تم إيقاف عداد '{work_type}' لـ '{user_name}'.\n"
                    f"مدة العمل: {duration} دقيقة.\n"
                    f"إجمالي دقائق '{work_type}' الآن: {all_data['users'][user_name][work_type]} دقيقة.",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            # تم نقل رسالة الخطأ لتظهر في كل الحالات
            if user_name not in active_timers and action == "stop_timer_for":
                 await query.edit_message_text(f"لا يوجد عداد نشط لـ '{user_name}'.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]))


        elif action == "view_totals":
            message = "📊 *إجمالي الدقائق المسجلة لكل شخص:*\n\n"
            for name, work_times in all_data.get("users", {}).items():
                message += f"👤 *{name}*:\n"
                total_minutes = sum(work_times.values())
                if not work_times or total_minutes == 0:
                    message += "  - لا يوجد وقت مسجل.\n"
                else:
                    for work_type, minutes in work_times.items():
                        message += f"  - {work_type}: {minutes} دقيقة\n"
                
                if total_minutes > 0:
                    total_hours = total_minutes // 60
                    rem_minutes = total_minutes % 60
                    message += f"  - *المجموع*: {total_minutes} دقيقة ({total_hours} س و {rem_minutes} د)\n"
                
                if name in active_timers:
                    message += f"  - ⏱️ *(عداد يعمل حالياً)*\n"

                message += "\n"
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]]
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        elif action == "calculate_for":
            user_name = parts[1]
            user_times = all_data.get("users", {}).get(user_name, {})
            message = f"💰 *حساب المستحقات لـ {user_name}:*\n\n"
            total = 0
            for work_type, minutes in user_times.items():
                rate = RATES_PER_HOUR.get(work_type, 0)
                hours = minutes / 60
                earned = hours * rate
                total += earned
                message += (
                    f"*{work_type}*:\n"
                    f"  - الوقت: {minutes} دقيقة ({hours:.2f} ساعة)\n"
                    f"  - المستحق: *{round_to_nearest_250(earned):,.0f}* دينار\n"
                )
            message += (
                f"\n-----------------------------------\n"
                f"💰 *إجمالي المستحقات*: *{round_to_nearest_250(total):,.0f}* دينار عراقي"
            )
            keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]]
            await query.edit_message_text(text=message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        elif action == "reset_user_confirm":
            user_name = parts[1]
            all_data["users"][user_name] = {work: 0 for work in WORK_TYPES}
            
            reset_message = f"✅ تم تصفير إجمالي وقت العمل للمستخدم '{user_name}'."
            if user_name in active_timers:
                active_timers.pop(user_name)
                reset_message += "\n⚠️ تم أيضاً إيقاف العداد النشط الخاص به."

            save_app_state()
            keyboard = [[InlineKeyboardButton("🔙 رجوع لقائمة المدير", callback_data="admin_menu")]]
            await query.edit_message_text(reset_message, reply_markup=InlineKeyboardMarkup(keyboard))

        elif action == "reset_all_execute":
            if user_id == ADMIN_USER_ID:
                all_data["users"] = {name: {w: 0 for w in WORK_TYPES} for name in USER_NAMES}
                active_timers.clear()
                save_app_state()

                keyboard = [[InlineKeyboardButton("🔙 رجوع لقائمة المدير", callback_data="admin_menu")]]
                await query.edit_message_text("✅ تم تصفير عدادات جميع المستخدمين وإيقاف جميع العدادات النشطة بنجاح.", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await context.bot.send_message(chat_id=user_id, text="عذراً، هذا الخيار متاح للمدير فقط.")


        elif action == "select_work":
            user_name, work_type = parts[1], parts[2]
            if user_name in active_timers:
                await query.edit_message_text(f"يوجد عداد وقت نشط بالفعل لـ '{user_name}'.")
            else:
                active_timers[user_name] = {'start_time': datetime.now(), 'work_type': work_type}
                save_app_state()

                keyboard = [[InlineKeyboardButton("إنهاء الوقت ⏹️", callback_data="timer_stop_select_user")]]
                await query.edit_message_text(
                    f"✅ تم بدء عداد الوقت لـ '{user_name}' في مهمة '{work_type}' الساعة {datetime.now().strftime('%H:%M:%S')}.",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

        elif action == "stop_timer_all":
            if not active_timers:
                await query.edit_message_text("لا توجد أي عدادات وقت نشطة لإيقافها.")
            else:
                message = "✅ تم إيقاف جميع العدادات النشطة:\n\n"
                for user_name in list(active_timers.keys()):
                    start_info = active_timers.pop(user_name)
                    work_type = start_info['work_type']
                    duration = round((datetime.now() - start_info['start_time']).total_seconds() / 60)
                    all_data["users"][user_name][work_type] += duration
                    message += f"👤 {user_name} ({work_type}): +{duration} دقيقة\n"
                
                save_app_state()

                keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]]
                await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif action == "calculate_money_select_user":
            keyboard = [[InlineKeyboardButton(name, callback_data=f"calculate_for:{name}")] for name in USER_NAMES]
            keyboard.append([InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")])
            await query.edit_message_text("اختر الشخص لحساب مستحقاته المالية:", reply_markup=InlineKeyboardMarkup(keyboard))

        elif action == "admin_menu":
            if user_id == ADMIN_USER_ID:
                user_reset_buttons = [[InlineKeyboardButton(f"❌ صفّر عداد {name}", callback_data=f"reset_user_confirm:{name}")] for name in USER_NAMES]
                keyboard = [
                    [InlineKeyboardButton("♻️ تصفير عداد الجميع", callback_data="reset_all_confirm")],
                    *user_reset_buttons,
                    [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]
                ]
                await query.edit_message_text("قائمة المدير (يرجى الحذر):", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await context.bot.send_message(chat_id=user_id, text="عذراً، هذا الخيار متاح للمدير فقط.")

        elif action == "reset_all_confirm":
            if user_id == ADMIN_USER_ID:
                keyboard = [
                    [InlineKeyboardButton("✅ نعم، قم بالتصفير", callback_data="reset_all_execute")],
                    [InlineKeyboardButton("❌ لا، الغاء", callback_data="admin_menu")]
                ]
                await query.edit_message_text(
                    "⚠️ *هل أنت متأكد أنك تريد تصفير عداد الجميع؟*\nهذا الإجراء لا يمكن التراجع عنه وسوف يوقف جميع العدادات النشطة.",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            else:
                await context.bot.send_message(chat_id=user_id, text="عذراً، هذا الخيار متاح للمدير فقط.")

        elif action == "main_menu":
            await start_command(update, context)

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
            else:
                keyboard = [[InlineKeyboardButton(name, callback_data=f"stop_timer_for:{name}")] for name in active_users]
                keyboard.append([InlineKeyboardButton("⏹️ إنهاء للجميع", callback_data="stop_timer_all")])
                keyboard.append([InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")])
                await query.edit_message_text("اختر المستخدم الذي تريد إيقاف عداده:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- دالة رئيسية لتشغيل البوت ---
def main():
    """الدالة الرئيسية لإعداد وتشغيل البوت."""
    print("Bot is starting...")
    load_app_state()
    
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Polling...")
    app.run_polling()


if __name__ == '__main__':
    main()
