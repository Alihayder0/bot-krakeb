import os
import json
import subprocess
import asyncio
import threading
import time
import random
import uuid
import base64
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# استيراد حزم معالجة الملفات
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# --- الإعدادات الرئيسية ---
load_dotenv()

# تحميل الإعدادات مع معالجة الأخطاء
TOKEN = os.getenv("TOKEN")
ADMIN_USER_ID_STR = os.getenv("ADMIN_ID")
# The channel identifier can be either a username (without @) or a numeric chat id (e.g. -1001234567890).
# Backwards-compatible: if CHANNEL_IDENTIFIER is not set, fall back to CHANNEL_USERNAME for older .env files.
CHANNEL_IDENTIFIER_RAW = os.getenv("CHANNEL_IDENTIFIER", os.getenv("CHANNEL_USERNAME", "mawad_taba3"))

# Normalize channel identifier: if it's numeric (e.g. -100...), use as int chat id, else keep username string
CHANNEL_ID = None
CHANNEL_USERNAME = None
if CHANNEL_IDENTIFIER_RAW:
    cid = str(CHANNEL_IDENTIFIER_RAW).strip()
    # strip leading @ if present for usernames
    if cid.startswith('@'):
        cid = cid[1:]
    try:
        # treat purely numeric values (possibly negative) as channel id
        CHANNEL_ID = int(cid)
    except (ValueError, TypeError):
        CHANNEL_USERNAME = cid

# التحقق من صحة TOKEN
if not TOKEN or "Example" in TOKEN or TOKEN == "YOUR_BOT_TOKEN_HERE":
    print("❌ خطأ: TOKEN غير صحيح في ملف .env")
    print("📋 يرجى:")
    print("   1. تحرير ملف .env")
    print("   2. وضع TOKEN الصحيح من @BotFather")
    print("   3. التأكد من حفظ الملف")
    exit(1)

# التحقق من صحة ADMIN_ID
if not ADMIN_USER_ID_STR or ADMIN_USER_ID_STR == "123456789":
    print("❌ خطأ: ADMIN_ID غير صحيح في ملف .env")
    print("📋 يرجى:")
    print("   1. الحصول على معرفك الرقمي من @userinfobot")
    print("   2. وضعه في ADMIN_ID في ملف .env")
    print("   3. التأكد من حفظ الملف")
    exit(1)

try:
    ADMIN_USER_ID = int(ADMIN_USER_ID_STR)
