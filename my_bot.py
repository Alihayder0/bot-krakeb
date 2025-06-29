بالتأكيد، فهمت طلبك. سأقوم بإزالة "قسم الصيانة" بالكامل من كود البوت الذي قدمته، بما في ذلك التنبيهات الدورية، متغيرات الحالة، والدوال المتعلقة به، لأنه غير ضروري لك في الوقت الحالي.

لقد قمت أيضًا بإصلاح خطأ تكرار الكود في دالة `save_data` واعتمدت النسخة الأفضل والأكثر أمانًا.

إليك الكود بعد التعديل، جاهز للنسخ والاستخدام:

```python
# -*- coding: utf-8 -*-
import os
import json
import subprocess
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

USER_NAMES = ["علي", "فهد", "حميد", "حيدر", "رامي", "سارة", "زيد", "بسمة"]
WORK_TYPES = ["طباعة", "عمل يدوي"]

RATES_PER_HOUR = {
    "طباعة": 2000,
    "عمل يدوي": 2000
}

# --- متغيرات لحفظ الحالة الحالية ---
active_timers = {}

# --- دوال التعامل مع البيانات ---
def load_data():
    """
    تحميل بيانات المستخدمين.
    """
    # الهيكل الافتراضي الجديد بدون معلومات النظام
    default_structure = {
        "users": {user: {work_type: 0 for work_type in WORK_TYPES} for user in USER_NAMES}
    }
    
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # دمج لضمان وجود كل المستخدمين الجدد
            default_structure['users'].update(data.get('users', {}))
            return default_structure
        except (json.JSONDecodeError, FileNotFoundError):
            return default_structure # في حالة الخطأ، ارجع الهيكل الافتراضي
    return default_structure

def save_data(data):
    """
    حفظ البيانات وعمل commit + push تلقائي إلى GitHub.
    """
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    try:
        # subprocess هو الخيار الأفضل والأكثر أمانًا من os.system
        result = subprocess.run(["git", "status", "--porcelain", DATA_FILE], capture_output=True, text=True)
        if result.stdout.strip(): # إذا كان هناك مخرجات، يعني أن الملف تغير
            print(f"تغييرات مكتشفة في {DATA_FILE}. بدء النسخ الاحتياطي...")
            subprocess.run(["git", "add", DATA_FILE], check=True)
            commit_message = f"Auto backup: {datetime.now().isoformat()}"
            subprocess.run(["git", "commit", "-m", commit_message], check=True)
            subprocess.run(["git", "push", "origin", "main"], check=True) # غيّر "main" إذا كان اسم الفرع مختلف
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
    
    # تحديد هل نرسل رسالة جديدة أو نعدل رسالة قائمة
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
    await query.answer()

    data = query.data
    user_id = query.from_user.id

    parts = data.split(':')
    action = parts[0]

    if action == "stop_timer_for":
        user_name = parts[1]
        if user_name not in active_timers:
            await query.answer(f"لا يوجد عداد نشط لـ '{user_name}'.", show_alert=True)
            return

        start_info = active_timers.pop(user_name)
        work_type = start_info['work_type']
        duration = round((datetime.now() - start_info['start_time']).total_seconds() / 60)

        all_data = load_data()
        all_data["users"].setdefault(user_name, {}).setdefault(work_type, 0)
        all_data["users"][user_name][work_type] += duration
        save_data(all_data)

        keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]]
        await query.edit_message_text(
            f"✅ تم إيقاف عداد '{work_type}' لـ '{user_name}'.\n"
            f"مدة العمل: {duration} دقيقة.\n"
            f"إجمالي دقائق '{work_type}' الآن: {all_data['users'][user_name][work_type]} دقيقة.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif action == "view_totals":
        all_data = load_data()
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
            message += "\n"
        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]]
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif action == "calculate_for":
        user_name = parts[1]
        all_data = load_data()
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
        all_data = load_data()
        all_data["users"][user_name] = {work: 0 for work in WORK_TYPES}
        save_data(all_data)
        keyboard = [[InlineKeyboardButton("🔙 رجوع لقائمة المدير", callback_data="admin_menu")]]
        await query.edit_message_text(f"✅ تم تصفير إجمالي وقت العمل للمستخدم '{user_name}'.", reply_markup=InlineKeyboardMarkup(keyboard))

    elif action == "reset_all_execute":
        if user_id == ADMIN_USER_ID:
            all_data = load_data()
            all_data["users"] = {name: {w: 0 for w in WORK_TYPES} for name in USER_NAMES}
            save_data(all_data)
            keyboard = [[InlineKeyboardButton("🔙 رجوع لقائمة المدير", callback_data="admin_menu")]]
            await query.edit_message_text("✅ تم تصفير عدادات جميع المستخدمين بنجاح.", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.answer("عذراً، هذا الخيار متاح للمدير فقط.", show_alert=True)

    elif action == "select_work":
        user_name, work_type = parts[1], parts[2]
        if user_name in active_timers:
            await query.edit_message_text(f"يوجد عداد وقت نشط بالفعل لـ '{user_name}'.")
            return
        active_timers[user_name] = {'start_time': datetime.now(), 'work_type': work_type}
        keyboard = [[InlineKeyboardButton("إنهاء الوقت ⏹️", callback_data="timer_stop_select_user")]]
        await query.edit_message_text(
            f"✅ تم بدء عداد الوقت لـ '{user_name}' في مهمة '{work_type}' الساعة {datetime.now().strftime('%H:%M:%S')}.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif action == "stop_timer_all":
        if not active_timers:
            await query.edit_message_text("لا توجد أي عدادات وقت نشطة لإيقافها.")
            return
        all_data = load_data()
        message = "✅ تم إيقاف جميع العدادات النشطة:\n\n"
        for user_name in list(active_timers.keys()):
            start_info = active_timers.pop(user_name)
            work_type = start_info['work_type']
            duration = round((datetime.now() - start_info['start_time']).total_seconds() / 60)
            all_data["users"].setdefault(user_name, {}).setdefault(work_type, 0)
            all_data["users"][user_name][work_type] += duration
            message += f"👤 {user_name} ({work_type}): +{duration} دقيقة\n"
        save_data(all_data)
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
            await query.answer("عذراً، هذا الخيار متاح للمدير فقط.", show_alert=True)

    elif action == "reset_all_confirm":
        if user_id == ADMIN_USER_ID:
            keyboard = [
                [InlineKeyboardButton("✅ نعم، قم بالتصفير", callback_data="reset_all_execute")],
                [InlineKeyboardButton("❌ لا، الغاء", callback_data="admin_menu")]
            ]
            await query.edit_message_text(
                "⚠️ *هل أنت متأكد أنك تريد تصفير عداد الجميع؟*\nهذا الإجراء لا يمكن التراجع عنه.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await query.answer("عذراً، هذا الخيار متاح للمدير فقط.", show_alert=True)

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
            return
        
        keyboard = [[InlineKeyboardButton(name, callback_data=f"stop_timer_for:{name}")] for name in active_users]
        keyboard.append([InlineKeyboardButton("⏹️ إنهاء للجميع", callback_data="stop_timer_all")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")])
        await query.edit_message_text("اختر المستخدم الذي تريد إيقاف عداده:", reply_markup=InlineKeyboardMarkup(keyboard))

    else:
        await query.answer("عذراً، الخيار غير معروف.", show_alert=True)

# --- دالة رئيسية لتشغيل البوت ---
def main():
    """الدالة الرئيسية لإعداد وتشغيل البوت."""
    print("Bot is starting...")
    load_data()
    
    app = Application.builder().token(TOKEN).build()

    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Polling...")
    app.run_polling()


if __name__ == '__main__':
    main()
```