except (ValueError, TypeError):
    print(f"❌ خطأ: ADMIN_ID يجب أن يكون رقماً صحيحاً، وليس '{ADMIN_USER_ID_STR}'")
    exit(1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")

USER_NAMES = ["علي", "فهد", "حميد", "حيدر", "رامي", "سارة", "زيد", "بسمة", "هاشم"]
WORK_TYPES = ["طباعة", "عمل يدوي"]

RATES_PER_HOUR = {
    "طباعة": 2000,
    "عمل يدوي": 2000
}

# --- قواعد البيانات الترفيهية ---
JOKES_DATABASE = [
    "ليش المبرمج يحب القهوة؟ لأنه بدونها ما يكدر يcompile! ☕️😄",
    "شنو الفرق بين المبرمج والمطور؟ المبرمج يكتب الكود والمطور يعيد كتابة نفس الكود 10 مرات! 🤪",
    "المبرمج الحقيقي يحل المشاكل اللي ما كانت موجودة أصلاً 😅",
    "Bug موجود؟ مو bug، هذي feature جديدة! 🐛➡️✨",
    "لمن يسألونك 'شلون تشتغل؟' قلهم: Copy + Paste + Stack Overflow 😎",
    "أفضل طريقة لتتعلم البرمجة: اكسر الكود، صلحه، اكسره مرة ثانية! 🔨💻",
    "التعليقات في الكود مثل الوعود... كلها كذب! 📝🤥",
    "المبرمج الوحيد اللي ما عنده bugs هو المبرمج اللي ما كتب كود! 🤷‍♂️",
    "شنو يقول المبرمج لما يشوف كوده بعد سنة؟ 'مين الأحمق اللي كتب هذا؟!' 🤔😱",
    "الفرق بين النظرية والواقع: في النظرية ما في فرق، بس في الواقع... والله فرق! 🤓"
]

MOTIVATIONAL_QUOTES = [
    "الشغل الجاد يدفع... بس الشغل الذكي يدفع أكثر! 💪💰",
    "كل دقيقة تشتغل فيها هي خطوة للأمام! 🚶‍♂️⏰",
    "المهنية ما تجي بالحظ، تجي بالممارسة والإتقان! ✨",
    "أنت أقوى مما تتصور، وأقدر على إنجاز أكثر مما تتخيل! 🔥",
    "الوقت ذهب، فلا تضيعه في شي ما يستاهل! ⏳💎",
    "اليوم الجديد = فرصة جديدة للتميز! 🌅",
    "الطموح بلا حدود، والإنجاز بلا توقف! 🚀",
    "أنت النجم اللي يضوي مكان الشغل! ⭐",
    "صبرك اليوم = نجاحك بكرة! 🌱➡️🌳",
    "كل عمل عظيم بدأ بخطوة واحدة بسيطة! 👣"
]

WORK_REACTIONS = [
    "يلا نشتغل! 💪",
    "وقت الجد! ⏰",
    "خلينا نبدع! ✨",
    "الله يوفقك! 🤲",
    "تسلم إيدك! 👏",
    "ماشي الحال! 😎",
    "شد حيلك! 💪",
    "بالتوفيق! 🍀"
]

ROASTS = [
    "انت أبطأ من انترنت الطلبة! 🐌💻",
    "شغلك مثل WiFi البيت... يقطع في أهم لحظة! 📶❌",
    "لو كان الكسل مهنة، انت كنت CEO! 😴👔",
    "انت تشتغل مثل برنامج Windows... بطيء ويعلق كثير! 🪟🐌",
    "سرعتك في الشغل تخلي السلحفاة تبدو مثل فهد! 🐢🏃‍♂️",
    "لو كان للكسل أولمبياد، انت كنت حصلت على ذهبية! 🏅😴"
]

COMPLIMENTS = [
    "انت نجم في الشغل! كل الاحترام! ⭐👏",
    "ما شاء الله عليك، دائماً مبدع! 🌟",
    "أسلوبك في الشغل يخلي الكل يتعلم منك! 📚✨",
    "انت مثال للجدية والاحترافية! 💼👌",
    "شغلك دائماً في القمة! فخر لأي فريق! 🏆",
    "إبداعك ما له حدود! 🎨🚀",
    "انت قدوة في الانضباط والتميز! 🎯",
    "ما شاء الله، دائماً تفاجئنا بالإنجازات! 🎉"
]

WISDOM_QUOTES = [
    "العلم في الصغر مثل النقش على الحجر... والكسل في الكبر مثل النقش على الماء! 🧠💎",
    "اللي ما يتعب في شغله، يتعب في فقره! 💪💰",
    "الوقت زي السيف، إن ما قطعت به قطعك! ⚔️⏰",
    "العمل عبادة، والإتقان سنة! 🤲✨",
    "اللي يزرع اليوم، يحصد بكرة! 🌱🌾",
    "المعرفة قوة، والتطبيق انتصار! 📚🏆",
    "النجاح 10% إلهام و 90% عرق! 💡💦",
    "اللي ما عنده هدف، يشتغل لهدف الغير! 🎯"
]

# --- الأسماء المشاغبة للتفاعلات الخاصة ---
NAUGHTY_NAMES = ["حيدر", "حمادة", "حميد", "علي", "هاشم", "رامي", "فهد"]

# --- ردود التنمر والمشاغبة (محدثة) ---
NAUGHTY_RESPONSES = {
    "حيدر": [
        "وصل حيدر الخبطة! 🤕 شنو خبطت اليوم؟ �",
        "حيدر يا حيدر، شنو ياخذ الروح  �️",
        "أهلين بحيدر! مsرة ثانية متأخر؟ الساعة موجودة! ⏰😤",
        "حيدر المعوق وصل! متى راح تتعلم تمشي صح؟ 🦯�",
    ],
    "حمادة": [
        "حمودي! وصل الكسول الأسطوري! 🏆�",
        "حمادة يا حمادة، ترة الشغل مو نوم! 😪➡️💼",
        "أهلا بحمادة النوامة! قوم نشتغل! 🛌➡️🏃‍♂️",
        "حمادة الغفلان وصل! فوق فوق! ⏰",
    ],
    "حميد": [
        "حميد الأسود وصل! 🖤 شنو المصيبة اليوم؟ 🤪",
        "وين حميد الداكن؟ شغل الضوء نشوفك! 💡�",
        "حميد يا حميد، كل يوم لك طقوس غريبة! 🎭",
        "حميد العبقري وصل! استعدوا للمفاجآت! 🎪",
    ],
    "علي": [
        "علي علي علي! الملك وصل؟ �😂",
        "أهلا بعلي العظيم! شنو أوامرك اليوم؟ 🎩",
        "علي يا حبيبي، متى راح تنزل من العرش؟ 👑➡️🪑",
        "وصل علي المهيب! كلكم احترام! �‍♂️",
    ],
    "هاشم": [
        "هاشم القصير وصل! 📏 شلونك يا قزم؟ 🤪",
        "هاشوم الصغنون! احتجت سلم تطلع؟ 🪜😂",
        "هاشم يا قصيرة، وين الكرسي المساعد؟ 🪑",
        "وصل هاشم الجيبي! حط تيليفونك تشوف! 📱�",
    ],
    "رامي": [
        "رامي الرمادي! شبيك داكن اليوم؟ 🌫️�",
        "أهلين برامي الغامق! شمس اليوم قوية احذر! ☀️😎",
        "رامي يا أسمر، البس نظارة لا نضيع! 🕶️",
        "وصل رامي الليلي! شغل الضوء نشوفك! 💡",
    ],
    "فهد": [
        "فهد البطيء وصل! 🐌 شبيك أبطأ من السلحفاة؟",
        "فهودي الكسول! متى راح تصير سريع زي اسمك؟ 🐅➡️�",
        "فهد يا فهد، انت عكس اسمك تماماً! 😂",
        "وصل الفهد المكسور! صلح نفسك وتعال! 🔧�",
    ]
}

# --- ردود عادية للأسماء الأخرى ---
NORMAL_RESPONSES = [
    "أهلاً وسهلاً! جاهز للعمل والإنتاج؟ 💪",
    "مرحباً بك! خلينا نسوي إنجازات اليوم! ✨",
    "أهلين! اليوم راح يكون يوم رائع للشغل! 🌟",
    "وصلت في الوقت المناسب! يلا نبدأ! 🚀",
    "أهلا بالمحترف! متحمس أشوف إنجازاتك اليوم! 🎯"
]

# --- البطل اليومي ---
daily_hero_data = {}

def get_daily_hero():
    """اختيار بطل اليوم"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    if today not in daily_hero_data:
        # اختيار بطل عشوائي لليوم
        daily_hero_data[today] = random.choice(USER_NAMES)
    
    return daily_hero_data[today]

def get_hero_message(hero_name):
    """رسالة خاصة بالبطل"""
    messages = [
        f"🏆 {hero_name} هو بطل اليوم! كل الاحترام والتقدير! 👑",
        f"⭐ اليوم {hero_name} النجم الأول! يستاهل كل التقدير! 🌟",
        f"🎖️ البطل {hero_name} في المقدمة دائماً! فخر للفريق! 💪",
        f"🏅 {hero_name} بطل بكل معنى الكلمة! عاشت الأيادي! 👏"
    ]
    return random.choice(messages)

def get_personalized_response(user_name):
    """الحصول على رد مخصص حسب الاسم"""
    if not user_name:
        return random.choice(NORMAL_RESPONSES)
    
    # تحديد إذا كان البطل اليومي
    today_hero = get_daily_hero()
    
    if user_name == today_hero:
        return get_hero_message(user_name)
    elif user_name in NAUGHTY_NAMES:
        return random.choice(NAUGHTY_RESPONSES[user_name])
    else:
        return random.choice(NORMAL_RESPONSES)

# متغيرات للفيتشرز الترفيهية
last_joke_time = {}
user_streaks = {}  # عدد الأيام المتتالية للشغل

# --- إعدادات نظام الطباعة ---
PRINT_TASK_STATUS = {
    "pending": "⏳ في الانتظار",
    "in_progress": "🔄 جاري العمل",
    "completed": "✅ مكتملة",
    "cancelled": "❌ ملغية"
}

PRINT_PRIORITIES = {
    "low": "🟢 عادية",
    "medium": "🟡 متوسطة", 
    "high": "🔴 عاجلة",
    "urgent": "🚨 طارئة"
}

# --- متغيرات لحفظ الحالة العامة للتطبيق ---
all_data = {}
active_timers = {}
lock = asyncio.Lock() # قفل لمنع تضارب البيانات
# تخزين مؤقت للملفات التي تنتظر وصف المهمة من المستخدم (user_id -> pending info)
pending_uploads = {}

# --- دوال التعامل مع البيانات ---

def load_app_state():
    """
    تحميل حالة التطبيق الكاملة (بيانات المستخدمين والعدادات النشطة) من ملف data.json.
    """
    global all_data, active_timers
    
    default_structure = {
        "users": {user: {work_type: 0 for work_type in WORK_TYPES} for user in USER_NAMES},
        "active_timers": {},
        # قائمة معرفات المستخدمين (Telegram user_id) المسموح لهم بتعديل أوقاتهم
        "self_edit_allowed_ids": [],
        # ربط معرفات التلغرام بأسماء المستخدمين في القائمة
        "user_links": {},
        # نظام إدارة الطباعة
        "print_tasks": {},  # قاموس للمهام: task_id -> task_info
        "print_settings": {
            "auto_receive_from_channel": True,
            "default_priority": "medium",
            "task_counter": 0
        }
    }
    
    if not os.path.exists(DATA_FILE):
        all_data = default_structure
        save_app_state()
        return

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
        
        # ضمان وجود الهياكل الأساسية
        all_data.setdefault("users", {})
        all_data.setdefault("active_timers", {})
        all_data.setdefault("self_edit_allowed_ids", [])
        all_data.setdefault("user_links", {})
        all_data.setdefault("print_tasks", {})
        all_data.setdefault("print_settings", {
            "auto_receive_from_channel": True,
            "default_priority": "medium", 
            "task_counter": 0
        })

        # ضمان وجود جميع المستخدمين الحاليين في البيانات
        for user in USER_NAMES:
            all_data["users"].setdefault(user, {work_type: 0 for work_type in WORK_TYPES})

        # استعادة العدادات النشطة من الملف
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

def minutes_between(start_time: datetime, end_time: datetime) -> int:
    """حساب الدقائق بين وقتين مع التقريب للأسفل لتجنب التضخيم عند تعدد الإيقافات."""
    delta_sec = max(0, (end_time - start_time).total_seconds())
    return int(delta_sec // 60)

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_USER_ID

def get_linked_name(user_id: int) -> str | None:
    # نخزن المفاتيح كسلاسل في JSON
    return all_data.get("user_links", {}).get(str(user_id))

def has_self_edit_permission(user_id: int) -> bool:
    allowed = all_data.get("self_edit_allowed_ids", [])
    return user_id in allowed or str(user_id) in allowed

async def send_typing_animation(context, chat_id, duration=2):
    """إرسال تأثير الكتابة لعدة ثوان"""
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(duration)
    except:
        pass

def get_random_reaction():
    """الحصول على رد فعل عشوائي"""
    return random.choice(WORK_REACTIONS)

def get_work_encouragement(user_name):
    """رسائل تشجيعية مخصصة حسب الوقت"""
    current_hour = datetime.now().hour
    
    if 6 <= current_hour < 12:
        return f"صباح الخير {user_name}! يلا نبدأ اليوم بقوة! 🌅💪"
    elif 12 <= current_hour < 17:
        return f"الله يعطيك العافية {user_name}! شغل الضهر دائماً مثمر! ☀️⚡"
    elif 17 <= current_hour < 21:
        return f"مساء النشاط {user_name}! خلينا نكمل بقوة! 🌇🔥"
    else:
        return f"سهرة عمل {user_name}؟ احترافي! بس لا تنسى الراحة! 🌙😴"

def calculate_user_streak(user_name):
    """حساب عدد الأيام المتتالية للعمل"""
    # منطق بسيط: إذا شتغل اليوم يبقى الstreak، وإلا يصفر
    user_times = all_data.get("users", {}).get(user_name, {})
    if sum(user_times.values()) > 0:
        return user_streaks.get(user_name, 0) + 1
    return 0

# --- دوال استخراج النص من الملفات ---

def extract_text_from_pdf(file_bytes):
    """استخراج النص من ملف PDF"""
    if not PDF_AVAILABLE:
        return None, "PDF reader not available"
    
    try:
        from io import BytesIO
        pdf_file = BytesIO(file_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        text_content = ""
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text_content += page.extract_text() + "\n"
        
        return text_content.strip(), None
    except Exception as e:
        return None, f"Error reading PDF: {str(e)}"

def extract_text_from_image(file_bytes):
    """استخراج النص من الصورة باستخدام OCR"""
    if not OCR_AVAILABLE:
        return None, "OCR not available"
    
    try:
        from io import BytesIO
        image_file = BytesIO(file_bytes)
        image = Image.open(image_file)
        
        # تحسين الصورة للـ OCR
        image = image.convert('L')  # تحويل للرمادي
        
        # استخراج النص
        text_content = pytesseract.image_to_string(image, lang='ara+eng')
        return text_content.strip(), None
    except Exception as e:
        return None, f"Error extracting text from image: {str(e)}"

def extract_text_from_docx(file_bytes):
    """استخراج النص من ملف Word"""
    if not DOCX_AVAILABLE:
        return None, "DOCX reader not available"
    
    try:
        from io import BytesIO
        docx_file = BytesIO(file_bytes)
        doc = Document(docx_file)
        
        text_content = ""
        for paragraph in doc.paragraphs:
            text_content += paragraph.text + "\n"
        
        return text_content.strip(), None
    except Exception as e:
        return None, f"Error reading DOCX: {str(e)}"

def extract_text_from_file(file_bytes, filename):
    """استخراج النص من أي نوع ملف مدعوم"""
    filename_lower = filename.lower()
    
    # تحديد نوع الملف واستخراج النص
    if filename_lower.endswith('.pdf'):
        return extract_text_from_pdf(file_bytes)
    
    elif filename_lower.endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif')):
        return extract_text_from_image(file_bytes)
    
    elif filename_lower.endswith('.docx'):
        return extract_text_from_docx(file_bytes)
    
    elif filename_lower.endswith(('.txt', '.text')):
        # معالجة ملفات النص العادية
        try:
            content = file_bytes.decode('utf-8')
            return content, None
        except UnicodeDecodeError:
            try:
                content = file_bytes.decode('utf-8-sig')
                return content, None
            except UnicodeDecodeError:
                try:
                    content = file_bytes.decode('windows-1256')
                    return content, None
                except UnicodeDecodeError:
                    return None, "Unable to decode text file"
    
    else:
        return None, f"Unsupported file type: {filename}"

def get_file_type_emoji(filename):
    """الحصول على رمز حسب نوع الملف"""
    filename_lower = filename.lower()
    
    if filename_lower.endswith('.pdf'):
        return "📄"
    elif filename_lower.endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif')):
        return "🖼️"
    elif filename_lower.endswith('.docx'):
        return "📝"
    elif filename_lower.endswith(('.txt', '.text')):
        return "📄"
    else:
        return "📁"

def create_print_task(content=None, filename=None, priority="medium", source="manual", file_data=None, file_metadata=None):
    """إنشاء مهمة طباعة جديدة مع دعم الملفات الكاملة"""
    task_id = str(uuid.uuid4())[:8]  # معرف قصير
    all_data["print_settings"]["task_counter"] += 1
    
    task = {
        "id": task_id,
        "number": all_data["print_settings"]["task_counter"],
        "content": content or "",  # النص المستخرج أو المكتوب
        "filename": filename or f"مهمة_{task_id}",
        "priority": priority,
        "status": "pending",
        "source": source,  # manual, channel, upload, text_message
        "created_at": datetime.now().isoformat(),
        "assigned_to": None,
        "started_at": None,
        "completed_at": None,
        "notes": "",
        
        # بيانات الملف الكاملة (جديد!)
        "file_data": file_data,  # الملف مشفر base64
        "file_metadata": file_metadata or {},  # معلومات الملف
        "has_file": file_data is not None,
        "file_type": get_file_type_from_name(filename) if filename else "text"
    }
    
    all_data["print_tasks"][task_id] = task
    save_app_state()
    return task_id

def get_file_type_from_name(filename):
    """تحديد نوع الملف من الاسم"""
    if not filename:
        return "unknown"
    
    filename_lower = filename.lower()
    if filename_lower.endswith('.pdf'):
        return "pdf"
    elif filename_lower.endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif')):
        return "image"
    elif filename_lower.endswith('.docx'):
        return "docx"
    elif filename_lower.endswith(('.txt', '.text')):
        return "text"
    else:
        return "other"

def get_tasks_by_status(status):
    """الحصول على المهام حسب الحالة"""
    return {tid: task for tid, task in all_data.get("print_tasks", {}).items() 
            if task["status"] == status}

def update_task_status(task_id, new_status, assigned_to=None, notes=""):
    """تحديث حالة المهمة"""
    tasks = all_data.get("print_tasks", {})
    if task_id not in tasks:
        return None

    task = tasks[task_id]
    old_status = task.get("status")

    # إلغاء المهمة: نحذفها نهائياً من النظام لتوفير المساحة
    if new_status == "cancelled":
        removed = tasks.pop(task_id, None)
        if removed is not None:
            save_app_state()
        return removed

    # تغييرات الحالة العادية
    task["status"] = new_status
    if assigned_to:
        task["assigned_to"] = assigned_to
    if notes:
        task["notes"] = notes

    current_time = datetime.now().isoformat()
    if new_status == "in_progress" and old_status == "pending":
        task["started_at"] = current_time
    elif new_status == "completed":
        task["completed_at"] = current_time

    save_app_state()
    return task

def get_print_stats():
    """إحصائيات مهام الطباعة"""
    tasks = all_data.get("print_tasks", {})
    stats = {
        "total": len(tasks),
        "pending": len([t for t in tasks.values() if t["status"] == "pending"]),
        "in_progress": len([t for t in tasks.values() if t["status"] == "in_progress"]),
        "completed": len([t for t in tasks.values() if t["status"] == "completed"]),
        # cancelled tasks are deleted immediately; keep the field for compatibility
        "cancelled": 0
    }
    return stats


def get_tasks_by_priority(priority: str):
    """Return tasks filtered by priority."""
    tasks = all_data.get("print_tasks", {})
    return {tid: t for tid, t in tasks.items() if t.get("priority") == priority}


async def prioritytasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /prioritytasks لعرض المهام ذات الأولوية العالية"""
    high_tasks = get_tasks_by_priority('high')
    if not high_tasks:
        await update.message.reply_text("لا توجد مهام ذات أولوية عالية حالياً.")
        return

    message = "🚨 *مهام ذات أولوية عالية:*\n\n"
    for t in sorted(high_tasks.values(), key=lambda x: x.get('created_at')):
        created = datetime.fromisoformat(t['created_at']).strftime('%Y-%m-%d')
        preview = t.get('content','')[:120] + ('...' if len(t.get('content',''))>120 else '')
        message += f"\n• #{t['number']} — {t['filename']} — {t['status']} — {created}\n  {preview}\n"

    await update.message.reply_text(message, parse_mode='Markdown')

def format_task_info(task, show_content=False):
    """تنسيق معلومات المهمة للعرض"""
    priority_icon = {"low": "🟢", "medium": "🟡", "high": "🔴", "urgent": "🚨"}
    status_icon = {"pending": "⏳", "in_progress": "🔄", "completed": "✅", "cancelled": "❌"}
    
    # رمز نوع الملف
    file_emoji = get_file_type_emoji(task['filename'])
    
    info = f"{status_icon.get(task['status'], '❓')} *المهمة #{task['number']}*\n"
    info += f"{file_emoji} {task['filename']}\n"
    info += f"{priority_icon.get(task['priority'], '⚪')} {PRINT_PRIORITIES.get(task['priority'], 'غير محدد')}\n"
    
    # معلومات الملف إذا كان موجود
    if task.get('has_file') and task.get('file_metadata'):
        metadata = task['file_metadata']
        info += f"📊 الحجم: {metadata.get('size_mb', 'غير معروف')} MB\n"
        info += f"🎯 النوع: {task.get('file_type', 'غير محدد').upper()}\n"
    
    if task.get("assigned_to"):
        info += f"👤 مكلف: {task['assigned_to']}\n"
    
    created = datetime.fromisoformat(task["created_at"])
    info += f"📅 أنشئت: {created.strftime('%Y-%m-%d %H:%M')}\n"
    
    if task.get("started_at"):
        started = datetime.fromisoformat(task["started_at"])
        info += f"▶️ بدأت: {started.strftime('%Y-%m-%d %H:%M')}\n"
    
    if task.get("completed_at"):
        completed = datetime.fromisoformat(task["completed_at"])
        info += f"✅ اكتملت: {completed.strftime('%Y-%m-%d %H:%M')}\n"

    # إذا تم حفظ نص مستخرج داخل metadata، لا نعرضه افتراضياً (مساحة وحشية)
    # ولكن نوضح وجود نص مستخرج في الميتاداتا
    if task.get('file_metadata') and task['file_metadata'].get('extracted_text'):
        info += f"📝 (يتضمن وصفًا مستخرجًا مخزنًا في metadata)\n"
    
    if task.get("notes"):
        info += f"📝 ملاحظات: {task['notes']}\n"
    
    if show_content and task.get("content"):
        content_preview = task["content"][:200] + "..." if len(task["content"]) > 200 else task["content"]
        info += f"\n📄 المحتوى/النص:\n```\n{content_preview}\n```"
    
    return info

async def send_original_file(context, chat_id, task_id):
    """إرسال الملف الأصلي للمهمة"""
    if task_id not in all_data.get("print_tasks", {}):
        return False, "المهمة غير موجودة"
    
    task = all_data["print_tasks"][task_id]
    
    if not task.get('has_file') or not task.get('file_data'):
        return False, "لا يوجد ملف أصلي مرفق مع هذه المهمة"
    
    try:
        # فك تشفير الملف
        file_bytes = base64.b64decode(task['file_data'])
        
        # إرسال الملف
        from io import BytesIO
        file_obj = BytesIO(file_bytes)
        file_obj.name = task['filename']
        
        await context.bot.send_document(
            chat_id=chat_id,
            document=file_obj,
            filename=task['filename'],
            caption=f"📁 الملف الأصلي للمهمة #{task['number']}\n🎯 {task['filename']}"
        )
        
        return True, "تم إرسال الملف بنجاح"
        
    except Exception as e:
        return False, f"خطأ في إرسال الملف: {str(e)}"

# --- معالجات الأوامر والأزرار ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """المعالج الخاص بأمر /start والقائمة الرئيسية."""
    
    # إضافة تأثير الكتابة
    await send_typing_animation(context, update.effective_chat.id, 1)
    
    # رسالة ترحيب مخصصة حسب الشخص
    user_id = update.effective_user.id
    linked_name = get_linked_name(user_id)
    
    if linked_name:
        message_text = get_personalized_response(linked_name)
    else:
        greetings = [
            "أهلاً وسهلاً! جاهز للعمل والإنتاج؟ 🚀",
            "مرحباً بك في عالم الإنتاجية! ✨",
            "يلا نشتغل ونبدع سوا! 💪",
            "وصلت للمكان الصحيح للنجاح! 🎯",
            "أهلاً بالمحترف! خلينا نبدأ! 🔥"
        ]
        message_text = random.choice(greetings)
    
    keyboard = [
        [InlineKeyboardButton("⏱️ بدء وقت العمل", callback_data="timer_start_select_user")],
        [InlineKeyboardButton("🛑 إيقاف وقت العمل", callback_data="timer_stop_select_user")],
        [InlineKeyboardButton("📊 عرض إجمالي الأوقات", callback_data="view_totals")],
        [InlineKeyboardButton("💰 حساب المال", callback_data="calculate_money_select_user")],
        [InlineKeyboardButton("🖨️ إدارة الطباعة", callback_data="print_management")],
        [InlineKeyboardButton("✏️ تعديل وقتي", callback_data="self_edit_menu")],
        [InlineKeyboardButton("🎪 المنطقة الترفيهية", callback_data="fun_zone")],
        [InlineKeyboardButton("🔗 ربط اسمي بحسابي (/linkme)", callback_data="show_linkme_help")],
        [InlineKeyboardButton("⚙️ قائمة المدير", callback_data="admin_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
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

    async with lock:
        data = query.data
        user_id = query.from_user.id
        parts = data.split(':')
        action = parts[0]

        if action == "stop_timer_for":
            user_name = parts[1]
            if user_name in active_timers:
                start_info = active_timers.pop(user_name)
                work_type = start_info['work_type']
                duration = minutes_between(start_info['start_time'], datetime.now())

                all_data["users"][user_name][work_type] += duration
                save_app_state()

                keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]]
                await query.edit_message_text(
                    f"✅ تم إيقاف عداد '{work_type}' لـ '{user_name}'.\n"
                    f"مدة العمل: {duration} دقيقة.\n"
                    f"إجمالي دقائق '{work_type}' الآن: {all_data['users'][user_name][work_type]} دقيقة.",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                # حالة الخطأ: لا يوجد عداد نشط لهذا المستخدم
                keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]]
                await query.edit_message_text(f"لا يوجد عداد نشط لـ '{user_name}'.", reply_markup=InlineKeyboardMarkup(keyboard))

        elif action == "view_totals":
            message = "📊 *إجمالي الدقائق المسجلة لكل شخص:*\n\n"
            for name, work_times in all_data.get("users", {}).items():
                message += f"👤 *{name}*:\n"
                total_minutes = sum(work_times.values())
                if not work_times or total_minutes == 0:
                    message += "  - لا يوجد وقت مسجل.\n"
                else:
                    for work_type, minutes in work_times.items():
                        if minutes > 0:
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
                await query.answer("عذراً، هذا الخيار متاح للمدير فقط.", show_alert=True)

        elif action == "select_work":
            user_name, work_type = parts[1], parts[2]
            if user_name in active_timers:
                await query.edit_message_text(f"يوجد عداد وقت نشط بالفعل لـ '{user_name}'.")
            else:
                active_timers[user_name] = {'start_time': datetime.now(), 'work_type': work_type}
                save_app_state()

                # رسالة تشجيعية مخصصة
                encouragement = get_work_encouragement(user_name)
                reaction = get_random_reaction()
                
                keyboard = [[InlineKeyboardButton("إنهاء الوقت ⏹️", callback_data="timer_stop_select_user")]]
                await query.edit_message_text(
                    f"✅ تم بدء عداد الوقت لـ '{user_name}' في مهمة '{work_type}' الساعة {datetime.now().strftime('%H:%M:%S')}.\n\n{encouragement}\n{reaction}",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

        elif action == "stop_timer_all":
            if not active_timers:
                await query.edit_message_text("لا توجد أي عدادات وقت نشطة لإيقافها.")
            else:
                message = "✅ تم إيقاف جميع العدادات النشطة:\n\n"
                for user_name_to_stop in list(active_timers.keys()):
                    start_info = active_timers.pop(user_name_to_stop)
                    work_type = start_info['work_type']
                    duration = minutes_between(start_info['start_time'], datetime.now())
                    all_data["users"][user_name_to_stop][work_type] += duration
                    message += f"👤 {user_name_to_stop} ({work_type}): +{duration} دقيقة\n"
                
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
                    [InlineKeyboardButton("🛠️ تعديل وقت شخص", callback_data="admin_adjust_select_user")],
                    [InlineKeyboardButton("🔐 إدارة الصلاحيات والربط", callback_data="admin_perm_menu")],
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
                    "⚠️ *هل أنت متأكد أنك تريد تصفير عداد الجميع؟*\nهذا الإجراء لا يمكن التراجع عنه وسوف يوقف جميع العدادات النشطة.",
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
            else:
                keyboard = [[InlineKeyboardButton(name, callback_data=f"stop_timer_for:{name}")] for name in active_users]
                keyboard.append([InlineKeyboardButton("⏹️ إنهاء للجميع", callback_data="stop_timer_all")])
                keyboard.append([InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")])
                await query.edit_message_text("اختر المستخدم الذي تريد إيقاف عداده:", reply_markup=InlineKeyboardMarkup(keyboard))

        # --- تعديلات الوقت من المدير ---
        elif action == "admin_adjust_select_user":
            if not is_admin(user_id):
                await query.answer("خاص بالمدير", show_alert=True)
            else:
                keyboard = [[InlineKeyboardButton(name, callback_data=f"admin_adjust_user:{name}")] for name in USER_NAMES]
                keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_menu")])
                await query.edit_message_text("اختر المستخدم لتعديل وقته:", reply_markup=InlineKeyboardMarkup(keyboard))

        elif action == "admin_adjust_user":
            if not is_admin(user_id):
                await query.answer("خاص بالمدير", show_alert=True)
            else:
                sel_user = parts[1]
                keyboard = [[InlineKeyboardButton(work, callback_data=f"admin_adjust_work:{sel_user}:{work}")] for work in WORK_TYPES]
                keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_adjust_select_user")])
                await query.edit_message_text(f"اختر نوع العمل لتعديل وقت '{sel_user}':", reply_markup=InlineKeyboardMarkup(keyboard))

        elif action == "admin_adjust_work":
            if not is_admin(user_id):
                await query.answer("خاص بالمدير", show_alert=True)
            else:
                sel_user, work = parts[1], parts[2]
                if sel_user in active_timers:
                    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data=f"admin_adjust_user:{sel_user}")]]
                    await query.edit_message_text("⚠️ لا يمكن تعديل الوقت أثناء وجود عداد نشط. أوقف العداد أولاً.", reply_markup=InlineKeyboardMarkup(keyboard))
                else:
                    deltas = [-30, -15, -5, 5, 15, 30]
                    keyboard = [
                        [InlineKeyboardButton(("➖" if d < 0 else "➕") + f" {abs(d)} دقيقة", callback_data=f"admin_apply_delta:{sel_user}:{work}:{d}") for d in deltas[i:i+3]]
                        for i in (0, 3)
                    ]
                    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"admin_adjust_user:{sel_user}")])
                    current = all_data["users"][sel_user][work]
                    await query.edit_message_text(
                        f"تعديل '{sel_user}' للعمل '{work}'.\nالوقت الحالي: {current} دقيقة\nاختر مقدار التعديل:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )

        elif action == "admin_apply_delta":
            if not is_admin(user_id):
                await query.answer("خاص بالمدير", show_alert=True)
            else:
                sel_user, work, delta_str = parts[1], parts[2], parts[3]
                delta = int(delta_str)
                if sel_user in active_timers:
                    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data=f"admin_adjust_user:{sel_user}")]]
                    await query.edit_message_text("⚠️ لا يمكن تعديل الوقت أثناء وجود عداد نشط. أوقف العداد أولاً.", reply_markup=InlineKeyboardMarkup(keyboard))
                else:
                    before = all_data["users"][sel_user][work]
                    after = max(0, before + delta)
                    all_data["users"][sel_user][work] = after
                    save_app_state()
                    keyboard = [
                        [InlineKeyboardButton("↩️ تعديل آخر", callback_data=f"admin_adjust_work:{sel_user}:{work}")],
                        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_adjust_select_user")]
                    ]
                    await query.edit_message_text(
                        f"✅ تم تعديل الوقت. {sel_user} / {work}: {before} → {after} دقيقة.",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )

        # --- إدارة الصلاحيات والربط (المدير) ---
        elif action == "admin_perm_menu":
            if not is_admin(user_id):
                await query.answer("خاص بالمدير", show_alert=True)
            else:
                links = all_data.get("user_links", {})
                allowed = set([str(x) for x in all_data.get("self_edit_allowed_ids", [])])
                rows = []
                if links:
                    for uid_str, name in links.items():
                        status = "مسموح" if uid_str in allowed else "ممنوع"
                        toggle_label = "🚫 سحب السماح" if uid_str in allowed else "✅ منح السماح"
                        rows.append([InlineKeyboardButton(f"{name} ({status})", callback_data="noop"), InlineKeyboardButton(toggle_label, callback_data=f"toggle_permission:{uid_str}")])
                        rows.append([InlineKeyboardButton("🔗 إلغاء الربط", callback_data=f"unlink_user:{uid_str}")])
                else:
                    rows.append([InlineKeyboardButton("لا يوجد مستخدمون مربوطون بعد", callback_data="noop")])
                rows.append([InlineKeyboardButton("ℹ️ إرشادات الربط", callback_data="show_linkme_help")])
                rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_menu")])
                await query.edit_message_text("إدارة الصلاحيات والربط:", reply_markup=InlineKeyboardMarkup(rows))

        elif action == "toggle_permission":
            if not is_admin(user_id):
                await query.answer("خاص بالمدير", show_alert=True)
            else:
                uid_str = parts[1]
                allowed_list = all_data.get("self_edit_allowed_ids", [])
                # دعم تخزين كأرقام أو سلاسل
                if uid_str in map(str, allowed_list):
                    # أزل
                    allowed_list = [x for x in allowed_list if str(x) != uid_str]
                else:
                    allowed_list.append(int(uid_str))
                all_data["self_edit_allowed_ids"] = allowed_list
                save_app_state()
                await query.edit_message_text("✅ تم تحديث الصلاحية.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_perm_menu")]]))

        elif action == "unlink_user":
            if not is_admin(user_id):
                await query.answer("خاص بالمدير", show_alert=True)
            else:
                uid_str = parts[1]
                name = all_data.get("user_links", {}).pop(uid_str, None)
                # إزالة أيضاً من قائمة المسموحين
                all_data["self_edit_allowed_ids"] = [x for x in all_data.get("self_edit_allowed_ids", []) if str(x) != uid_str]
                save_app_state()
                msg = f"✅ تم إلغاء الربط للمستخدم {uid_str} ({name})." if name else "لم يتم العثور على هذا الربط."
                await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_perm_menu")]]))

        elif action == "show_linkme_help":
            msg = (
                "لربط حسابك باسمك في النظام:\n\n"
                "1) أرسل الأمر /linkme\n"
                "2) اختر اسمك من القائمة\n"
                "3) اطلب من المدير منحك صلاحية 'تعديل وقتي'\n\n"
                "بعدها يمكنك استخدام خيار '✏️ تعديل وقتي' لتعديل أوقاتك (ضمن حدود الأمان)."
            )
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]))

        elif action == "noop":
            # لا شيء
            pass

        # --- تعديل الوقت الذاتي ---
        elif action == "self_edit_menu":
            linked_name = get_linked_name(user_id)
            if not linked_name:
                kb = [[InlineKeyboardButton("🔗 كيف أربط؟", callback_data="show_linkme_help")], [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
                await query.edit_message_text("⚠️ لم تقم بربط حسابك باسمك بعد.", reply_markup=InlineKeyboardMarkup(kb))
            elif not has_self_edit_permission(user_id):
                kb = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
                await query.edit_message_text("⚠️ ليس لديك صلاحية تعديل وقتك. يرجى التواصل مع المدير.", reply_markup=InlineKeyboardMarkup(kb))
            else:
                keyboard = [[InlineKeyboardButton(work, callback_data=f"self_edit_select_work:{linked_name}:{work}")] for work in WORK_TYPES]
                keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
                await query.edit_message_text(f"مرحباً {linked_name}. اختر نوع العمل لتعديل الوقت:", reply_markup=InlineKeyboardMarkup(keyboard))

        elif action == "self_edit_select_work":
            linked_name, work = parts[1], parts[2]
            if linked_name != get_linked_name(user_id):
                await query.answer("غير مسموح", show_alert=True)
            elif linked_name in active_timers:
                await query.edit_message_text("⚠️ لا يمكنك تعديل الوقت أثناء تشغيل عدادك. أوقف العداد أولاً.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="self_edit_menu")]]))
            else:
                deltas = [-30, -15, -5, 5, 15, 30]
                keyboard = [
                    [InlineKeyboardButton(("➖" if d < 0 else "➕") + f" {abs(d)} دقيقة", callback_data=f"self_apply_delta:{linked_name}:{work}:{d}") for d in deltas[i:i+3]]
                    for i in (0, 3)
                ]
                keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="self_edit_menu")])
                current = all_data["users"][linked_name][work]
                await query.edit_message_text(
                    f"الوقت الحالي لـ {linked_name} / {work}: {current} دقيقة. اختر مقدار التعديل:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

        elif action == "self_apply_delta":
            linked_name, work, delta_str = parts[1], parts[2], parts[3]
            if linked_name != get_linked_name(user_id) or not has_self_edit_permission(user_id):
                await query.answer("غير مسموح", show_alert=True)
            elif linked_name in active_timers:
                await query.edit_message_text("⚠️ لا يمكنك تعديل الوقت أثناء تشغيل عدادك. أوقف العداد أولاً.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="self_edit_menu")]]))
            else:
                delta = int(delta_str)
                before = all_data["users"][linked_name][work]
                after = max(0, before + delta)
                all_data["users"][linked_name][work] = after
                save_app_state()
                keyboard = [
                    [InlineKeyboardButton("↩️ تعديل آخر", callback_data=f"self_edit_select_work:{linked_name}:{work}")],
                    [InlineKeyboardButton("🔙 رجوع", callback_data="self_edit_menu")]
                ]
                await query.edit_message_text(
                    f"✅ تم تعديل الوقت. {linked_name} / {work}: {before} → {after} دقيقة.",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

        # --- ربط الحساب بالاسم ---
        elif action == "link_name":
            chosen_name = parts[1]
            if chosen_name not in USER_NAMES:
                await query.answer("اسم غير معروف", show_alert=True)
            else:
                # تأكد من أن الاسم موجود في users
                all_data["users"].setdefault(chosen_name, {work_type: 0 for work_type in WORK_TYPES})
                # إزالة أي ربط سابق لنفس الاسم
                prev_uid = None
                for uid_str, name in list(all_data.get("user_links", {}).items()):
                    if name == chosen_name:
                        prev_uid = uid_str
                        all_data["user_links"].pop(uid_str, None)
                        # إزالة من المسموحين أيضاً
                        all_data["self_edit_allowed_ids"] = [x for x in all_data.get("self_edit_allowed_ids", []) if str(x) != uid_str]
                # اربط المستخدم الحالي
                all_data.setdefault("user_links", {})[str(user_id)] = chosen_name
                save_app_state()
                note = f" (تم إلغاء ربط المستخدم {prev_uid} الذي كان مرتبطاً بهذا الاسم)" if prev_uid else ""
                kb = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
                await query.edit_message_text(f"✅ تم ربط حسابك بالاسم '{chosen_name}'.{note}", reply_markup=InlineKeyboardMarkup(kb))

        # --- المنطقة الترفيهية ---
        elif action == "fun_zone":
            linked_name = get_linked_name(user_id)
            welcome_msg = get_personalized_response(linked_name) if linked_name else "🎪 أهلاً بك في المنطقة الترفيهية!"
            
            keyboard = [
                [InlineKeyboardButton("🏆 مين بطل اليوم؟", callback_data="daily_hero")],
                [InlineKeyboardButton("😂 نكتة عشوائية", callback_data="random_joke")],
                [InlineKeyboardButton("💪 تحفيز للعمل", callback_data="motivational_quote")],
                [InlineKeyboardButton("🔥 هجوم ودي", callback_data="friendly_roast")],
                [InlineKeyboardButton("🌟 مجاملة لطيفة", callback_data="nice_compliment")],
                [InlineKeyboardButton("🧠 حكمة اليوم", callback_data="daily_wisdom")],
                [InlineKeyboardButton("🎯 تحدي العمل", callback_data="work_challenge")],
                [InlineKeyboardButton("🎭 وضع المشاغبة", callback_data="naughty_mode")],
                [InlineKeyboardButton("📈 إحصائياتي المرحة", callback_data="fun_stats")],
                [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]
            ]
            await query.edit_message_text(f"{welcome_msg}\n\n� اختر شنو تريد:", reply_markup=InlineKeyboardMarkup(keyboard))

        elif action == "random_joke":
            # تأثير الكتابة قبل النكتة
            await send_typing_animation(context, query.message.chat_id, 2)
            joke = random.choice(JOKES_DATABASE)
            keyboard = [
                [InlineKeyboardButton("😂 نكتة ثانية!", callback_data="random_joke")],
                [InlineKeyboardButton("🔙 رجوع للمنطقة الترفيهية", callback_data="fun_zone")]
            ]
            await query.edit_message_text(f"😄 {joke}", reply_markup=InlineKeyboardMarkup(keyboard))

        elif action == "motivational_quote":
            await send_typing_animation(context, query.message.chat_id, 1.5)
            quote = random.choice(MOTIVATIONAL_QUOTES)
            keyboard = [
                [InlineKeyboardButton("💪 تحفيز آخر!", callback_data="motivational_quote")],
                [InlineKeyboardButton("🔙 رجوع للمنطقة الترفيهية", callback_data="fun_zone")]
            ]
            await query.edit_message_text(f"🔥 {quote}", reply_markup=InlineKeyboardMarkup(keyboard))

        elif action == "friendly_roast":
            await send_typing_animation(context, query.message.chat_id, 2)
            roast = random.choice(ROASTS)
            keyboard = [
                [InlineKeyboardButton("🔥 هجوم آخر!", callback_data="friendly_roast")],
                [InlineKeyboardButton("🌟 مجاملة عشان أصالح!", callback_data="nice_compliment")],
                [InlineKeyboardButton("🔙 رجوع للمنطقة الترفيهية", callback_data="fun_zone")]
            ]
            await query.edit_message_text(f"🔥😈 {roast}\n\n(مزحة ودية! ❤️)", reply_markup=InlineKeyboardMarkup(keyboard))

        elif action == "nice_compliment":
            await send_typing_animation(context, query.message.chat_id, 1)
            compliment = random.choice(COMPLIMENTS)
            keyboard = [
                [InlineKeyboardButton("🌟 مجاملة ثانية!", callback_data="nice_compliment")],
                [InlineKeyboardButton("🔥 هجوم ودي!", callback_data="friendly_roast")],
                [InlineKeyboardButton("🔙 رجوع للمنطقة الترفيهية", callback_data="fun_zone")]
            ]
            await query.edit_message_text(f"✨ {compliment}", reply_markup=InlineKeyboardMarkup(keyboard))

        elif action == "daily_wisdom":
            await send_typing_animation(context, query.message.chat_id, 2)
            wisdom = random.choice(WISDOM_QUOTES)
            keyboard = [
                [InlineKeyboardButton("🧠 حكمة أخرى!", callback_data="daily_wisdom")],
                [InlineKeyboardButton("🔙 رجوع للمنطقة الترفيهية", callback_data="fun_zone")]
            ]
            await query.edit_message_text(f"🎓 {wisdom}", reply_markup=InlineKeyboardMarkup(keyboard))

        elif action == "work_challenge":
            challenges = [
                "تحدي اليوم: اشتغل لمدة 25 دقيقة متواصلة بدون انقطاع! ⏱️🎯",
                "تحدي الإنتاجية: خلص 3 مهام صغيرة في الساعة القادمة! 📝✅",
                "تحدي التركيز: شغل موسيقى هادئة واشتغل لمدة 45 دقيقة! 🎵🧘",
                "تحدي الطموح: حدد هدف واحد كبير لهذا الأسبوع! 🎯📅",
                "تحدي الصبر: اشتغل بدون تفحص الهاتف لمدة ساعة! 📱❌",
                "تحدي الإبداع: فكر في طريقة جديدة لتحسين شغلك! 💡✨"
            ]
            challenge = random.choice(challenges)
            keyboard = [
                [InlineKeyboardButton("🎯 تحدي آخر!", callback_data="work_challenge")],
                [InlineKeyboardButton("💪 قبلت التحدي!", callback_data="challenge_accepted")],
                [InlineKeyboardButton("🔙 رجوع للمنطقة الترفيهية", callback_data="fun_zone")]
            ]
            await query.edit_message_text(f"🔥 {challenge}", reply_markup=InlineKeyboardMarkup(keyboard))

        elif action == "challenge_accepted":
            responses = [
                "ممتاز! هذا الموقف اللي نحبه! 🔥💪",
                "تسلم! شد حيلك وحقق الهدف! 🎯⚡",
                "احترافي! خلينا نشوف الإنجاز! 🚀",
                "هذا الكلام! روح اثبت قوتك! 💪🔥",
                "عاشت الهمة العالية! يلا إنجاز! ⭐"
            ]
            response = random.choice(responses)
            keyboard = [[InlineKeyboardButton("🔙 رجوع للمنطقة الترفيهية", callback_data="fun_zone")]]
            await query.edit_message_text(response, reply_markup=InlineKeyboardMarkup(keyboard))

        elif action == "daily_hero":
            hero_name = get_daily_hero()
            hero_msg = get_hero_message(hero_name)
            
            # إضافة تفاصيل أكثر للبطل
            linked_name = get_linked_name(user_id)
            if linked_name == hero_name:
                hero_msg += f"\n\n🎉 مبروك {linked_name}! انت بطل اليوم! 🏆"
                hero_msg += "\nتستاهل معاملة VIP اليوم! ✨"
            else:
                hero_msg += f"\n\n📢 يلا كلكم هنئوا {hero_name}!"
                
            keyboard = [
                [InlineKeyboardButton("👏 تهنئة البطل", callback_data=f"congratulate_hero:{hero_name}")],
                [InlineKeyboardButton("🔄 بطل جديد بكرة", callback_data="tomorrow_hero")],
                [InlineKeyboardButton("🔙 رجوع للمنطقة الترفيهية", callback_data="fun_zone")]
            ]
            await query.edit_message_text(hero_msg, reply_markup=InlineKeyboardMarkup(keyboard))
            
        elif action == "congratulate_hero":
            hero_name = parts[1] if len(parts) > 1 else get_daily_hero()
            linked_name = get_linked_name(user_id)
            
            congrat_messages = [
                f"🎊 {linked_name} هنأ {hero_name}! عاشت الأيادي!",
                f"👏 {linked_name} يقول: مبروك {hero_name}! تستاهل!",
                f"🏆 {linked_name} معجب بإنجازات {hero_name}!",
                f"⭐ {linked_name} يرفع القبعة لـ {hero_name}!"
            ]
            
            message = random.choice(congrat_messages)
            keyboard = [[InlineKeyboardButton("🔙 رجوع للمنطقة الترفيهية", callback_data="fun_zone")]]
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
            
        elif action == "naughty_mode":
            linked_name = get_linked_name(user_id)
            
            if not linked_name:
                msg = "⚠️ ربط حسابك أولاً عشان أعرف مع مين أحجي!\nاستخدم /linkme"
            elif linked_name in NAUGHTY_NAMES:
                roasts = NAUGHTY_RESPONSES[linked_name]
                msg = f"😈 وضع المشاغبة مفعل لـ {linked_name}!\n\n"
                msg += random.choice(roasts)
                msg += f"\n\n🤪 هاي عينة من اللي ينتظرك كل ما تيجي هنا!"
            else:
                msg = f"😇 {linked_name} انت من الطيبين!\n"
                msg += "وضع المشاغبة مخصص بس للمشاكسين... انت ما تستاهل! 😄"
                
            keyboard = [[InlineKeyboardButton("🔙 رجوع للمنطقة الترفيهية", callback_data="fun_zone")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

        elif action == "fun_stats":
            linked_name = get_linked_name(user_id)
            if linked_name:
                user_times = all_data.get("users", {}).get(linked_name, {})
                total_minutes = sum(user_times.values())
                total_hours = total_minutes / 60
                
                # إحصائيات مرحة
                coffee_cups = int(total_hours * 1.5)  # كوب قهوة كل 40 دقيقة
                pizza_slices = int(total_hours * 0.3)  # شريحة بيتزا كل 3 ساعات
                power_level = min(100, int(total_hours * 2))  # مستوى القوة
                
                fun_titles = [
                    "المبتدئ المجتهد", "العامل النشيط", "المحترف الطموح", 
                    "خبير الإنتاجية", "أسطورة العمل", "إمبراطور الإنجاز"
                ]
                title_index = min(len(fun_titles)-1, int(total_hours // 10))
                title = fun_titles[title_index]
                
                # إضافة معلومات البطل اليومي
                hero_status = ""
                if linked_name == get_daily_hero():
                    hero_status = "🏆 بطل اليوم! 🏆\n"
                
                stats_msg = f"📊 إحصائيات {linked_name} المرحة:\n\n{hero_status}"
                stats_msg += f"🏆 اللقب: {title}\n"
                stats_msg += f"⚡ مستوى القوة: {power_level}%\n"
                stats_msg += f"☕ أكواب القهوة المستهلكة: {coffee_cups}\n"
                stats_msg += f"🍕 شرائح البيتزا المكتسبة: {pizza_slices}\n"
                stats_msg += f"⏰ ساعات العمل الإجمالية: {total_hours:.1f}\n"
                stats_msg += f"🎯 نقاط الإنتاجية: {total_minutes * 10}\n"
                
                # إضافة إحصائية المشاغبة
                if linked_name in NAUGHTY_NAMES:
                    stats_msg += f"😈 مستوى المشاغبة: عالي جداً! 🔥\n"
                
                if total_hours < 5:
                    stats_msg += "\n💡 نصيحة: اشتغل أكثر عشان تطلع إحصائيات أروع!"
                elif total_hours < 20:
                    stats_msg += "\n🔥 ممتاز! انت في الطريق الصحيح للاحترافية!"
                else:
                    stats_msg += "\n👑 أنت أسطورة حقيقية في العمل! احترام!"
                    
            else:
                stats_msg = "⚠️ ربط حسابك أولاً عشان تشوف إحصائياتك المرحة!\nاستخدم /linkme"
            
            keyboard = [[InlineKeyboardButton("🔙 رجوع للمنطقة الترفيهية", callback_data="fun_zone")]]
            await query.edit_message_text(stats_msg, reply_markup=InlineKeyboardMarkup(keyboard))

        # --- إدارة الطباعة ---
        elif action == "print_management":
            stats = get_print_stats()
            message = f"🖨️ *نظام إدارة الطباعة*\n\n"
            message += f"📊 *الإحصائيات السريعة:*\n"
            message += f"📋 إجمالي المهام: {stats['total']}\n"
            message += f"⏳ في الانتظار: {stats['pending']}\n"
            message += f"🔄 جاري العمل: {stats['in_progress']}\n"
            message += f"✅ مكتملة: {stats['completed']}\n"
            message += f"❌ ملغية: {stats['cancelled']}\n"
            
            keyboard = [
                [InlineKeyboardButton("📋 المهام الحالية", callback_data="print_view_pending")],
                [InlineKeyboardButton("🔄 المهام الجارية", callback_data="print_view_in_progress")],
                [InlineKeyboardButton("✅ المهام المكتملة", callback_data="print_view_completed")],
                [InlineKeyboardButton("➕ إضافة مهمة يدوياً", callback_data="print_add_manual")],
                [InlineKeyboardButton("⚙️ إعدادات النظام", callback_data="print_settings")],
                [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]
            ]
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        elif action == "print_view_pending":
            pending_tasks = get_tasks_by_status("pending")
            if not pending_tasks:
                message = "📋 لا توجد مهام في الانتظار حالياً."
                keyboard = [[InlineKeyboardButton("🔙 رجوع لإدارة الطباعة", callback_data="print_management")]]
            else:
                message = "📋 *المهام في الانتظار:*\n\n"
                keyboard = []
                for task_id, task in list(pending_tasks.items())[:10]:  # أول 10 مهام
                    message += f"• {format_task_info(task)}\n"
                    keyboard.append([
                        InlineKeyboardButton(f"▶️ بدء #{task['number']}", callback_data=f"print_start:{task_id}"),
                        InlineKeyboardButton(f"👁️ عرض #{task['number']}", callback_data=f"print_view:{task_id}")
                    ])
                keyboard.append([InlineKeyboardButton("🔙 رجوع لإدارة الطباعة", callback_data="print_management")])
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        elif action == "print_view_in_progress":
            progress_tasks = get_tasks_by_status("in_progress")
            if not progress_tasks:
                message = "🔄 لا توجد مهام جاري العمل عليها حالياً."
                keyboard = [[InlineKeyboardButton("🔙 رجوع لإدارة الطباعة", callback_data="print_management")]]
            else:
                message = "🔄 *المهام الجاري العمل عليها:*\n\n"
                keyboard = []
                for task_id, task in progress_tasks.items():
                    message += f"• {format_task_info(task)}\n"
                    keyboard.append([
                        InlineKeyboardButton(f"✅ إنهاء #{task['number']}", callback_data=f"print_complete:{task_id}"),
                        InlineKeyboardButton(f"👁️ عرض #{task['number']}", callback_data=f"print_view:{task_id}")
                    ])
                keyboard.append([InlineKeyboardButton("🔙 رجوع لإدارة الطباعة", callback_data="print_management")])
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        elif action == "print_view_completed":
            completed_tasks = get_tasks_by_status("completed")
            if not completed_tasks:
                message = "✅ لا توجد مهام مكتملة حالياً."
                keyboard = [[InlineKeyboardButton("🔙 رجوع لإدارة الطباعة", callback_data="print_management")]]
            else:
                message = "✅ *المهام المكتملة:*\n\n"
                keyboard = []
                for task_id, task in list(completed_tasks.items())[-10:]:  # آخر 10 مهام
                    message += f"• {format_task_info(task)}\n"
                    keyboard.append([InlineKeyboardButton(f"👁️ عرض #{task['number']}", callback_data=f"print_view:{task_id}")])
                keyboard.append([InlineKeyboardButton("🔙 رجوع لإدارة الطباعة", callback_data="print_management")])
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        elif action == "print_view":
            task_id = parts[1]
            if task_id not in all_data.get("print_tasks", {}):
                message = "❌ المهمة غير موجودة."
                keyboard = [[InlineKeyboardButton("🔙 رجوع لإدارة الطباعة", callback_data="print_management")]]
            else:
                task = all_data["print_tasks"][task_id]
                message = f"📄 *تفاصيل المهمة:*\n\n{format_task_info(task, show_content=True)}"
                
                keyboard = []
                
                # أزرار حالة المهمة
                if task["status"] == "pending":
                    keyboard.append([InlineKeyboardButton("▶️ بدء العمل", callback_data=f"print_start:{task_id}")])
                elif task["status"] == "in_progress":
                    keyboard.append([InlineKeyboardButton("✅ إنهاء المهمة", callback_data=f"print_complete:{task_id}")])
                
                if task["status"] in ["pending", "in_progress"]:
                    keyboard.append([InlineKeyboardButton("❌ إلغاء المهمة", callback_data=f"print_cancel:{task_id}")])
                
                # زر تحميل الملف الأصلي (إذا كان موجود)
                if task.get('has_file'):
                    keyboard.append([InlineKeyboardButton("� تحميل الملف الأصلي", callback_data=f"print_download:{task_id}")])
                
                keyboard.append([InlineKeyboardButton("�🔙 رجوع لإدارة الطباعة", callback_data="print_management")])
            
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        elif action == "print_download":
            task_id = parts[1]
            
            # إرسال الملف الأصلي
            success, message = await send_original_file(context, query.message.chat_id, task_id)
            
            if success:
                await query.answer("✅ تم إرسال الملف!", show_alert=True)
            else:
                await query.answer(f"❌ {message}", show_alert=True)

        elif action == "print_start":
            task_id = parts[1]
            linked_name = get_linked_name(user_id)
            worker_name = linked_name or f"مستخدم_{user_id}"
            
            changed_task = update_task_status(task_id, "in_progress", assigned_to=worker_name)
            if changed_task:
                task = changed_task
                message = f"✅ تم بدء العمل على المهمة #{task['number']}!\n\n{format_task_info(task)}"
            else:
                message = "❌ فشل في بدء المهمة."
            
            keyboard = [[InlineKeyboardButton("🔙 رجوع لإدارة الطباعة", callback_data="print_management")]]
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        elif action == "print_complete":
            task_id = parts[1]
            changed_task = update_task_status(task_id, "completed")
            if changed_task:
                task = changed_task
                message = f"🎉 تم إنهاء المهمة #{task['number']} بنجاح!\n\n{format_task_info(task)}"
            else:
                message = "❌ فشل في إنهاء المهمة."
            
            keyboard = [[InlineKeyboardButton("🔙 رجوع لإدارة الطباعة", callback_data="print_management")]]
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        elif action == "print_cancel":
            task_id = parts[1]
            changed_task = update_task_status(task_id, "cancelled")
            if changed_task:
                # المهمة تم حذفها من النظام؛ نستخدم بيانات المهمة المحذوفة لعرض ملخص
                task = changed_task
                message = f"❌ تم إلغاء وحذف المهمة #{task['number']} من النظام.\n\n{format_task_info(task)}"
            else:
                message = "❌ فشل في إلغاء المهمة."
            
            keyboard = [[InlineKeyboardButton("🔙 رجوع لإدارة الطباعة", callback_data="print_management")]]
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        elif action == "print_add_manual":
            message = (
                "➕ *إضافة مهمة طباعة يدوياً*\n\n"
                "أرسل نص المهمة الآن، أو أرسل ملف نصي.\n"
                "يمكنك أيضاً استخدام الأمر:\n"
                "`/addtask النص هنا`"
            )
            keyboard = [[InlineKeyboardButton("🔙 رجوع لإدارة الطباعة", callback_data="print_management")]]
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        elif action == "print_settings":
            settings = all_data.get("print_settings", {})
            auto_receive = settings.get("auto_receive_from_channel", True)
            default_priority = settings.get("default_priority", "medium")
            
            message = f"⚙️ *إعدادات نظام الطباعة*\n\n"
            message += f"📺 استقبال تلقائي من القناة: {'✅ مفعل' if auto_receive else '❌ معطل'}\n"
            message += f"📋 الأولوية الافتراضية: {PRINT_PRIORITIES.get(default_priority, 'غير محدد')}\n"
            message += f"📊 عداد المهام: {settings.get('task_counter', 0)}\n"
            
            keyboard = [
                [InlineKeyboardButton(
                    f"{'❌ تعطيل' if auto_receive else '✅ تفعيل'} الاستقبال التلقائي",
                    callback_data="print_toggle_auto_receive"
                )],
                [InlineKeyboardButton("🔄 تغيير الأولوية الافتراضية", callback_data="print_change_priority")],
                [InlineKeyboardButton("🗑️ حذف جميع المهام المكتملة", callback_data="print_clear_completed")],
                [InlineKeyboardButton("🔙 رجوع لإدارة الطباعة", callback_data="print_management")]
            ]
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

        elif action == "print_toggle_auto_receive":
            current = all_data.get("print_settings", {}).get("auto_receive_from_channel", True)
            all_data["print_settings"]["auto_receive_from_channel"] = not current
            save_app_state()
            
            status = "تم تفعيل" if not current else "تم تعطيل"
            if CHANNEL_ID is not None:
                chan_desc = f"chat_id={CHANNEL_ID}"
            elif CHANNEL_USERNAME:
                chan_desc = f"@{CHANNEL_USERNAME}"
            else:
                chan_desc = "(غير محددة)"
            message = f"✅ {status} الاستقبال التلقائي من قناة '{chan_desc}'."
            keyboard = [[InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="print_settings")]]
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

        elif action == "print_change_priority":
            message = "🔄 اختر الأولوية الافتراضية للمهام الجديدة:"
            keyboard = [
                [InlineKeyboardButton("🟢 عادية", callback_data="print_set_priority:low")],
                [InlineKeyboardButton("🟡 متوسطة", callback_data="print_set_priority:medium")],
                [InlineKeyboardButton("🔴 عاجلة", callback_data="print_set_priority:high")],
                [InlineKeyboardButton("🚨 طارئة", callback_data="print_set_priority:urgent")],
                [InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="print_settings")]
            ]
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

        elif action == "print_set_priority":
            priority = parts[1]
            all_data["print_settings"]["default_priority"] = priority
            save_app_state()
            
            message = f"✅ تم تعيين الأولوية الافتراضية إلى: {PRINT_PRIORITIES.get(priority, 'غير محدد')}"
            keyboard = [[InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="print_settings")]]
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

        elif action == "print_clear_completed":
            completed_tasks = get_tasks_by_status("completed")
            count = len(completed_tasks)
            
            if count == 0:
                message = "✅ لا توجد مهام مكتملة لحذفها."
            else:
                # حذف المهام المكتملة
                for task_id in completed_tasks.keys():
                    del all_data["print_tasks"][task_id]
                save_app_state()
                message = f"🗑️ تم حذف {count} مهمة مكتملة."
            
            keyboard = [[InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="print_settings")]]
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

async def linkme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /linkme لربط حساب التلغرام باسم المستخدم في القائمة."""
    keyboard = [[InlineKeyboardButton(name, callback_data=f"link_name:{name}")] for name in USER_NAMES]
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
    await update.message.reply_text("اختر اسمك للربط:", reply_markup=InlineKeyboardMarkup(keyboard))

async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /joke لإرسال نكتة عشوائية"""
    await send_typing_animation(context, update.effective_chat.id, 2)
    joke = random.choice(JOKES_DATABASE)
    await update.message.reply_text(f"😄 {joke}")

async def motivate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /motivate لإرسال رسالة تحفيزية"""
    await send_typing_animation(context, update.effective_chat.id, 1.5)
    quote = random.choice(MOTIVATIONAL_QUOTES)
    await update.message.reply_text(f"🔥 {quote}")

async def roast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /roast للهجوم الودي"""
    await send_typing_animation(context, update.effective_chat.id, 2)
    roast = random.choice(ROASTS)
    await update.message.reply_text(f"🔥😈 {roast}\n\n(مزحة ودية! ❤️)")

async def compliment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /compliment للمجاملات"""
    await send_typing_animation(context, update.effective_chat.id, 1)
    compliment = random.choice(COMPLIMENTS)
    await update.message.reply_text(f"✨ {compliment}")

async def wisdom_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /wisdom للحكم والأقوال"""
    await send_typing_animation(context, update.effective_chat.id, 2)
    wisdom = random.choice(WISDOM_QUOTES)
    await update.message.reply_text(f"🎓 {wisdom}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /stats للإحصائيات المرحة"""
    user_id = update.effective_user.id
    linked_name = get_linked_name(user_id)
    
    if linked_name:
        user_times = all_data.get("users", {}).get(linked_name, {})
        total_minutes = sum(user_times.values())
        total_hours = total_minutes / 60
        
        # إحصائيات مرحة
        coffee_cups = int(total_hours * 1.5)
        pizza_slices = int(total_hours * 0.3)
        power_level = min(100, int(total_hours * 2))
        
        fun_titles = [
            "المبتدئ المجتهد", "العامل النشيط", "المحترف الطموح", 
            "خبير الإنتاجية", "أسطورة العمل", "إمبراطور الإنجاز"
        ]
        title_index = min(len(fun_titles)-1, int(total_hours // 10))
        title = fun_titles[title_index]
        
        stats_msg = f"📊 إحصائيات {linked_name} المرحة:\n\n"
        stats_msg += f"🏆 اللقب: {title}\n"
        stats_msg += f"⚡ مستوى القوة: {power_level}%\n"
        stats_msg += f"☕ أكواب القهوة المستهلكة: {coffee_cups}\n"
        stats_msg += f"🍕 شرائح البيتزا المكتسبة: {pizza_slices}\n"
        stats_msg += f"⏰ ساعات العمل الإجمالية: {total_hours:.1f}\n"
        stats_msg += f"🎯 نقاط الإنتاجية: {total_minutes * 10}\n\n"
        
        if total_hours < 5:
            stats_msg += "💡 نصيحة: اشتغل أكثر عشان تطلع إحصائيات أروع!"
        elif total_hours < 20:
            stats_msg += "🔥 ممتاز! انت في الطريق الصحيح للاحترافية!"
        else:
            stats_msg += "👑 أنت أسطورة حقيقية في العمل! احترام!"
            
    else:
        stats_msg = "⚠️ ربط حسابك أولاً عشان تشوف إحصائياتك المرحة!\nاستخدم /linkme"
    
    await update.message.reply_text(stats_msg)

async def addtask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /addtask لإضافة مهمة طباعة يدوياً"""
    if not context.args:
        await update.message.reply_text(
            "❌ يرجى كتابة نص المهمة بعد الأمر.\n"
            "مثال: `/addtask طباعة المواد الدراسية للفصل الأول`"
        )
        return
    
    content = " ".join(context.args)
    task_id = create_print_task(
        content=content,
        filename=f"مهمة_يدوية_{datetime.now().strftime('%Y%m%d_%H%M')}",
        priority="medium",
        source="manual"
        # لا file_data - هذه مهمة نصية فقط
    )
    
    task = all_data["print_tasks"][task_id]
    await update.message.reply_text(
        f"✅ تم إنشاء مهمة طباعة جديدة!\n\n"
        f"📋 المهمة #{task['number']}\n"
        f"� مهمة نصية\n"
        f"🔤 المحتوى: {content[:100]}{'...' if len(content) > 100 else ''}\n\n"
        f"يمكنك إدارة المهمة من قسم 🖨️ إدارة الطباعة"
    )

async def printstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /printstats لعرض إحصائيات الطباعة"""
    stats = get_print_stats()
    
    message = f"📊 *إحصائيات نظام الطباعة*\n\n"
    message += f"📋 إجمالي المهام: {stats['total']}\n"
    message += f"⏳ في الانتظار: {stats['pending']}\n"
    message += f"🔄 جاري العمل: {stats['in_progress']}\n"
    message += f"✅ مكتملة: {stats['completed']}\n"
    message += f"❌ ملغية: {stats['cancelled']}\n\n"
    
    if stats['total'] > 0:
        completion_rate = (stats['completed'] / stats['total']) * 100
        message += f"📈 معدل الإنجاز: {completion_rate:.1f}%\n"
    
    # إحصائيات إضافية
    tasks = all_data.get("print_tasks", {})
    if tasks:
        today = datetime.now().date()
        today_tasks = [t for t in tasks.values() 
                      if datetime.fromisoformat(t["created_at"]).date() == today]
        message += f"📅 مهام اليوم: {len(today_tasks)}\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def hero_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /hero لعرض بطل اليوم"""
    hero_name = get_daily_hero()
    hero_msg = get_hero_message(hero_name)
    
    user_id = update.effective_user.id
    linked_name = get_linked_name(user_id)
    
    if linked_name == hero_name:
        hero_msg += f"\n\n🎉 مبروك {linked_name}! انت بطل اليوم! 🏆"
        hero_msg += "\nتستاهل معاملة VIP اليوم! ✨"
    else:
        hero_msg += f"\n\n📢 يلا كلكم هنئوا {hero_name}!"
    
    await update.message.reply_text(hero_msg)

async def handle_document_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الملفات المرسلة للبوت مباشرة أو من القناة - حفظ كامل للملف"""
    try:
        # DEBUG: طباعة معلومات الدردشة لمعرفة المعرف الصحيح
        print(f"📩 DEBUG: Received file from chat_id={update.effective_chat.id}, title='{update.effective_chat.title}', username='{update.effective_chat.username}'")
        
        # التحقق من المصدر - قناة أم مراسلة مباشرة
        chat_matches_channel = False
        try:
            if CHANNEL_ID is not None and update.effective_chat.id is not None:
                chat_matches_channel = (update.effective_chat.id == CHANNEL_ID)
            elif CHANNEL_USERNAME:
                chat_matches_channel = (str(update.effective_chat.username or '').lower() == CHANNEL_USERNAME.lower())
        except Exception:
            chat_matches_channel = False

        is_from_channel = chat_matches_channel and all_data.get("print_settings", {}).get("auto_receive_from_channel", True)
        
        # تحميل الملف
        file = await context.bot.get_file(update.message.document.file_id)
        file_content = await file.download_as_bytearray()
        
        # معلومات الملف
        filename = update.message.document.file_name or ("ملف_من_القناة" if is_from_channel else "ملف_مرفوع")
        file_size = len(file_content)
        file_type = get_file_type_from_name(filename)
        
        # تشفير الملف لحفظه في JSON
        file_base64 = base64.b64encode(file_content).decode('utf-8')
        
        # بيانات وصفية للملف
        file_metadata = {
            "original_name": filename,
            "size_bytes": file_size,
            "size_mb": round(file_size / (1024 * 1024), 2),
            "mime_type": update.message.document.mime_type,
            "file_id": update.message.document.file_id,
            "uploaded_at": datetime.now().isoformat(),
            "source_chat": update.effective_chat.username or str(update.effective_chat.id)
        }
        
        # محاولة استخراج النص (اختياري)
        extracted_text = ""
        extraction_error = None
        
        if file_type in ["pdf", "image", "docx", "text"]:
            try:
                extracted_text, extraction_error = extract_text_from_file(file_content, filename)
                if extracted_text is None:
                    extracted_text = ""
            except Exception as e:
                extraction_error = str(e)
                extracted_text = ""
        
        # تحديد المحتوى - النص المستخرج أو وصف الملف
        if extracted_text.strip():
            content = extracted_text
        else:
            content = f"ملف {file_type}: {filename}\nالحجم: {file_metadata['size_mb']} MB"
            if extraction_error:
                content += f"\nملاحظة: لم يتم استخراج النص - {extraction_error}"
        
        # إنشاء مهمة طباعة مع الملف الكامل
        # إذا الملف PDF وكان المرسل شخصياً (مش من القناة)، نفترض أنه يريد أن يرسل الوصف بعده
        source = "channel" if is_from_channel else "upload"
        if file_type == 'pdf' and not is_from_channel:
            # احفظ الملف مؤقتاً بانتظار رسالة وصف من نفس المستخدم
            user_id = update.effective_user.id
            pending_uploads[str(user_id)] = {
                'file_base64': file_base64,
                'filename': filename,
                'file_metadata': file_metadata,
                'priority': all_data["print_settings"]["default_priority"],
                'source': source,
                'extracted_text': extracted_text
            }

            await update.message.reply_text(
                f"📥 استلمت ملف PDF: {filename}\n\n"
                "لو سمحت ارسل وصف المهمة الآن (رسالة نصية).\n"
                "أو ارسل /cancelupload لإلغاء هذه الرفع."
            )

            return

        task_id = create_print_task(
            content=content,
            filename=filename,
            priority=all_data["print_settings"]["default_priority"],
            source=source,
            file_data=file_base64,
            file_metadata=file_metadata
        )

        task = all_data["print_tasks"][task_id]
        file_emoji = get_file_type_emoji(filename)
        
        # إرسال رد مناسب
        if is_from_channel:
            # إشعار للمدير من القناة
            notification = f"📥 *ملف جديد من القناة!*\n\n"
            notification += f"{file_emoji} *المهمة #{task['number']}*\n"
            notification += f"📁 الملف: {filename}\n"
            notification += f"📊 الحجم: {file_metadata['size_mb']} MB\n"
            notification += f"🎯 النوع: {file_type.upper()}\n"
            notification += f"📝 النص المستخرج: {'✅ متوفر' if extracted_text.strip() else '❌ غير متوفر'}\n"
            
            if extracted_text.strip():
                preview = extracted_text[:200] + "..." if len(extracted_text) > 200 else extracted_text
                notification += f"\n📄 معاينة:\n```\n{preview}\n```"
            
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_USER_ID,
                    text=notification,
                    parse_mode='Markdown'
                )
            except Exception as e:
                print(f"فشل إرسال الإشعار للمدير: {e}")
        else:
            # رد للمستخدم الذي أرسل الملف مباشرة
            response = f"{file_emoji} تم استلام الملف وحفظه كاملاً!\n\n"
            response += f"📋 المهمة #{task['number']}\n"
            response += f"📁 {filename}\n"
            response += f"📊 الحجم: {file_metadata['size_mb']} MB\n"
            response += f"🎯 النوع: {file_type.upper()}\n"
            response += f"� تم حفظ الملف الأصلي مع البيانات\n"
            
            if extracted_text.strip():
                response += f"📝 تم استخراج {len(extracted_text)} حرف من النص\n"
            elif extraction_error:
                response += f"⚠️ لم يتم استخراج النص: {extraction_error}\n"
            
            response += f"\nيمكنك إدارة المهمة من قسم 🖨️ إدارة الطباعة"
            
            await update.message.reply_text(response)

    except Exception as e:
        error_msg = f"❌ خطأ في معالجة الملف: {str(e)}"
        # إذا لم يكن مصدر الرسالة هو القناة المُعرفة، رُد على المرسل
        if not chat_matches_channel:
            await update.message.reply_text(error_msg)
        else:
            print(f"خطأ في معالجة ملف القناة: {e}")

async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الصور المرسلة للبوت"""
    try:
        # الحصول على أعلى جودة للصورة
        photo = update.message.photo[-1]
        
        # تحميل الصورة
        file = await context.bot.get_file(photo.file_id)
        file_content = await file.download_as_bytearray()
        
        # معلومات الصورة
        filename = f"صورة_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        file_size = len(file_content)
        
        # تشفير الصورة لحفظها
        file_base64 = base64.b64encode(file_content).decode('utf-8')
        
        # بيانات وصفية
        file_metadata = {
            "original_name": filename,
            "size_bytes": file_size,
            "size_mb": round(file_size / (1024 * 1024), 2),
            "width": photo.width,
            "height": photo.height,
            "file_id": photo.file_id,
            "uploaded_at": datetime.now().isoformat(),
            "source_chat": str(update.effective_chat.id),
            "mime_type": "image/jpeg"
        }
        
        # محاولة استخراج النص من الصورة
        extracted_text = ""
        extraction_error = None
        
        try:
            extracted_text, extraction_error = extract_text_from_image(file_content)
            if extracted_text is None:
                extracted_text = ""
        except Exception as e:
            extraction_error = str(e)
            extracted_text = ""
        
        # تحديد المحتوى
        if extracted_text.strip():
            content = extracted_text
        else:
            content = f"صورة: {filename}\nالأبعاد: {photo.width}x{photo.height}\nالحجم: {file_metadata['size_mb']} MB"
            if extraction_error:
                content += f"\nملاحظة: لم يتم استخراج النص - {extraction_error}"
        
        # إنشاء مهمة طباعة
        task_id = create_print_task(
            content=content,
            filename=filename,
            priority=all_data["print_settings"]["default_priority"],
            source="photo",
            file_data=file_base64,
            file_metadata=file_metadata
        )
        
        task = all_data["print_tasks"][task_id]
        
        response = f"🖼️ تم استلام الصورة وحفظها كاملة!\n\n"
        response += f"📋 المهمة #{task['number']}\n"
        response += f"📁 {filename}\n"
        response += f"📊 الحجم: {file_metadata['size_mb']} MB\n"
        response += f"📏 الأبعاد: {photo.width}×{photo.height}\n"
        response += f"💾 تم حفظ الصورة الأصلية مع البيانات\n"
        
        if extracted_text.strip():
            response += f"📝 تم استخراج {len(extracted_text)} حرف من النص\n"
        elif extraction_error:
            response += f"⚠️ لم يتم استخراج النص: {extraction_error}\n"
        
        response += f"\nيمكنك إدارة المهمة من قسم 🖨️ إدارة الطباعة"
        
        await update.message.reply_text(response)
        
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في معالجة الصورة: {str(e)}")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية العادية لإضافة مهام سريعة"""
    # تجاهل الرسائل القصيرة أو الأوامر
    text = update.message.text
    if not text or text.startswith('/'):
        return

    user_id = str(update.effective_user.id)

    # إذا هناك رفع مؤقت بانتظار وصف لهذه الرفع فالأولوية له: وصف الملف يجب أن يستهلك قبل إنشاء مهمة نصية منفصلة
    if user_id in pending_uploads:
        pending = pending_uploads.pop(user_id)
        description = text.strip()

        # إذا كان مكتوباً قصير جداً، نطلب توضيح
        if len(description) < 3:
            # أعد التخزين وانتظر وصف أطول
            pending_uploads[user_id] = pending
            await update.message.reply_text("❗ الوصف قصير جداً. ارسل وصف أو تفاصيل أطول لو سمحت.")
            return

        # دعم خاص: إذا كان الوصف يحتوي على الكلمة الخاصة 'مهمةة' نعتبرها أولوية عالية
        priority = pending.get('priority', 'medium')
        if 'مهمةة' in description:
            description = description.replace('مهمةة', '').strip()
            priority = 'high'

        # لا نجمع النص المستخرج مع الوصف؛ نضع الوصف كمحتوى المهمة
        # ونحفظ أي نص مستخرج داخل metadata تحت 'extracted_text' ليكون متاحًا لكن غير معروض افتراضياً
        file_meta = dict(pending.get('file_metadata', {}))
        if pending.get('extracted_text'):
            file_meta['extracted_text'] = pending['extracted_text']

        task_id = create_print_task(
            content=description,
            filename=pending['filename'],
            priority=priority,
            source=pending.get('source', 'upload'),
            file_data=pending.get('file_base64'),
            file_metadata=file_meta
        )

        task = all_data['print_tasks'][task_id]
        await update.message.reply_text(
            f"✅ تم إنشاء مهمة طباعة من الملف والوصف!\n\n"
            f"📋 المهمة #{task['number']}\n"
            f"� {task['filename']}\n"
            f"🔤 الوصف: {description[:200]}{'...' if len(description) > 200 else ''}\n\n"
            f"أولوية: {'عالية 🔴' if priority=='high' else 'عادية 🟡'}\n\n"
            f"يمكنك إدارة المهمة من قسم 🖨️ إدارة الطباعة"
        )
        return

    # دعم خاص: إذا احتوت الرسالة على المفتاح الدقيق 'مهمةة' في أي مكان، ننشئ مهمة بأولوية عالية
    trigger = 'مهمةة'
    if trigger in text:
        # استخراج الوصف بعد إزالة الكلمة المفتاحية من النص
        description = text.replace(trigger, '').strip()
        if not description:
            await update.message.reply_text("✳️ استعمل 'مهمةة' متبوعة وصف المهمة. مثال: `مهمةة طباعة كتيب العرض`")
            return

        task_id = create_print_task(
            content=description,
            filename=f"مهمة_سريعة_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            priority='high',
            source='text_message'
        )

        task = all_data['print_tasks'][task_id]
        await update.message.reply_text(
            f"🚨 تم إنشاء مهمة ذات أولوية!\n\n"
            f"📋 المهمة #{task['number']}\n"
            f"� {task['filename']}\n"
            f"🔤 الوصف: {description[:200]}{'...' if len(description) > 200 else ''}\n\n"
            f"استخدم /prioritytasks لعرض المهام ذات الأولوية"
        )
        return

    # إنشاء مهمة من النص المرسل (سلوك افتراضي)
    if len(text) < 10:
        # تجاهل الرسائل القصيرة العشوائية التي ليست أوصاف
        return

    task_id = create_print_task(
        content=text,
        filename=f"مهمة_نصية_{datetime.now().strftime('%H%M%S')}",
        priority="medium",
        source="text_message"
    )

    task = all_data["print_tasks"][task_id]
    await update.message.reply_text(
        f"📝 تم إنشاء مهمة طباعة من النص المرسل!\n\n"
        f"📋 المهمة #{task['number']}\n"
        f"📄 مهمة نصية\n"
        f"🔤 المحتوى: {text[:100]}{'...' if len(text) > 100 else ''}\n\n"
        f"يمكنك إدارة المهمة من قسم 🖨️ إدارة الطباعة"
    )


async def cancel_upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر لإلغاء أي رفع مؤقت ينتظر وصف من المستخدم"""
    user_id = str(update.effective_user.id)
    if user_id in pending_uploads:
        pending_uploads.pop(user_id, None)
        await update.message.reply_text("✅ تم إلغاء الرفع المؤقت.")
    else:
        await update.message.reply_text("لا توجد رفعات مؤقتة لديك الآن.")


async def prioritytasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة المهام ذات الأولوية العالية"""
    tasks = [t for t in all_data.get('print_tasks', {}).values() if t.get('priority') == 'high']
    if not tasks:
        await update.message.reply_text("لا توجد مهام ذات أولوية عالية حالياً.")
        return

    # فرز حسب رقم المهمة
    tasks_sorted = sorted(tasks, key=lambda x: x.get('number', 0))
    message = "🚨 *المهام ذات الأولوية العالية:*\n\n"
    for t in tasks_sorted:
        created = ''
        try:
            created = datetime.fromisoformat(t.get('created_at', '')).strftime('%Y-%m-%d')
        except Exception:
            created = t.get('created_at', '')

        message += f"*#{t.get('number')}* — {t.get('filename')} | {t.get('status')} | {created}\n"
        if t.get('content'):
            preview = t.get('content')[:120] + ('...' if len(t.get('content')) > 120 else '')
            message += f"   📝 {preview}\n"

    await update.message.reply_text(message, parse_mode='Markdown')

# --- دالة رئيسية لتشغيل البوت ---
def main():
    """الدالة الرئيسية لإعداد وتشغيل البوت."""
    print("🤖 Bot is starting...")
    load_app_state()
    
    app = Application.builder().token(TOKEN).build()

    # إضافة جميع معالجات الأوامر
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("linkme", linkme_command))
    app.add_handler(CommandHandler("joke", joke_command))
    app.add_handler(CommandHandler("motivate", motivate_command))
    app.add_handler(CommandHandler("roast", roast_command))
    app.add_handler(CommandHandler("compliment", compliment_command))
    app.add_handler(CommandHandler("wisdom", wisdom_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("addtask", addtask_command))
    app.add_handler(CommandHandler("printstats", printstats_command))
    app.add_handler(CommandHandler("hero", hero_command))
    # أمر لإلغاء رفع مؤقت
    app.add_handler(CommandHandler("cancelupload", cancel_upload_command))
    # أمر لعرض المهام ذات الأولوية
    app.add_handler(CommandHandler("prioritytasks", prioritytasks_command))
    
    # معالجات الرسائل والملفات
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # معالج الأزرار (يجب أن يكون الأخير)
    app.add_handler(CallbackQueryHandler(button_handler))

    # جدولة عملية التنظيف اليومية: حذف المهام المكتملة الأقدم من 7 أيام
    def cleanup_old_completed_tasks_once():
        try:
            now = datetime.now()
            cutoff = now - timedelta(days=7)
            tasks = all_data.get('print_tasks', {})
            to_delete = []
            for tid, task in list(tasks.items()):
                if task.get('status') == 'completed' and task.get('completed_at'):
                    try:
                        completed = datetime.fromisoformat(task['completed_at'])
                        if completed < cutoff:
                            to_delete.append(tid)
                    except Exception:
                        # إذا كان هناك تنسيق زمني خاطئ، احذفه أيضاً
                        to_delete.append(tid)

            if to_delete:
                for tid in to_delete:
                    tasks.pop(tid, None)
                save_app_state()
                print(f"🧹 تم حذف {len(to_delete)} مهمة مكتملة أقدم من 7 أيام للحفاظ على المساحة.")
        except Exception as e:
            print(f"خطأ في عملية التنظيف التلقائي: {e}")

    # إذا لم تتوفر JobQueue (أو لتجنب اعتماده)، نشغل مؤشرًا دائماً في خيط منفصل يقوم بالتنظيف كل 24 ساعة
    def _cleanup_thread_loop():
        # بداية بعد 60 ثانية لإعطاء البوت وقت الإقلاع
        time.sleep(60)
        while True:
            cleanup_old_completed_tasks_once()
            # انتظر 24 ساعة
            time.sleep(24 * 60 * 60)

    t = threading.Thread(target=_cleanup_thread_loop, name='cleanup-thread', daemon=True)
    t.start()

    print("🚀 Bot is now polling for updates...")
    print("📋 Available commands:")
    print("   /start - القائمة الرئيسية")
    print("   /linkme - ربط الحساب")
    print("   /hero - بطل اليوم")
    print("   /joke - نكتة عشوائية")
    print("   /motivate - رسالة تحفيزية") 
    print("   /roast - هجوم ودي")
    print("   /compliment - مجاملة")
    print("   /wisdom - حكمة")
    print("   /stats - إحصائيات مرحة")
    print("   /addtask - إضافة مهمة طباعة")
    print("   /printstats - إحصائيات الطباعة")
    if CHANNEL_ID is not None:
        channel_display = f"chat_id={CHANNEL_ID}"
    elif CHANNEL_USERNAME:
        channel_display = f"@{CHANNEL_USERNAME}"
    else:
        channel_display = "(none)"

    print(f"🖨️ Print management: Monitoring {channel_display}")
    
    app.run_polling()
''

if __name__ == '__main__':
    main()
