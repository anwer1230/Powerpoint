import os
import json
import uuid
import time
import logging
import asyncio
import threading
import queue
import re
import random
import string


def randomize_message(text):
    """إضافة مسافة عشوائية أو رمز غير مرئي لتنويع الرسالة وتفادي اكتشاف التكرار"""
    rnd = random.choice(['', ' ', '  ', '\u200B', '\u200C'])
    return text + rnd
from threading import Lock
from flask import Flask, session, request, render_template, jsonify, redirect
from flask_socketio import SocketIO, emit, join_room, leave_room
from telethon import TelegramClient, events, functions
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError, PhoneCodeInvalidError, PasswordHashInvalidError, FloodWaitError, UserAlreadyParticipantError, InviteHashExpiredError, InviteHashInvalidError
from telethon.sessions import StringSession
import socket

# تكوين السجلات المحسن
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/telegram_monitoring.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# إنشاء التطبيق
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", os.urandom(24))

# إعداد SocketIO
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='threading',
    ping_timeout=30, 
    ping_interval=15,
    logger=False, 
    engineio_logger=False,
    allow_upgrades=True,
    transports=['websocket', 'polling']
)

# إعدادات النظام
SESSIONS_DIR = "/tmp/sessions"
if not os.path.exists(SESSIONS_DIR):
    os.makedirs(SESSIONS_DIR)

# نظام المستخدمين الخمسة المحددين مسبقاً
PREDEFINED_USERS = {
    "user_1": {
        "id": "user_1",
        "name": "المستخدم الأول",
        "icon": "fas fa-user",
        "color": "#007bff"
    },
    "user_2": {
        "id": "user_2", 
        "name": "المستخدم الثاني",
        "icon": "fas fa-user-tie",
        "color": "#28a745"
    },
    "user_3": {
        "id": "user_3",
        "name": "المستخدم الثالث", 
        "icon": "fas fa-user-graduate",
        "color": "#ffc107"
    },
    "user_4": {
        "id": "user_4",
        "name": "المستخدم الرابع",
        "icon": "fas fa-user-cog",
        "color": "#dc3545"
    },
    "user_5": {
        "id": "user_5",
        "name": "المستخدم الخامس",
        "icon": "fas fa-user-astronaut", 
        "color": "#6f42c1"
    }
}

# معالجات الأخطاء الشاملة
@app.errorhandler(404)
def not_found_error(error):
    try:
        return jsonify({"error": "Page not found"}), 404
    except Exception as e:
        logger.error(f"Error in 404 handler: {str(e)}")
        return jsonify({"error": "Page not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    try:
        return render_template('index.html', 
                              settings={}, 
                              connection_status='disconnected',
                              app_title="مركز سرعة انجاز 📚للخدمات الطلابية والاكاديمية"), 500
    except Exception as e:
        logger.error(f"Error in 500 handler: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    try:
        return render_template('index.html', 
                              settings={}, 
                              connection_status='disconnected',
                              app_title="مركز سرعة انجاز 📚للخدمات الطلابية والاكاديمية"), 500
    except Exception as template_error:
        logger.error(f"Error in exception handler: {str(template_error)}")
        return jsonify({"error": "Server error"}), 500

# معالج أخطاء Socket.IO
@socketio.on_error_default
def default_error_handler(e):
    logger.error(f"Socket.IO error: {str(e)}")



USERS = {}
USERS_LOCK = Lock()

# بيانات Telegram API
API_ID = '22043994'
API_HASH = '56f64582b363d367280db96586b97801'

if not API_ID or not API_HASH:
    logger.warning("⚠️ لم يتم إعداد TELEGRAM_API_ID و TELEGRAM_API_HASH - وظائف التليجرام لن تعمل")

# =========================== 
# نظام Queue للتنبيهات المحسن
# ===========================
class AlertQueue:
    """نظام queue متقدم لإدارة التنبيهات"""

    def __init__(self):
        self.queue = queue.Queue()
        self.running = False
        self.thread = None

    def start(self):
        """بدء معالج التنبيهات"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._process_alerts, daemon=True)
            self.thread.start()
            logger.info("Alert queue processor started")

    def stop(self):
        """إيقاف معالج التنبيهات"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)

    def add_alert(self, user_id, alert_data):
        """إضافة تنبيه جديد للقائمة"""
        try:
            self.queue.put({
                'user_id': user_id,
                'alert_data': alert_data,
                'timestamp': time.time()
            }, timeout=1)
        except queue.Full:
            logger.warning(f"Alert queue full for user {user_id}")

    def _process_alerts(self):
        """معالجة التنبيهات بشكل مستمر"""
        while self.running:
            try:
                alert = self.queue.get(timeout=1)
                self._send_alert(alert)
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing alert: {str(e)}")

    def _send_alert(self, alert):
        """إرسال التنبيه للمستخدم"""
        user_id = alert['user_id']
        alert_data = alert['alert_data']

        try:
            # إرسال للواجهة
            socketio.emit('new_alert', alert_data, to=user_id)
            socketio.emit('log_update', {
                "message": f"🚨 تنبيه فوري: '{alert_data['keyword']}' في {alert_data['group']}"
            }, to=user_id)

            # إرسال للرسائل المحفوظة
            self._send_to_saved_messages(user_id, alert_data)

        except Exception as e:
            logger.error(f"Failed to send alert for user {user_id}: {str(e)}")

    def _send_to_saved_messages(self, user_id, alert_data):
        """إرسال التنبيه للرسائل المحفوظة"""
        try:
            with USERS_LOCK:
                if user_id in USERS:
                    client_manager = USERS[user_id].get('client_manager')
                    if client_manager and client_manager.client:
                        notification_msg = f"""🚨 تنبيه فوري - مراقبة شاملة للحساب

📝 الكلمة المراقبة: {alert_data['keyword']}
📊 المصدر: {alert_data['group']}
👤 المرسل: {alert_data.get('sender', 'غير معروف')}
🕐 وقت الرسالة: {alert_data.get('message_time', '')}
🔗 معرف الرسالة: {alert_data.get('message_id', '')}

💬 نص الرسالة:
{alert_data.get('message', '')[:500]}{'...' if len(alert_data.get('message', '')) > 500 else ''}

--- تنبيه فوري من المراقبة الشاملة اللحظية لكامل الحساب"""

                        # تشغيل في thread منفصل لضمان عدم التأخير
                        def send_alert_async():
                            try:
                                if hasattr(client_manager, 'run_coroutine'):
                                    client_manager.run_coroutine(
                                        client_manager.client.send_message('me', notification_msg)
                                    )
                                    logger.info(f"✅ Alert sent to saved messages for user {user_id}")
                                else:
                                    logger.warning(f"⚠️ No run_coroutine method available for user {user_id}")
                            except Exception as send_error:
                                logger.error(f"❌ Failed to send alert message: {str(send_error)}")

                        # تشغيل في thread منفصل
                        threading.Thread(target=send_alert_async, daemon=True).start()

        except Exception as e:
            logger.error(f"Failed to send to saved messages: {str(e)}")

# إنشاء نظام التنبيهات العالمي
alert_queue = AlertQueue()

# =========================== 
# إدارة الجلسات والإعدادات
# ===========================
def save_settings(user_id, settings):
    """حفظ إعدادات المستخدم"""
    try:
        path = os.path.join(SESSIONS_DIR, f"{user_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving settings for {user_id}: {str(e)}")
        return False

def load_settings(user_id):
    """تحميل إعدادات المستخدم"""
    try:
        path = os.path.join(SESSIONS_DIR, f"{user_id}.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading settings for {user_id}: {str(e)}")
        return {}

def load_all_sessions():
    """تحميل جميع الجلسات الموجودة"""
    logger.info("Loading existing sessions...")
    session_count = 0

    with USERS_LOCK:
        try:
            for filename in os.listdir(SESSIONS_DIR):
                if filename.endswith('.json'):
                    user_id = filename.split('.')[0]
                    settings = load_settings(user_id)

                    if settings and 'phone' in settings:
                        USERS[user_id] = {
                            'client_manager': None,
                            'settings': settings,
                            'thread': None,
                            'is_running': False,
                            'stats': {"sent": 0, "errors": 0},
                            'connected': False,
                            'authenticated': False,
                            'awaiting_code': False,
                            'awaiting_password': False,
                            'phone_code_hash': None,
                            'monitoring_active': False,
                            'event_handlers_registered': False
                        }
                        session_count += 1
                        logger.info(f"✓ Loaded session for {user_id}")

        except Exception as e:
            logger.error(f"Error loading sessions: {str(e)}")

    logger.info(f"Loaded {session_count} sessions successfully")
    return session_count

# =========================== 
# مدير التليجرام المحسن مع Event Handlers
# ===========================
class TelegramClientManager:
    """مدير عملاء التليجرام المحسن مع Event Handlers"""

    def __init__(self, user_id):
        self.user_id = user_id
        self.client = None
        self.loop = None
        self.thread = None
        self.stop_flag = threading.Event()
        self.is_ready = threading.Event()
        self.event_handlers_registered = False
        self.monitored_keywords = []
        self.monitored_groups = []

    async def send_to_saved_messages(self, text):
        """إرسال رسالة إلى المحادثة المحفوظة (Saved Messages)"""
        try:
            if self.client:
                await self.client.send_message('me', text)
                logger.info(f"Sent message to saved messages for user {self.user_id}")
        except Exception as e:
            logger.error(f"Failed to send to saved messages: {str(e)}")

    def start_client_thread(self):
        """بدء thread منفصل للعميل"""
        if self.thread and self.thread.is_alive():
            return

        self.stop_flag.clear()
        self.is_ready.clear()
        self.thread = threading.Thread(target=self._run_client_loop, daemon=True)
        self.thread.start()

        # انتظار حتى يصبح العميل جاهزاً
        if not self.is_ready.wait(timeout=30):
            raise Exception("Client initialization timeout")

    def _run_client_loop(self):
        """تشغيل event loop للعميل"""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            if API_ID and API_HASH:
                self.client = TelegramClient(StringSession(), int(API_ID), API_HASH)
            else:
                logger.error("API_ID or API_HASH not set")
                return

            self.loop.run_until_complete(self._client_main())

        except Exception as e:
            logger.error(f"Client thread error for {self.user_id}: {str(e)}")
        finally:
            if self.loop:
                self.loop.close()

    async def _client_main(self):
        """الوظيفة الرئيسية للعميل"""
        try:
            if self.client:
                await self.client.connect()
                self.is_ready.set()

                # تسجيل event handlers
                await self._register_event_handlers()

                # الحفاظ على الاتصال
                while not self.stop_flag.is_set():
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Client main error: {str(e)}")
        finally:
            if self.client:
                await self.client.disconnect()

    async def _register_event_handlers(self):
        """تسجيل event handlers للرسائل الجديدة"""
        try:
            if self.event_handlers_registered or not self.client:
                return

            @self.client.on(events.NewMessage)
            async def new_message_handler(event):
                await self._handle_new_message(event)
                # ─────────── إضافة ربط البوت التعليمي (التعديل الوحيد في الكود الأصلي) ───────────
                if learning_manager.is_active(self.user_id):
                    bot = learning_manager.get_bot(self.user_id)
                    await bot.handle_incoming_message(event, self)
                # ───────────────────────────────────────────────────────────────────────────────

            self.event_handlers_registered = True
            logger.info(f"Event handlers registered for user {self.user_id}")

        except Exception as e:
            logger.error(f"Failed to register event handlers: {str(e)}")

    async def _handle_new_message(self, event):
        """معالجة الرسائل الجديدة الواردة - مراقبة شاملة لكامل الحساب"""
        try:
            message = event.message
            if not message.text:
                return

            # الحصول على معلومات المحادثة
            chat = await event.get_chat()
            chat_username = getattr(chat, 'username', None)
            chat_title = getattr(chat, 'title', None)

            # تحديد معرف المجموعة/المحادثة
            group_identifier = None
            if chat_username:
                group_identifier = f"@{chat_username}"
            elif chat_title:
                group_identifier = chat_title
            elif hasattr(chat, 'first_name'):
                # محادثة شخصية
                group_identifier = f"محادثة مع {chat.first_name}"
            else:
                group_identifier = f"محادثة {chat.id}"

            # ⚠️ إزالة فحص المجموعات المحددة - مراقبة شاملة لكل شيء
            # مراقبة كامل المجموعات والمحادثات بدون استثناء

            # فحص الكلمات المفتاحية في كل رسالة
            if self.monitored_keywords:  # إذا كان هناك كلمات مراقبة
                message_lower = message.text.lower()
                for keyword in self.monitored_keywords:
                    keyword_lower = keyword.lower().strip()
                    if keyword_lower and keyword_lower in message_lower:
                        await self._trigger_keyword_alert(message, keyword, group_identifier, event)
            else:
                # إذا لم تكن هناك كلمات محددة، راقب كل الرسائل
                await self._trigger_keyword_alert(message, "رسالة جديدة", group_identifier, event)

        except Exception as e:
            logger.error(f"Error handling new message: {str(e)}")

    async def _trigger_keyword_alert(self, message, keyword, group_identifier, event):
        """تشغيل تنبيه الكلمة المفتاحية"""
        try:
            # الحصول على معلومات المرسل
            sender_name = "غير معروف"
            try:
                sender = await event.get_sender()
                if sender:
                    sender_name = getattr(sender, 'first_name', '') or getattr(sender, 'username', '') or str(sender.id)
            except:
                pass

            # إنشاء بيانات التنبيه
            alert_data = {
                "keyword": keyword,
                "group": group_identifier,
                "message": message.text[:200] + "..." if len(message.text) > 200 else message.text,
                "timestamp": time.strftime('%H:%M:%S'),
                "sender": sender_name,
                "message_time": time.strftime('%H:%M:%S', time.localtime(message.date.timestamp())),
                "message_id": message.id,
                "full_message": message.text
            }

            # إضافة التنبيه للقائمة بأولوية عالية
            alert_queue.add_alert(self.user_id, alert_data)

            # إرسال فوري للواجهة أيضاً
            try:
                socketio.emit('new_alert', alert_data, to=self.user_id)
                socketio.emit('log_update', {
                    "message": f"🚨 تنبيه فوري: '{keyword}' في {group_identifier} من {sender_name}"
                }, to=self.user_id)
                logger.info(f"✅ Immediate alert sent to interface for user {self.user_id}")
            except Exception as emit_error:
                logger.error(f"❌ Failed to emit immediate alert: {str(emit_error)}")

            logger.info(f"✅ Keyword alert triggered for user {self.user_id}: '{keyword}' in {group_identifier}")

        except Exception as e:
            logger.error(f"❌ Error triggering keyword alert: {str(e)}")

    def update_monitoring_settings(self, keywords, groups):
        """تحديث إعدادات المراقبة - فقط الكلمات المفتاحية (المجموعات للإرسال فقط)"""
        self.monitored_keywords = [k.strip() for k in keywords if k.strip()]
        # ⚠️ لا نحفظ مجموعات المراقبة - نراقب كل شيء
        # نحفظ مجموعات الإرسال منفصلة في الإعدادات العادية

        logger.info(f"Updated monitoring settings for {self.user_id}: {len(self.monitored_keywords)} keywords - مراقبة شاملة لكامل الحساب")

    def run_coroutine(self, coro):
        """تشغيل coroutine في event loop الخاص بالعميل"""
        if not self.loop:
            raise Exception("Event loop not initialized")

        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result(timeout=30)

    def stop(self):
        """إيقاف العميل"""
        self.stop_flag.set()
        if self.thread:
            self.thread.join(timeout=5)

def get_all_users_operations_status():
    """الحصول على حالة العمليات لجميع المستخدمين"""
    operations_status = {}

    with USERS_LOCK:
        for user_id, user_data in USERS.items():
            if user_id in PREDEFINED_USERS:
                operations_status[user_id] = {
                    'name': PREDEFINED_USERS[user_id]['name'],
                    'connected': user_data.get('connected', False),
                    'authenticated': user_data.get('authenticated', False),
                    'is_running': user_data.get('is_running', False),
                    'monitoring_active': user_data.get('monitoring_active', False),
                    'stats': user_data.get('stats', {"sent": 0, "errors": 0})
                }

    return operations_status

def notify_user_about_background_operations(user_id):
    """إشعار المستخدم بالعمليات التي تعمل في الخلفية"""
    try:
        active_operations = []

        with USERS_LOCK:
            for uid, user_data in USERS.items():
                if uid != user_id and uid in PREDEFINED_USERS:
                    if user_data.get('is_running', False) or user_data.get('monitoring_active', False):
                        active_operations.append({
                            'user_name': PREDEFINED_USERS[uid]['name'],
                            'operations': []
                        })

                        if user_data.get('monitoring_active', False):
                            active_operations[-1]['operations'].append('مراقبة نشطة')
                        if user_data.get('is_running', False):
                            active_operations[-1]['operations'].append('إرسال مجدول')

        if active_operations:
            operations_text = []
            for op in active_operations:
                operations_text.append(f"• {op['user_name']}: {', '.join(op['operations'])}")

            socketio.emit('log_update', {
                "message": f"📊 العمليات النشطة في الخلفية:\n" + "\n".join(operations_text)
            }, to=user_id)

    except Exception as e:
        logger.error(f"Error notifying about background operations: {str(e)}")

def update_monitoring_settings(self, keywords, groups):
    """تحديث إعدادات المراقبة - فقط الكلمات المفتاحية (المجموعات للإرسال فقط)"""
    self.monitored_keywords = [k.strip() for k in keywords if k.strip()]
    # ⚠️ لا نحفظ مجموعات المراقبة - نراقب كل شيء
    # نحفظ مجموعات الإرسال منفصلة في الإعدادات العادية

    logger.info(f"Updated monitoring settings for {self.user_id}: {len(self.monitored_keywords)} keywords - مراقبة شاملة لكامل الحساب")

def run_coroutine(self, coro):
    """تشغيل coroutine في event loop الخاص بالعميل"""
    if not self.loop:
        raise Exception("Event loop not initialized")

    future = asyncio.run_coroutine_threadsafe(coro, self.loop)
    return future.result(timeout=30)

def stop(self):
    """إيقاف العميل"""
    self.stop_flag.set()
    if self.thread:
        self.thread.join(timeout=5)

# =========================== 
# مدير التليجرام الرئيسي
# ===========================
class TelegramManager:
    """مدير عملاء التليجرام"""

    def __init__(self):
        self.client_managers = {}

    def get_client_manager(self, user_id):
        """الحصول على مدير العميل للمستخدم"""
        if user_id not in self.client_managers:
            self.client_managers[user_id] = TelegramClientManager(user_id)
        return self.client_managers[user_id]

    def setup_client(self, user_id, phone_number):
        """إعداد عميل التليجرام"""
        try:
            if not API_ID or not API_HASH:
                socketio.emit('log_update', {
                    "message": "❌ لم يتم إعداد بيانات Telegram API"
                }, to=user_id)
                return {
                    "status": "error", 
                    "message": "❌ بيانات API غير متوفرة - يرجى إضافة TELEGRAM_API_ID و TELEGRAM_API_HASH في الأسرار"
                }

            # التأكد من عدم وجود ملفات جلسة قديمة لرقم هاتف مختلف
            session_file = os.path.join(SESSIONS_DIR, f"{user_id}_session.session")
            if os.path.exists(session_file):
                try:
                    os.remove(session_file)
                    logger.info(f"Removed old session file for user {user_id}")
                except Exception as e:
                    logger.warning(f"Could not remove old session file: {e}")

            socketio.emit('log_update', {
                "message": "🔄 جاري إعداد العميل..."
            }, to=user_id)

            client_manager = self.get_client_manager(user_id)
            client_manager.start_client_thread()

            socketio.emit('log_update', {
                "message": "📡 فحص حالة التصريح..."
            }, to=user_id)

            is_authorized = client_manager.run_coroutine(
                client_manager.client.is_user_authorized()
            )

            if not is_authorized:
                socketio.emit('log_update', {
                    "message": f"📱 إرسال كود التحقق إلى: {phone_number}"
                }, to=user_id)

                try:
                    sent = client_manager.run_coroutine(
                        client_manager.client.send_code_request(phone_number)
                    )
                except Exception as send_err:
                    err_msg = str(send_err)
                    logger.error(f"send_code_request failed: {err_msg}")
                    socketio.emit('log_update', {
                        "message": f"❌ فشل إرسال الكود: {err_msg}"
                    }, to=user_id)
                    return {"status": "error", "message": f"❌ فشل إرسال الكود: {err_msg}"}

                code_type = type(sent.type).__name__ if hasattr(sent, 'type') else 'unknown'
                logger.info(f"Code sent to {phone_number}, type={code_type}")
                socketio.emit('log_update', {
                    "message": f"📨 نوع الإرسال: {code_type}"
                }, to=user_id)

                with USERS_LOCK:
                    if user_id in USERS:
                        USERS[user_id]['awaiting_code'] = True
                        USERS[user_id]['phone_code_hash'] = sent.phone_code_hash
                        USERS[user_id]['client_manager'] = client_manager
                        USERS[user_id]['connected'] = True

                # إرسال إشعار تحديث حالة تسجيل الدخول
                socketio.emit('login_status', {
                    "logged_in": False,
                    "connected": True,
                    "awaiting_code": True,
                    "awaiting_password": False,
                    "is_running": False
                }, to=user_id)

                socketio.emit('log_update', {
                    "message": "✅ تم إرسال كود التحقق - تحقق من رسائل تيليجرام"
                }, to=user_id)

                return {
                    "status": "code_required", 
                    "message": "📱 تم إرسال كود التحقق"
                }
            else:
                with USERS_LOCK:
                    if user_id in USERS:
                        USERS[user_id]['client_manager'] = client_manager
                        USERS[user_id]['connected'] = True
                        USERS[user_id]['authenticated'] = True
                        USERS[user_id]['awaiting_code'] = False
                        USERS[user_id]['awaiting_password'] = False

                # إرسال إشعار نجح تسجيل الدخول
                socketio.emit('login_status', {
                    "logged_in": True,
                    "connected": True,
                    "awaiting_code": False,
                    "awaiting_password": False,
                    "is_running": False
                }, to=user_id)

                socketio.emit('connection_status', {
                    "status": "connected"
                }, to=user_id)

                return {"status": "success", "message": "✅ تم تسجيل الدخول"}

        except Exception as e:
            error_message = str(e)
            logger.error(f"Setup error for {user_id}: {error_message}")

            # معالجة خاصة لخطأ ResendCodeRequest
            if "ResendCodeRequest" in error_message or "all available options" in error_message:
                socketio.emit('log_update', {
                    "message": "⚠️ تم استنفاد محاولات إرسال الكود. يرجى الانتظار قليلاً ثم المحاولة مرة أخرى"
                }, to=user_id)
                return {"status": "error", "message": "⚠️ يرجى الانتظار قبل طلب كود جديد"}

            socketio.emit('log_update', {
                "message": f"❌ خطأ في الإعداد: {error_message}"
            }, to=user_id)
            return {"status": "error", "message": f"❌ خطأ: {error_message}"}

    def _fetch_account_name(self, user_id):
        """جلب اسم حساب التليجرام (first_name + last_name) وتخزينه"""
        try:
            with USERS_LOCK:
                if user_id not in USERS:
                    return None
                client_manager = USERS[user_id].get('client_manager')
            if not client_manager or not client_manager.client:
                return None
            me = client_manager.run_coroutine(client_manager.client.get_me())
            if not me:
                return None
            parts = []
            if getattr(me, 'first_name', None):
                parts.append(me.first_name)
            if getattr(me, 'last_name', None):
                parts.append(me.last_name)
            name = ' '.join(parts).strip()
            if not name:
                name = getattr(me, 'username', None) or 'حساب تليجرام'
            with USERS_LOCK:
                if user_id in USERS:
                    USERS[user_id]['account_name'] = name
                    USERS[user_id]['account_username'] = getattr(me, 'username', None)
                    USERS[user_id]['account_phone'] = getattr(me, 'phone', None)
            return name
        except Exception as e:
            logger.error(f"Error fetching account name for {user_id}: {e}")
            return None

    def verify_code(self, user_id, code):
        """التحقق من كود التحقق"""
        try:
            with USERS_LOCK:
                if user_id not in USERS or not USERS[user_id].get('awaiting_code'):
                    return {"status": "error", "message": "❌ لم يتم طلب كود التحقق"}

                client_manager = USERS[user_id].get('client_manager')
                phone_code_hash = USERS[user_id].get('phone_code_hash')
                phone = USERS[user_id]['settings']['phone']

            if not client_manager or not phone_code_hash:
                return {"status": "error", "message": "❌ بيانات الجلسة مفقودة"}

            try:
                user = client_manager.run_coroutine(
                    client_manager.client.sign_in(phone, code, phone_code_hash=phone_code_hash)
                )

                with USERS_LOCK:
                    USERS[user_id]['connected'] = True
                    USERS[user_id]['authenticated'] = True
                    USERS[user_id]['awaiting_code'] = False
                    USERS[user_id]['awaiting_password'] = False

                account_name = self._fetch_account_name(user_id)

                # إرسال تحديث حالة تسجيل الدخول
                socketio.emit('login_status', {
                    "logged_in": True,
                    "connected": True,
                    "awaiting_code": False,
                    "awaiting_password": False,
                    "is_running": False,
                    "account_name": account_name
                }, to=user_id)

                socketio.emit('connection_status', {
                    "status": "connected"
                }, to=user_id)

                return {"status": "success", "message": "✅ تم التحقق بنجاح", "account_name": account_name}

            except SessionPasswordNeededError:
                with USERS_LOCK:
                    USERS[user_id]['awaiting_code'] = False
                    USERS[user_id]['awaiting_password'] = True

                # إرسال تحديث حالة تسجيل الدخول
                socketio.emit('login_status', {
                    "logged_in": False,
                    "connected": True,
                    "awaiting_code": False,
                    "awaiting_password": True,
                    "is_running": False
                }, to=user_id)

                return {
                    "status": "password_required", 
                    "message": "🔒 يرجى إدخال كلمة مرور التحقق بخطوتين"
                }

        except PhoneCodeInvalidError:
            return {"status": "error", "message": "❌ كود التحقق غير صحيح"}
        except PhoneCodeExpiredError:
            return {"status": "error", "message": "❌ انتهت صلاحية كود التحقق"}
        except Exception as e:
            logger.error(f"Code verification error: {str(e)}")
            return {"status": "error", "message": f"❌ خطأ: {str(e)}"}

    def verify_password(self, user_id, password):
        """التحقق من كلمة المرور"""
        try:
            with USERS_LOCK:
                if user_id not in USERS or not USERS[user_id].get('awaiting_password'):
                    return {"status": "error", "message": "❌ لم يتم طلب كلمة المرور"}

                client_manager = USERS[user_id].get('client_manager')

            if not client_manager:
                return {"status": "error", "message": "❌ بيانات الجلسة مفقودة"}

            try:
                await_result = client_manager.run_coroutine(
                    client_manager.client.sign_in(password=password)
                )

                with USERS_LOCK:
                    USERS[user_id]['connected'] = True
                    USERS[user_id]['authenticated'] = True
                    USERS[user_id]['awaiting_password'] = False

                account_name = self._fetch_account_name(user_id)

                # إرسال تحديث حالة تسجيل الدخول بعد كلمة المرور
                socketio.emit('login_status', {
                    'logged_in': True,
                    'connected': True,
                    'awaiting_code': False,
                    'awaiting_password': False,
                    'account_name': account_name
                }, to=user_id)

                return {"status": "success", "message": "✅ تم التحقق بنجاح", "account_name": account_name}

            except PasswordHashInvalidError:
                return {"status": "error", "message": "❌ كلمة المرور غير صحيحة"}

        except Exception as e:
            logger.error(f"Password verification error: {str(e)}")
            return {"status": "error", "message": f"❌ خطأ: {str(e)}"}

    def send_message_async(self, user_id, entity, message):
        """إرسال رسالة"""
        try:
            with USERS_LOCK:
                if user_id not in USERS:
                    raise Exception("المستخدم غير موجود - يرجى تسجيل الدخول أولاً")

                client_manager = USERS[user_id].get('client_manager')
                if not client_manager:
                    raise Exception("لم يتم تسجيل الدخول - يرجى تسجيل الدخول في التليجرام أولاً")

                if not client_manager.client:
                    raise Exception("عميل التليجرام غير مُهيأ - يرجى إعادة تسجيل الدخول")

            try:
                is_authorized = client_manager.run_coroutine(
                    client_manager.client.is_user_authorized()
                )

                if not is_authorized:
                    raise Exception("جلسة التليجرام منتهية الصلاحية - يرجى إعادة تسجيل الدخول")
            except Exception as auth_error:
                raise Exception(f"خطأ في التحقق من التصريح: {str(auth_error)}")

            try:
                entity_obj = client_manager.run_coroutine(
                    client_manager.client.get_entity(entity)
                )
            except:
                if not entity.startswith('@') and not entity.startswith('https://'):
                    entity = '@' + entity
                entity_obj = client_manager.run_coroutine(
                    client_manager.client.get_entity(entity)
                )

            result = client_manager.run_coroutine(
                client_manager.client.send_message(entity_obj, message)
            )

            return {"success": True, "message_id": result.id}

        except Exception as e:
            logger.error(f"Send message error: {str(e)}")
            raise Exception(str(e))

    def send_media_async(self, user_id, entity, image_files):
        """إرسال الصور فقط"""
        try:
            with USERS_LOCK:
                if user_id not in USERS:
                    raise Exception("المستخدم غير موجود")

                client_manager = USERS[user_id].get('client_manager')

            if not client_manager:
                raise Exception("العميل غير متصل")

            is_authorized = client_manager.run_coroutine(
                client_manager.client.is_user_authorized()
            )

            if not is_authorized:
                raise Exception("العميل غير مصرح")

            try:
                entity_obj = client_manager.run_coroutine(
                    client_manager.client.get_entity(entity)
                )
            except:
                if not entity.startswith('@') and not entity.startswith('https://'):
                    entity = '@' + entity
                entity_obj = client_manager.run_coroutine(
                    client_manager.client.get_entity(entity)
                )

            # إرسال كل صورة منفصلة
            results = []
            for img_file in image_files:
                try:
                    result = client_manager.run_coroutine(
                        client_manager.client.send_file(
                            entity_obj, 
                            img_file['path'],
                            caption=f"📷 {img_file['name']}"
                        )
                    )
                    results.append(result.id)
                except Exception as img_error:
                    logger.error(f"Error sending image {img_file['name']}: {str(img_error)}")
                    raise img_error

            return {"success": True, "message_ids": results}

        except Exception as e:
            logger.error(f"Send media error: {str(e)}")
            raise Exception(str(e))

    def send_message_with_media_async(self, user_id, entity, message, image_files):
        """إرسال رسالة مع صور - طريقة محسنة ومُصلحة"""
        try:
            with USERS_LOCK:
                if user_id not in USERS:
                    raise Exception("المستخدم غير موجود")

                client_manager = USERS[user_id].get('client_manager')

            if not client_manager:
                raise Exception("العميل غير متصل")

            is_authorized = client_manager.run_coroutine(
                client_manager.client.is_user_authorized()
            )

            if not is_authorized:
                raise Exception("العميل غير مصرح")

            try:
                entity_obj = client_manager.run_coroutine(
                    client_manager.client.get_entity(entity)
                )
            except:
                if not entity.startswith('@') and not entity.startswith('https://'):
                    entity = '@' + entity
                entity_obj = client_manager.run_coroutine(
                    client_manager.client.get_entity(entity)
                )

            results = []

            # إرسال الصور مع الرسالة النصية
            if image_files and len(image_files) > 0:
                # طريقة محسنة: إرسال جميع الصور مع النص كرسالة واحدة
                try:
                    # تحضير مسارات الصور
                    image_paths = []
                    for img_file in image_files:
                        if os.path.exists(img_file['path']):
                            image_paths.append(img_file['path'])
                        else:
                            logger.warning(f"Image file not found: {img_file['path']}")

                    if image_paths:
                        # إرسال كل الصور مع النص كرسالة واحدة
                        if len(image_paths) == 1:
                            # صورة واحدة فقط
                            media_result = client_manager.run_coroutine(
                                client_manager.client.send_file(
                                    entity_obj, 
                                    image_paths[0],
                                    caption=message if message else "📷"
                                )
                            )
                            results.append(media_result.id)
                            logger.info(f"Successfully sent single image with message to {entity}")
                        else:
                            # عدة صور - إرسال كمجموعة (album)
                            try:
                                # إرسال النص أولاً إذا كان موجوداً
                                if message and message.strip():
                                    text_result = client_manager.run_coroutine(
                                        client_manager.client.send_message(entity_obj, message)
                                    )
                                    results.append(text_result.id)

                                # ثم إرسال الصور كمجموعة
                                media_result = client_manager.run_coroutine(
                                    client_manager.client.send_file(
                                        entity_obj, 
                                        image_paths,
                                        caption="📷 مجموعة صور"
                                    )
                                )

                                # معالجة النتائج
                                if hasattr(media_result, '__iter__'):
                                    for result in media_result:
                                        results.append(result.id)
                                else:
                                    results.append(media_result.id)

                                logger.info(f"Successfully sent {len(image_paths)} images as album to {entity}")
                            except Exception as album_error:
                                logger.warning(f"Failed to send as album, sending individually: {str(album_error)}")

                                # إرسال النص أولاً إذا كان موجوداً
                                if message and message.strip():
                                    text_result = client_manager.run_coroutine(
                                        client_manager.client.send_message(entity_obj, message)
                                    )
                                    results.append(text_result.id)

                                # إرسال الصور واحدة تلو الأخرى
                                for i, img_path in enumerate(image_paths):
                                    try:
                                        media_result = client_manager.run_coroutine(
                                            client_manager.client.send_file(
                                                entity_obj, 
                                                img_path,
                                                caption=f"📷 صورة {i+1}"
                                            )
                                        )
                                        results.append(media_result.id)
                                    except Exception as img_error:
                                        logger.error(f"Error sending individual image {i+1}: {str(img_error)}")
                                        continue

                except Exception as media_error:
                    logger.error(f"Error in media sending process: {str(media_error)}")
                    # كحل أخير، أرسل النص فقط
                    if message and message.strip():
                        text_result = client_manager.run_coroutine(
                            client_manager.client.send_message(entity_obj, message)
                        )
                        results.append(text_result.id)
                        logger.info(f"Sent text only due to media error: {str(media_error)}")
            else:
                # إذا لم تكن هناك صور، أرسل الرسالة النصية فقط
                if message and message.strip():
                    text_result = client_manager.run_coroutine(
                        client_manager.client.send_message(entity_obj, message)
                    )
                    results.append(text_result.id)
                    logger.info(f"Successfully sent text message to {entity}")

            return {"success": True, "message_ids": results}

        except Exception as e:
            logger.error(f"Send message with media error: {str(e)}")
            raise Exception(str(e))


# إنشاء مدير التليجرام
telegram_manager = TelegramManager()

# =========================== 
# نظام المراقبة المحسن مع Event Handlers
# ===========================
def monitoring_worker(user_id):
    """مهمة المراقبة المحسنة مع Event Handlers"""
    logger.info(f"Starting enhanced monitoring worker with event handlers for user {user_id}")

    try:
        with USERS_LOCK:
            if user_id not in USERS:
                logger.error(f"No user data found for {user_id}")
                return

            USERS[user_id]['monitoring_active'] = True
            client_manager = USERS[user_id].get('client_manager')
            settings = USERS[user_id]['settings']

        if not client_manager:
            logger.error(f"No client manager for user {user_id}")
            return

        # تحديث إعدادات المراقبة في العميل
        watch_words = settings.get('watch_words', [])
        send_groups = settings.get('groups', [])  # مجموعات الإرسال فقط

        if hasattr(client_manager, 'update_monitoring_settings'):
            client_manager.update_monitoring_settings(watch_words, send_groups)
        else:
            logger.warning(f"Client manager for {user_id} does not have update_monitoring_settings method.")


        # إرسال إشعار بدء المراقبة
        if watch_words:
            socketio.emit('log_update', {
                "message": f"🚀 بدأت المراقبة الشاملة الفورية - {len(watch_words)} كلمة مراقبة في كامل الحساب | الإرسال لـ {len(send_groups)} مجموعة"
            }, to=user_id)
        else:
            socketio.emit('log_update', {
                "message": f"🚀 بدأت المراقبة الشاملة لكامل الرسائل في الحساب | الإرسال لـ {len(send_groups)} مجموعة"
            }, to=user_id)

        # الحفاظ على المراقبة نشطة
        consecutive_errors = 0

        max_consecutive_errors = 5

        while True:
            with USERS_LOCK:
                if user_id not in USERS or not USERS[user_id].get('is_running', False):
                    logger.info(f"Stopping monitoring for user {user_id} as is_running is False")
                    break

                user_data = USERS[user_id].copy()
                USERS[user_id]['monitoring_active'] = True

            try:
                # تنفيذ الإرسال المجدول إذا كان مطلوب
                settings = user_data.get('settings', {})
                send_type = settings.get('send_type', 'manual')
                current_time = time.time()

                if send_type == 'scheduled':
                    interval_seconds = int(settings.get('interval_seconds', 3600))
                    last_send = user_data.get('last_scheduled_send', 0)

                    if current_time - last_send >= interval_seconds:
                        logger.info(f"Executing scheduled send for user {user_id}")
                        execute_scheduled_messages(user_id, settings)

                        with USERS_LOCK:
                            if user_id in USERS:
                                USERS[user_id]['last_scheduled_send'] = current_time

                consecutive_errors = 0

                # إرسال إشارة حياة
                status_info = {
                    'timestamp': time.strftime('%H:%M:%S'),
                    'status': 'active',
                    'type': 'event_driven_monitoring',
                    'keywords_active': bool(watch_words),
                    'event_handlers': True
                }

                socketio.emit('heartbeat', status_info, to=user_id)

            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Monitoring cycle error for {user_id}: {str(e)}")

                socketio.emit('log_update', {
                    "message": f"⚠️ خطأ في المراقبة: {str(e)[:100]}"
                }, to=user_id)

                if consecutive_errors >= max_consecutive_errors:
                    socketio.emit('log_update', {
                        "message": f"❌ تم إيقاف المراقبة بسبب تكرار الأخطاء ({consecutive_errors})"
                    }, to=user_id)
                    # إيقاف المراقبة إذا تجاوزنا الحد الأقصى للأخطاء
                    with USERS_LOCK:
                        if user_id in USERS:
                            USERS[user_id]['is_running'] = False
                    break

            # فترة انتظار مناسبة
            time.sleep(10)

    except Exception as e:
        logger.error(f"Monitoring worker top-level error for {user_id}: {str(e)}")
    finally:
        with USERS_LOCK:
            if user_id in USERS:
                USERS[user_id]['is_running'] = False
                USERS[user_id]['monitoring_active'] = False
                USERS[user_id]['thread'] = None

        socketio.emit('log_update', {
            "message": "⏹ تم إيقاف نظام المراقبة المحسن"
        }, to=user_id)

        socketio.emit('heartbeat', {
            'timestamp': time.strftime('%H:%M:%S'),
            'status': 'stopped'
        }, to=user_id)

        logger.info(f"Enhanced monitoring worker ended for user {user_id}")

def execute_scheduled_messages(user_id, settings):
    """تنفيذ الإرسال المجدول"""
    groups = settings.get('groups', [])
    message = settings.get('message', '')

    if not groups or not message:
        return

    try:
        socketio.emit('log_update', {
            "message": f"📅 تنفيذ الإرسال المجدول إلى {len(groups)} مجموعة"
        }, to=user_id)

        successful = 0
        failed = 0

        for i, group in enumerate(groups, 1):
            try:
                result = telegram_manager.send_message_async(user_id, group, message)

                socketio.emit('log_update', {
                    "message": f"✅ [{i}/{len(groups)}] إرسال مجدول نجح إلى: {group}"
                }, to=user_id)

                successful += 1
                with USERS_LOCK:
                    if user_id in USERS:
                        USERS[user_id]['stats']['sent'] += 1

                if i < len(groups):
                    time.sleep(3)

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Scheduled send error to {group}: {error_msg}")

                socketio.emit('log_update', {
                    "message": f"❌ [{i}/{len(groups)}] إرسال مجدول فشل إلى {group}"
                }, to=user_id)

                failed += 1
                with USERS_LOCK:
                    if user_id in USERS:
                        USERS[user_id]['stats']['errors'] += 1

        socketio.emit('log_update', {
            "message": f"📊 انتهى الإرسال المجدول: ✅ {successful} نجح | ❌ {failed} فشل"
        }, to=user_id)

    except Exception as e:
        logger.error(f"Scheduled messages error: {str(e)}")

# =========================== 
# أحداث Socket.IO
# ===========================
@socketio.on('connect')
def handle_connect():
    try:
        # إذا لم يكن هناك user_id، نستخدم المستخدم الأول كافتراضي
        if 'user_id' not in session:
            session['user_id'] = "user_1"  # المستخدم الافتراضي
            session.permanent = True

        user_id = session['user_id']

        # التأكد من أن المستخدم ضمن المستخدمين المحددين مسبقاً
        if user_id not in PREDEFINED_USERS:
            user_id = "user_1"  # الافتراضي إذا لم يكن مستخدماً صحيحاً
            session['user_id'] = user_id

        join_room(user_id)
        logger.info(f"User {user_id} ({PREDEFINED_USERS[user_id]['name']}) connected via socket")

        # إرسال إشارة اتصال فورية مع معلومات المستخدم
        emit('connection_confirmed', {
            'status': 'connected',
            'user_id': user_id,
            'user_name': PREDEFINED_USERS[user_id]['name'],
            'timestamp': time.strftime('%H:%M:%S')
        })

        # إرسال قائمة المستخدمين المتاحين
        emit('users_list', {
            'current_user': user_id,
            'users': PREDEFINED_USERS
        })

        # إشعار بالعمليات النشطة في الخلفية
        notify_user_about_background_operations(user_id)

        # إرسال حالة جميع المستخدمين
        all_status = get_all_users_operations_status()
        emit('all_users_status', all_status)

    except Exception as e:
        logger.error(f"Connection error: {str(e)}")
        emit('connection_error', {'message': str(e)})

# دالة Socket.IO للتبديل بين المستخدمين - محسنة
@socketio.on('switch_user')
def handle_switch_user(data):
    """التبديل إلى مستخدم مختلف"""
    try:
        new_user_id = data.get('user_id')

        if not new_user_id or new_user_id not in PREDEFINED_USERS:
            emit('error', {'message': 'مستخدم غير صحيح'})
            return

        # مغادرة الغرفة القديمة بأمان
        old_user_id = session.get('user_id', 'user_1')
        try:
            leave_room(old_user_id)
        except Exception as leave_error:
            logger.warning(f"Error leaving room {old_user_id}: {str(leave_error)}")

        # تحديث الجلسة
        session['user_id'] = new_user_id
        session.permanent = True

        # الانضمام للغرفة الجديدة بأمان
        try:
            join_room(new_user_id)
        except Exception as join_error:
            logger.warning(f"Error joining room {new_user_id}: {str(join_error)}")

        logger.info(f"User switched from {old_user_id} to {new_user_id}")

        # إرسال تأكيد التبديل
        emit('user_switched', {
            'current_user': new_user_id,
            'user_name': PREDEFINED_USERS[new_user_id]['name'],
            'message': f"تم التبديل إلى {PREDEFINED_USERS[new_user_id]['name']}"
        })

        # إرسال حالة المستخدم الجديد
        try:
            with USERS_LOCK:
                if new_user_id in USERS:
                    user_data = USERS[new_user_id]
                    connected = user_data.get('connected', False)
                    authenticated = user_data.get('authenticated', False)
                    awaiting_code = user_data.get('awaiting_code', False)
                    awaiting_password = user_data.get('awaiting_password', False)
                    is_running = user_data.get('is_running', False)

                    emit('connection_status', {
                        "status": "connected" if connected else "disconnected"
                    })

                    emit('login_status', {
                        "logged_in": authenticated,
                        "connected": connected,
                        "awaiting_code": awaiting_code,
                        "awaiting_password": awaiting_password,
                        "is_running": is_running
                    })

                    # إرسال إعدادات المستخدم
                    settings = load_settings(new_user_id)
                    emit('user_settings', settings)
                else:
                    # إرسال حالة افتراضية للمستخدم الجديد
                    emit('connection_status', {"status": "disconnected"})
                    emit('login_status', {
                        "logged_in": False,
                        "connected": False,
                        "awaiting_code": False,
                        "awaiting_password": False,
                        "is_running": False
                    })
        except Exception as status_error:
            logger.error(f"Error sending user status: {str(status_error)}")

    except Exception as e:
        logger.error(f"Error switching user: {str(e)}")
        emit('error', {'message': f'خطأ في التبديل: {str(e)}'})

    # إرسال حالة الاتصال فوراً
    with USERS_LOCK:
        if user_id in USERS:
            connected = USERS[user_id].get('connected', False)
            authenticated = USERS[user_id].get('authenticated', False)
            awaiting_code = USERS[user_id].get('awaiting_code', False)
            awaiting_password = USERS[user_id].get('awaiting_password', False)
            is_running = USERS[user_id].get('is_running', False)

            emit('connection_status', {
                "status": "connected" if connected else "disconnected"
            })

            emit('login_status', {
                "logged_in": authenticated,
                "connected": connected,
                "awaiting_code": awaiting_code,
                "awaiting_password": awaiting_password,
                "is_running": is_running
            })

    emit('console_log', {
        "message": f"[{time.strftime('%H:%M:%S')}] INFO: Socket connected"
    })

    # إرسال رسالة ترحيب
    emit('log_update', {
        "message": f"🔄 تم الاتصال بالخادم - {time.strftime('%H:%M:%S')}"
    })


@socketio.on('disconnect')
def handle_disconnect(data=None):
    if 'user_id' in session:
        user_id = session['user_id']
        leave_room(user_id)
        logger.info(f"User {user_id} disconnected from socket")

# =========================== 
# المسارات الأساسية
# ===========================
@app.route("/")
def index():
    # إنشاء أو التحقق من user_id مع نظام المستخدمين الخمسة
    if 'user_id' not in session:
        session['user_id'] = "user_1"  # المستخدم الافتراضي
        session.permanent = True
    elif session['user_id'] not in PREDEFINED_USERS:
        # إذا كان المستخدم غير صالح، استخدم الافتراضي
        session['user_id'] = "user_1"

    user_id = session['user_id']

    # تحميل إعدادات المستخدم الحالي (قد تكون فارغة للمستخدمين الجدد)
    settings = load_settings(user_id)
    connection_status = "disconnected"

    # التأكد من وجود بيانات المستخدم في الذاكرة
    with USERS_LOCK:
        if user_id not in USERS:
            # إنشاء بيانات افتراضية للمستخدم إذا لم تكن موجودة
            USERS[user_id] = {
                'client_manager': None,
                'settings': settings,
                'thread': None,
                'is_running': False,
                'stats': {"sent": 0, "errors": 0},
                'connected': False,
                'authenticated': False,
                'awaiting_code': False,
                'awaiting_password': False,
                'phone_code_hash': None,
                'monitoring_active': False,
                'event_handlers_registered': False
            }

        # الحصول على حالة الاتصال للمستخدم الحالي
        user_data = USERS[user_id]
        connected = user_data.get('connected', False)
        connection_status = "connected" if connected else "disconnected"

    # إضافة عنوان التطبيق
    app_title = "مركز سرعة انجاز 📚للخدمات الطلابية والاكاديمية"
    whatsapp_link = "https://wa.me/+966510349663"

    # إضافة معلومات المستخدم الحالي والمستخدمين المتاحين
    current_user = PREDEFINED_USERS[user_id]

    response = render_template('index.html',
                          settings=settings,
                          connection_status=connection_status,
                          app_title=app_title,
                          whatsapp_link=whatsapp_link,
                          current_user=current_user,
                          predefined_users=PREDEFINED_USERS)

    # إنشاء response object مع headers لمنع التخزين المؤقت
    from flask import make_response
    resp = make_response(response)
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'

    return resp

@app.route("/fresh")
def fresh():
    """مسار جديد لتجاوز أي مشاكل في التخزين المؤقت"""
    from flask import make_response
    html = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <title>🚀 التطبيق يعمل بنجاح!</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .success { font-size: 2em; margin: 20px 0; }
        .message { font-size: 1.2em; margin: 10px 0; }
        .btn { background: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-size: 1.1em; display: inline-block; margin: 10px; }
        .btn:hover { background: #218838; color: white; }
    </style>
</head>
<body>
    <div class="success">✅ التطبيق يعمل بشكل مثالي!</div>
    <div class="message">🎉 مركز سرعة انجاز للخدمات الطلابية والأكاديمية</div>
    <div class="message">📱 نظام مراقبة التليجرام الذكي</div>
    <a href="/" class="btn">🏠 الانتقال للتطبيق الرئيسي</a>
    <script>
        setTimeout(function() {
            window.location.href = '/';
        }, 3000);
    </script>
</body>
</html>"""

    resp = make_response(html)
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'

    return resp

# معالجات heartbeat
@socketio.on('heartbeat')
def handle_heartbeat(data):
    try:
        user_id = session.get('user_id')
        if user_id:
            emit('heartbeat_response', {
                'timestamp': time.time(),
                'server_time': time.strftime('%H:%M:%S')
            })
    except Exception as e:
        logger.error(f"Heartbeat error: {str(e)}")

@app.route('/static/<path:filename>')
def static_files(filename):
    """خدمة الملفات الثابتة"""
    return app.send_static_file(filename)

@app.route("/manifest.json")
def manifest():
    manifest_data = {
        "name": "مركز سرعة انجاز للخدمات الطلابية والأكاديمية",
        "short_name": "سرعة انجاز",
        "start_url": "/",
        "display": "standalone",
        "theme_color": "#1e3c78",
        "background_color": "#0d1117",
        "icons": [
            {"src": "/static/icons/icon-72.png", "sizes": "72x72", "type": "image/png"},
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"}
        ]
    }
    return app.response_class(json.dumps(manifest_data, indent=2), mimetype='application/manifest+json')

@app.route("/sw.js")
def service_worker():
    sw_js = """
const CACHE_NAME = 'app-cache-v1';
const urlsToCache = ['/', '/static/css/style.css'];

self.addEventListener('install', event => {
    event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache)));
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request).then(response => response || fetch(event.request))
    );
});
"""
    return app.response_class(sw_js, content_type='application/javascript')

# =========================== 
# API Routes - نفس الكود الأصلي مع إضافات تحسين
# ===========================

@app.route("/api", methods=["GET", "HEAD"])
def api_health():
    """نقطة نهاية صحة النظام - لمنع أخطاء 404 من heartbeat"""
    try:
        if request.method == "HEAD":
            return "", 200
        return jsonify({"status": "ok", "timestamp": time.time(), "message": "Server is running"})
    except Exception as e:
        logger.error(f"Error in api health check: {str(e)}")
        if request.method == "HEAD":
            return "", 500
        return jsonify({"status": "error", "message": "Server error"}), 500
@app.route("/api/save_login", methods=["POST"])
def api_save_login():
    data = request.json

    if not data or not data.get('phone'):
        return jsonify({
            "success": False, 
            "message": "❌ يرجى إدخال رقم الهاتف"
        })

    new_phone = data.get('phone')

    # التحقق من وجود user_id في الجلسة
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
        session.permanent = True
    else:
        # التحقق من تغيير رقم الهاتف
        current_user_id = session['user_id']
        current_settings = load_settings(current_user_id)

        # إذا تغير رقم الهاتف، إنشاء جلسة جديدة
        if current_settings.get('phone') and current_settings.get('phone') != new_phone:
            logger.info(f"Phone number changed from {current_settings.get('phone')} to {new_phone}, creating new session")

            # إيقاف الجلسة الحالية إذا كانت نشطة
            with USERS_LOCK:
                if current_user_id in USERS:
                    if USERS[current_user_id].get('is_running'):
                        USERS[current_user_id]['is_running'] = False

                    client_manager = USERS[current_user_id].get('client_manager')
                    if client_manager:
                        client_manager.stop()

                    del USERS[current_user_id]

            # إنشاء user_id جديد
            session['user_id'] = str(uuid.uuid4())
            session.permanent = True

            socketio.emit('log_update', {
                "message": f"🔄 تم إنشاء جلسة جديدة لرقم {new_phone}"
            }, to=session['user_id'])

    user_id = session['user_id']

    settings = {
        'phone': new_phone,
        'password': data.get('password', ''),
        'login_time': time.time()
    }

    if not save_settings(user_id, settings):
        return jsonify({
            "success": False, 
            "message": "❌ فشل في حفظ البيانات"
        })

    try:
        socketio.emit('log_update', {
            "message": "🔄 بدء عملية تسجيل الدخول..."
        }, to=user_id)

        # تنظيف أي جلسات قديمة لنفس رقم الهاتف
        with USERS_LOCK:
            # البحث عن جلسات أخرى بنفس رقم الهاتف وحذفها
            users_to_remove = []
            for existing_user_id, user_data in USERS.items():
                if existing_user_id != user_id and user_data['settings'].get('phone') == settings['phone']:
                    users_to_remove.append(existing_user_id)
                    logger.info(f"Removing duplicate session for phone {settings['phone']}: {existing_user_id}")

            for old_user_id in users_to_remove:
                if USERS[old_user_id].get('is_running'):
                    USERS[old_user_id]['is_running'] = False

                client_manager = USERS[old_user_id].get('client_manager')
                if client_manager:
                    client_manager.stop()

                del USERS[old_user_id]

            # إنشاء الجلسة الجديدة
            USERS[user_id] = {
                'client_manager': None,
                'settings': settings,
                'thread': None,
                'is_running': False,
                'stats': {"sent": 0, "errors": 0},
                'connected': False,
                'authenticated': False,
                'awaiting_code': False,
                'awaiting_password': False,
                'phone_code_hash': None,
                'monitoring_active': False,
                'event_handlers_registered': False
            }

        result = telegram_manager.setup_client(user_id, settings['phone'])

        if result["status"] == "success":
            socketio.emit('log_update', {
                "message": "✅ تم تسجيل الدخول بنجاح"
            }, to=user_id)

            socketio.emit('connection_status', {
                "status": "connected"
            }, to=user_id)

            # إرسال تحديث حالة تسجيل الدخول للواجهة
            socketio.emit('login_status', {
                "logged_in": True,
                "connected": True,
                "awaiting_code": False,
                "awaiting_password": False,
                "is_running": False
            }, to=user_id)

            return jsonify({
                "success": True, 
                "message": "✅ تم تسجيل الدخول"
            })

        elif result["status"] == "code_required":
            socketio.emit('log_update', {
                "message": "📱 تم إرسال كود التحقق"
            }, to=user_id)

            return jsonify({
                "success": True, 
                "message": "📱 تم إرسال كود التحقق", 
                "code_required": True
            })

        else:
            error_message = result.get('message', 'خطأ غير معروف')
            socketio.emit('log_update', {
                "message": f"❌ {error_message}"
            }, to=user_id)

            return jsonify({
                "success": False, 
                "message": f"❌ {error_message}"
            })

    except Exception as e:
        logger.error(f"Login error for user {user_id}: {str(e)}")
        socketio.emit('log_update', {
            "message": f"❌ خطأ: {str(e)}"
        }, to=user_id)

        return jsonify({
            "success": False, 
            "message": f"❌ خطأ: {str(e)}"
        })

@app.route("/api/verify_code", methods=["POST"])
def api_verify_code():
    # التأكد من وجود user_id في الجلسة
    if 'user_id' not in session:
        return jsonify({
            "success": False, 
            "message": "❌ الجلسة غير صالحة، يرجى إعادة تحميل الصفحة"
        })

    user_id = session['user_id']
    data = request.json

    if not data:
        return jsonify({
            "success": False, 
            "message": "❌ لم يتم إرسال البيانات"
        })

    code = data.get('code')
    password = data.get('password')

    if not code and not password:
        return jsonify({
            "success": False, 
            "message": "❌ يرجى إدخال الكود أو كلمة المرور"
        })

    try:
        if code:
            result = telegram_manager.verify_code(user_id, code)
        else:
            result = telegram_manager.verify_password(user_id, password)

        if result["status"] == "success":
            account_name = result.get("account_name")
            socketio.emit('log_update', {
                "message": f"✅ تم التحقق بنجاح — أهلاً {account_name}" if account_name else "✅ تم التحقق بنجاح"
            }, to=user_id)

            socketio.emit('connection_status', {
                "status": "connected"
            }, to=user_id)

            return jsonify({
                "success": True,
                "message": f"✅ تم التحقق بنجاح — أهلاً {account_name}" if account_name else "✅ تم التحقق بنجاح",
                "account_name": account_name
            })

        elif result["status"] == "password_required":
            return jsonify({
                "success": True, 
                "message": result["message"], 
                "password_required": True
            })

        else:
            error_message = result.get('message', 'فشل التحقق')
            socketio.emit('log_update', {
                "message": f"❌ {error_message}"
            }, to=user_id)

            return jsonify({
                "success": False, 
                "message": f"❌ {error_message}"
            })

    except Exception as e:
        socketio.emit('log_update', {
            "message": f"❌ خطأ في التحقق: {str(e)}"
        }, to=user_id)

        return jsonify({
            "success": False, 
            "message": f"❌ خطأ: {str(e)}"
        })

@app.route("/api/save_settings", methods=["POST"])
def api_save_settings():
    # التأكد من وجود user_id في الجلسة
    if 'user_id' not in session:
        return jsonify({
            "success": False, 
            "message": "❌ الجلسة غير صالحة، يرجى إعادة تحميل الصفحة"
        })

    user_id = session['user_id']
    data = request.json

    if not data:
        return jsonify({
            "success": False, 
            "message": "❌ لم يتم إرسال البيانات"
        })

    current_settings = load_settings(user_id)
    current_settings.update({
        'message': data.get('message', ''),
        'groups': [g.strip() for g in data.get('groups', '').split('\n') if g.strip()],
        'interval_seconds': int(data.get('interval_seconds', 3600)),
        'watch_words': [w.strip() for w in data.get('watch_words', '').split('\n') if w.strip()],
        'send_type': data.get('send_type', 'manual'),
        'scheduled_time': data.get('scheduled_time', ''),
        'max_retries': int(data.get('max_retries', 5)),
        'auto_reconnect': data.get('auto_reconnect', False)
    })

    if save_settings(user_id, current_settings):
        with USERS_LOCK:
            if user_id in USERS:
                USERS[user_id]['settings'] = current_settings
                # تحديث إعدادات المراقبة في العميل
                client_manager = USERS[user_id].get('client_manager')
                if client_manager and hasattr(client_manager, 'update_monitoring_settings'):
                    client_manager.update_monitoring_settings(
                        current_settings.get('watch_words', []),
                        current_settings.get('groups', [])
                    )

        socketio.emit('log_update', {
            "message": "✅ تم حفظ الإعدادات بنجاح"
        }, to=user_id)

        return jsonify({
            "success": True, 
            "message": "✅ تم حفظ الإعدادات"
        })
    else:
        return jsonify({
            "success": False, 
            "message": "❌ فشل في حفظ الإعدادات"
        })

@app.route("/api/user_logout", methods=["POST"])
def api_user_logout():
    """تسجيل الخروج وإنهاء جلسة التليجرام مع الحفاظ على هوية المستخدم"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({
            "success": False,
            "message": "❌ لا توجد جلسة نشطة"
        })

    try:
        logger.info(f"User {user_id} logging out...")

        with USERS_LOCK:
            if user_id in USERS:
                # إيقاف العميل والمراقبة
                client_manager = USERS[user_id].get('client_manager')
                if client_manager:
                    try:
                        # إيقاف المراقبة أولاً
                        if USERS[user_id].get('is_running'):
                            USERS[user_id]['is_running'] = False

                        # قطع الاتصال وإيقاف العميل
                        if hasattr(client_manager, 'client') and client_manager.client:
                            client_manager.client.disconnect()
                            logger.info(f"Client disconnected for user {user_id}")

                        # إيقاف thread إذا كان يعمل
                        if hasattr(client_manager, 'stop'):
                            client_manager.stop()

                    except Exception as e:
                        logger.error(f"خطأ في إغلاق العميل للمستخدم {user_id}: {e}")

                # حذف بيانات المستخدم من الذاكرة
                del USERS[user_id]
                logger.info(f"User data removed from memory for {user_id}")

        # مسح ملفات جلسة التليجرام
        session_file = os.path.join(SESSIONS_DIR, f"{user_id}_session.session")
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
                logger.info(f"Session file removed for {user_id}")
            except Exception as e:
                logger.error(f"خطأ في حذف ملف الجلسة: {e}")

        # مسح إعدادات المستخدم (اختياري - قد تريد الاحتفاظ بها)
        settings_file = os.path.join(SESSIONS_DIR, f"{user_id}.json")
        if os.path.exists(settings_file):
            try:
                # لا نحذف الإعدادات، نفرغ البيانات الحساسة فقط
                settings = load_settings(user_id)
                settings.update({
                    'phone': '',
                    'authenticated': False,
                    'connected': False
                })
                save_settings(user_id, settings)
                logger.info(f"Settings cleared for {user_id}")
            except Exception as e:
                logger.error(f"خطأ في مسح الإعدادات: {e}")

        # إرسال إشعار مسح الجلسة
        socketio.emit('log_update', {
            "message": "🚪 تم تسجيل الخروج وإنهاء جلسة التليجرام"
        }, to=user_id)

        socketio.emit('connection_status', {
            "status": "disconnected"
        }, to=user_id)

        socketio.emit('login_status', {
            "logged_in": False,
            "connected": False,
            "awaiting_code": False,
            "awaiting_password": False,
            "is_running": False
        }, to=user_id)

        # لا نمسح session.clear() بل نحتفظ بهوية المستخدم
        # session.clear()  - لا نستخدم هذا في النظام الجديد

        logger.info(f"User {user_id} logged out successfully")

        return jsonify({
            "success": True,
            "message": "✅ تم تسجيل الخروج وإنهاء جلسة التليجرام بنجاح"
        })

    except Exception as e:
        logger.error(f"خطأ في تسجيل الخروج للمستخدم {user_id}: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"❌ خطأ في تسجيل الخروج: {str(e)}"
        })

@app.route("/api/get_account_info", methods=["GET"])
def api_get_account_info():
    """جلب معلومات حساب التليجرام للمستخدم الحالي (الاسم/المعرف/الهاتف)"""
    user_id = session.get('user_id', 'user_1')
    try:
        with USERS_LOCK:
            udata = USERS.get(user_id, {})
            cached = {
                "account_name": udata.get('account_name'),
                "account_username": udata.get('account_username'),
                "account_phone": udata.get('account_phone'),
                "authenticated": udata.get('authenticated', False)
            }
        if not cached["account_name"] and cached["authenticated"]:
            try:
                cached["account_name"] = telegram_manager._fetch_account_name(user_id)
                with USERS_LOCK:
                    cached["account_username"] = USERS.get(user_id, {}).get('account_username')
                    cached["account_phone"] = USERS.get(user_id, {}).get('account_phone')
            except Exception as e:
                logger.error(f"get_account_info refresh failed: {e}")
        return jsonify({
            "success": True,
            "user_id": user_id,
            "predefined_name": PREDEFINED_USERS.get(user_id, {}).get('name'),
            **cached
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/switch_user", methods=["POST"])
def api_switch_user():
    """التبديل إلى مستخدم آخر مع الحفاظ على استمرارية العمليات لجميع المستخدمين"""
    try:
        data = request.get_json()
        new_user_id = data.get('user_id')

        if not new_user_id or new_user_id not in PREDEFINED_USERS:
            return jsonify({
                "success": False,
                "message": "❌ مستخدم غير صحيح"
            })

        old_user_id = session.get('user_id', 'user_1')

        # الحفاظ على العمليات المستمرة للمستخدم القديم
        # لا نوقف العمليات الجارية، فقط نحفظ الإعدادات
        if old_user_id in USERS:
            current_settings = USERS[old_user_id].get('settings', {})
            if current_settings:
                save_settings(old_user_id, current_settings)
                logger.info(f"✅ Settings saved for user {old_user_id} - Operations continue running")

        # التأكد من وجود بيانات المستخدم الجديد
        with USERS_LOCK:
            if new_user_id not in USERS:
                # تحميل الإعدادات المحفوظة للمستخدم الجديد
                saved_settings = load_settings(new_user_id)

                # إنشاء بيانات للمستخدم الجديد مع الإعدادات المحفوظة
                USERS[new_user_id] = {
                    'client_manager': None,
                    'settings': saved_settings,
                    'thread': None,
                    'is_running': False,
                    'stats': {"sent": 0, "errors": 0},
                    'connected': False,
                    'authenticated': False,
                    'awaiting_code': False,
                    'awaiting_password': False,
                    'phone_code_hash': None,
                    'monitoring_active': False,
                    'event_handlers_registered': False
                }

                # التحقق من وجود جلسة محفوظة للمستخدم الجديد
                session_file = os.path.join(SESSIONS_DIR, f"{new_user_id}_session.session")
                if os.path.exists(session_file) and saved_settings.get('phone'):
                    USERS[new_user_id]['connected'] = True
                    USERS[new_user_id]['authenticated'] = True
                    logger.info(f"Found existing session for user {new_user_id}")
            else:
                # إعادة تحميل الإعدادات للمستخدم الموجود
                saved_settings = load_settings(new_user_id)
                USERS[new_user_id]['settings'].update(saved_settings)

        # تحديث الجلسة فقط للواجهة
        session['user_id'] = new_user_id
        session.permanent = True

        logger.info(f"✅ User switched from {old_user_id} to {new_user_id} - All operations remain active")

        # عرض حالة العمليات المستمرة
        active_operations_summary = get_all_users_operations_status()

        # إرسال الإعدادات الخاصة بالمستخدم الجديد
        socketio.emit('user_settings', USERS[new_user_id]['settings'], to=new_user_id)

        # محاولة استرجاع/جلب اسم حساب التليجرام للمستخدم الجديد
        account_name = None
        try:
            with USERS_LOCK:
                account_name = USERS[new_user_id].get('account_name')
            if not account_name and USERS[new_user_id].get('authenticated'):
                account_name = telegram_manager._fetch_account_name(new_user_id)
        except Exception as e:
            logger.error(f"Could not load account name on switch: {e}")

        return jsonify({
            "success": True,
            "message": f"✅ تم التبديل إلى {PREDEFINED_USERS[new_user_id]['name']}" + (f" — حساب تليجرام: {account_name}" if account_name else ""),
            "switched": old_user_id != new_user_id,
            "previous_user_id": old_user_id,
            "user": {
                "id": new_user_id,
                "name": PREDEFINED_USERS[new_user_id]['name'],
                "icon": PREDEFINED_USERS[new_user_id]['icon'],
                "color": PREDEFINED_USERS[new_user_id]['color'],
                "account_name": account_name,
                "authenticated": USERS[new_user_id].get('authenticated', False)
            },
            "account_name": account_name,
            "settings": USERS[new_user_id]['settings'],
            "active_operations": active_operations_summary
        })

    except Exception as e:
        logger.error(f"Error in user switching API: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"❌ خطأ في التبديل: {str(e)}"
        })

@app.route("/api/start_monitoring", methods=["POST"])
def api_start_monitoring():
    # التأكد من وجود user_id في الجلسة
    if 'user_id' not in session:
        return jsonify({
            "success": False, 
            "message": "❌ الجلسة غير صالحة، يرجى إعادة تحميل الصفحة"
        })

    user_id = session['user_id']

    with USERS_LOCK:
        if user_id not in USERS:
            return jsonify({
                "success": False, 
                "message": "❌ لم يتم إعداد الحساب"
            })

        if not USERS[user_id].get('authenticated'):
            return jsonify({
                "success": False, 
                "message": "❌ يجب تسجيل الدخول أولاً"
            })

        if USERS[user_id]['is_running']:
            return jsonify({
                "success": False, 
                "message": "✅ النظام يعمل بالفعل"
            })

        USERS[user_id]['is_running'] = True

    socketio.emit('log_update', {
        "message": "🚀 بدء تشغيل نظام المراقبة المحسن مع Event Handlers..."
    }, to=user_id)

    try:
        monitoring_thread = threading.Thread(
            target=monitoring_worker, 
            args=(user_id,), 
            daemon=True
        )
        monitoring_thread.start()

        with USERS_LOCK:
            USERS[user_id]['thread'] = monitoring_thread

        # إرسال تحديث حالة المراقبة للواجهة
        socketio.emit('monitoring_status', {
            "monitoring_active": True,
            "status": "running",
            "is_running": True
        }, to=user_id)

        # إرسال تحديث الأزرار
        socketio.emit('update_monitoring_buttons', {
            "is_running": True
        }, to=user_id)

        return jsonify({
            "success": True, 
            "message": "🚀 بدأت المراقبة المحسنة مع Event Handlers"
        })

    except Exception as e:
        logger.error(f"Failed to start monitoring for {user_id}: {str(e)}")

        with USERS_LOCK:
            USERS[user_id]['is_running'] = False

        return jsonify({
            "success": False, 
            "message": f"❌ فشل في بدء المراقبة: {str(e)}"
        })

@app.route("/api/stop_monitoring", methods=["POST"])
def api_stop_monitoring():
    # التأكد من وجود user_id في الجلسة
    if 'user_id' not in session:
        return jsonify({
            "success": False, 
            "message": "❌ الجلسة غير صالحة، يرجى إعادة تحميل الصفحة"
        })

    user_id = session['user_id']

    with USERS_LOCK:
        if user_id in USERS and USERS[user_id]['is_running']:
            USERS[user_id]['is_running'] = False
            socketio.emit('log_update', {
                "message": "⏹ إيقاف نظام المراقبة..."
            }, to=user_id)

            # إرسال تحديث حالة المراقبة للواجهة
            socketio.emit('monitoring_status', {
                "monitoring_active": False,
                "status": "stopped",
                "is_running": False
            }, to=user_id)

            # إرسال تحديث الأزرار
            socketio.emit('update_monitoring_buttons', {
                "is_running": False
            }, to=user_id)

            return jsonify({
                "success": True, 
                "message": "⏹ تم إيقاف المراقبة"
            })

    return jsonify({
        "success": False, 
        "message": "❌ النظام غير مشغل"
    })

@app.route("/api/send_now", methods=["POST"])
def api_send_now():
    # التأكد من وجود user_id في الجلسة
    if 'user_id' not in session:
        return jsonify({
            "success": False, 
            "message": "❌ الجلسة غير صالحة، يرجى إعادة تحميل الصفحة"
        })

    user_id = session['user_id']

    with USERS_LOCK:
        if user_id not in USERS:
            return jsonify({
                "success": False, 
                "message": "❌ لم يتم إعداد الحساب"
            })

        if not USERS[user_id].get('authenticated'):
            return jsonify({
                "success": False, 
                "message": "❌ يجب تسجيل الدخول أولاً"
            })

    # قراءة البيانات من الطلب المرسل من JavaScript
    data = request.get_json()
    if not data:
        return jsonify({
            "success": False, 
            "message": "❌ لا توجد بيانات مرسلة"
        })

    message = data.get('message', '').strip()
    groups = data.get('groups', '').strip()
    images = data.get('images', [])

    # التحقق من وجود محتوى للإرسال
    if not message and not images:
        return jsonify({
            "success": False, 
            "message": "❌ يجب كتابة رسالة أو رفع صورة للإرسال"
        })

    if not groups:
        return jsonify({
            "success": False, 
            "message": "❌ يجب تحديد المجموعات للإرسال إليها"
        })

    # تحويل النص إلى قائمة مجموعات
    groups_list = [g.strip() for g in groups.replace('\n', ',').split(',') if g.strip()]

    if not groups_list:
        return jsonify({
            "success": False, 
            "message": "❌ يجب تحديد مجموعة واحدة على الأقل"
        })

    # تحضير الصور إذا وجدت
    image_files = []
    if images:
        try:
            import base64
            import tempfile

            for img_data in images:
                # استخراج البيانات من Base64
                base64_data = img_data['data'].split(',')[1]  # إزالة البادئة
                image_bytes = base64.b64decode(base64_data)

                # إنشاء ملف مؤقت
                temp_file = tempfile.NamedTemporaryFile(delete=False, 
                                                     suffix=f".{img_data['type'].split('/')[-1]}")
                temp_file.write(image_bytes)
                temp_file.flush()

                image_files.append({
                    'path': temp_file.name,
                    'name': img_data['name'],
                    'type': img_data['type']
                })

            socketio.emit('log_update', {
                "message": f"📷 تم تحضير {len(image_files)} صورة للإرسال"
            }, to=user_id)

        except Exception as e:
            logger.error(f"Error processing images: {str(e)}")
            return jsonify({
                "success": False,
                "message": f"❌ خطأ في معالجة الصور: {str(e)}"
            })

    content_type = "رسالة"
    if images and message:
        content_type = f"رسالة مع {len(images)} صورة"
    elif images:
        content_type = f"{len(images)} صورة"

    socketio.emit('log_update', {
        "message": f"🚀 بدء الإرسال الفوري: {content_type} إلى {len(groups_list)} مجموعة"
    }, to=user_id)

    def send_messages_with_images():
        try:
            successful = 0
            failed = 0

            for i, group in enumerate(groups_list, 1):
                try:
                    if images and message:
                        # إرسال الصور مع النص
                        result = telegram_manager.send_message_with_media_async(
                            user_id, group, message, image_files
                        )
                    elif images:
                        # إرسال الصور فقط
                        result = telegram_manager.send_media_async(
                            user_id, group, image_files
                        )
                    else:
                        # إرسال النص فقط
                        result = telegram_manager.send_message_async(user_id, group, message)

                    socketio.emit('log_update', {
                        "message": f"✅ [{i}/{len(groups_list)}] نجح إلى: {group}"
                    }, to=user_id)

                    successful += 1
                    with USERS_LOCK:
                        if user_id in USERS:
                            USERS[user_id]['stats']['sent'] += 1

                    socketio.emit('stats_update', USERS[user_id]['stats'], to=user_id)

                    if i < len(groups_list):
                        time.sleep(3)

                except Exception as e:
                    error_msg = str(e)
                    if "banned" in error_msg.lower():
                        error_type = "محظور"
                    elif "private" in error_msg.lower():
                        error_type = "خاص/محدود"
                    elif "can't write" in error_msg.lower():
                        error_type = "غير مسموح"
                    else:
                        error_type = "خطأ"

                    logger.error(f"Send error to {group}: {error_msg}")
                    socketio.emit('log_update', {
                        "message": f"❌ [{i}/{len(groups_list)}] فشل إلى {group}: {error_type}"
                    }, to=user_id)

                    failed += 1
                    with USERS_LOCK:
                        if user_id in USERS:
                            USERS[user_id]['stats']['errors'] += 1

                    socketio.emit('stats_update', USERS[user_id]['stats'], to=user_id)

            # ملخص نهائي
            socketio.emit('log_update', {
                "message": f"📊 انتهى الإرسال: ✅ {successful} نجح | ❌ {failed} فشل"
            }, to=user_id)

        except Exception as e:
            logger.error(f"Send thread error: {str(e)}")
        finally:
            # تنظيف الملفات المؤقتة
            for img_file in image_files:
                try:
                    if os.path.exists(img_file['path']):
                        os.unlink(img_file['path'])
                        logger.info(f"Cleaned up temp file: {img_file['name']}")
                except Exception as e:
                    logger.error(f"Error cleaning temp file {img_file.get('name', 'unknown')}: {str(e)}")

    threading.Thread(target=send_messages_with_images, daemon=True).start()

    return jsonify({
        "success": True, 
        "message": f"🚀 بدأ إرسال {content_type} لـ {len(groups_list)} مجموعة"
    })

@app.route("/api/get_stats", methods=["GET"])
def api_get_stats():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"sent": 0, "errors": 0})

    with USERS_LOCK:
        if user_id in USERS:
            return jsonify(USERS[user_id]['stats'])

    return jsonify({"sent": 0, "errors": 0})

@app.route("/api/get_login_status", methods=["GET"])
def api_get_login_status():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"logged_in": False, "connected": False})

    with USERS_LOCK:
        if user_id in USERS:
            # التحقق من وجود جلسة محفوظة وعميل متصل
            user_data = USERS[user_id]
            client_manager = user_data.get('client_manager')
            authenticated = user_data.get('authenticated', False)
            connected = user_data.get('connected', False)

            # تحقق إضافي من وجود جلسة محفوظة إذا لم يكن authenticated
            if not authenticated and 'settings' in user_data and 'phone' in user_data['settings']:
                session_file = os.path.join(SESSIONS_DIR, f"{user_id}_session.session")
                if os.path.exists(session_file):
                    # يوجد ملف جلسة محفوظ، اعتبر المستخدم مسجل دخول
                    authenticated = True
                    connected = True
                    # تحديث حالة المستخدم
                    USERS[user_id]['authenticated'] = True
                    USERS[user_id]['connected'] = True

            return jsonify({
                "logged_in": authenticated, 
                "connected": connected,
                "is_running": user_data.get('is_running', False)
            })

    return jsonify({"logged_in": False, "connected": False, "is_running": False})

@app.route("/api/get_user_info", methods=["GET"])
def api_get_user_info():
    """جلب معلومات المستخدم الحالي"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"success": False, "message": "غير مسجل دخول"})

    with USERS_LOCK:
        if user_id in USERS and 'settings' in USERS[user_id]:
            settings = USERS[user_id]['settings']
            return jsonify({
                "success": True,
                "phone": settings.get('phone', ''),
                "name": settings.get('name', ''),
                "user_id": user_id[:8] + "..."  # عرض جزء من معرف المستخدم للأمان
            })

    return jsonify({"success": False, "message": "لم يتم العثور على معلومات المستخدم"})

@app.route("/api/resend_code", methods=["POST"])
def api_resend_code():
    """إعادة إرسال كود التحقق (اختياري عبر SMS)"""
    try:
        if 'user_id' not in session:
            return jsonify({"success": False, "message": "❌ الجلسة غير صالحة"})
        user_id = session['user_id']
        data = request.json or {}
        force_sms = bool(data.get('force_sms', False))

        with USERS_LOCK:
            if user_id not in USERS:
                return jsonify({"success": False, "message": "❌ يرجى البدء بإدخال رقم الهاتف أولاً"})
            client_manager = USERS[user_id].get('client_manager')
            settings = USERS[user_id].get('settings', {})
            phone = settings.get('phone')

        if not client_manager or not client_manager.client or not phone:
            return jsonify({"success": False, "message": "❌ لم يتم إعداد العميل"})

        sent = client_manager.run_coroutine(
            client_manager.client.send_code_request(phone, force_sms=force_sms)
        )
        with USERS_LOCK:
            if user_id in USERS:
                USERS[user_id]['awaiting_code'] = True
                USERS[user_id]['phone_code_hash'] = sent.phone_code_hash

        msg = "📱 تم إعادة الإرسال عبر SMS" if force_sms else "📱 تم إعادة إرسال الكود"
        socketio.emit('log_update', {"message": msg}, to=user_id)
        return jsonify({"success": True, "message": msg})
    except Exception as e:
        logger.error(f"Resend code error: {str(e)}")
        return jsonify({"success": False, "message": f"❌ {str(e)}"})

@app.route("/api/reset_login", methods=["POST"])
def api_reset_login():
    """إعادة تعيين جلسة تسجيل الدخول للمستخدم الحالي"""
    user_id = session.get('user_id', 'user_1')

    if user_id not in PREDEFINED_USERS:
        return jsonify({
            "success": False,
            "message": "❌ مستخدم غير صحيح"
        })

    try:
        logger.info(f"Resetting login for user {user_id}")

        with USERS_LOCK:
            if user_id in USERS:
                # إيقاف المراقبة إذا كانت تعمل
                if USERS[user_id].get('is_running', False):
                    USERS[user_id]['is_running'] = False

                # إيقاف العميل
                client_manager = USERS[user_id].get('client_manager')
                if client_manager:
                    try:
                        if hasattr(client_manager, 'stop'):
                            client_manager.stop()
                        if hasattr(client_manager, 'client') and client_manager.client:
                            client_manager.client.disconnect()
                        logger.info(f"Client stopped and disconnected for user {user_id}")
                    except Exception as e:
                        logger.error(f"Error stopping client for {user_id}: {e}")

                # حذف بيانات المستخدم من الذاكرة
                del USERS[user_id]
                logger.info(f"User data removed from memory for {user_id}")

        # مسح ملف جلسة التليجرام
        session_file = os.path.join(SESSIONS_DIR, f"{user_id}_session.session")
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
                logger.info(f"Session file removed for {user_id}")
            except Exception as e:
                logger.error(f"Failed to remove session file for {user_id}: {str(e)}")

        # إرسال إشعارات التحديث
        socketio.emit('log_update', {
            "message": f"🔄 تم إعادة تعيين جلسة تسجيل الدخول لـ {PREDEFINED_USERS[user_id]['name']}"
        }, to=user_id)

        socketio.emit('connection_status', {
            "status": "disconnected"
        }, to=user_id)

        socketio.emit('login_status', {
            "logged_in": False,
            "connected": False,
            "awaiting_code": False,
            "awaiting_password": False,
            "is_running": False
        }, to=user_id)

        logger.info(f"Login reset completed for user {user_id}")

        return jsonify({
            "success": True, 
            "message": f"✅ تم إعادة تعيين جلسة {PREDEFINED_USERS[user_id]['name']} بنجاح"
        })

    except Exception as e:
        logger.error(f"Error resetting login for {user_id}: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"❌ خطأ في إعادة التعيين: {str(e)}"
        })

# =========================== 
# Keep-Alive API
# ===========================
@app.route("/api/keep_alive_status", methods=["GET"])
def api_keep_alive_status():
    """الحصول على حالة نظام Keep-Alive"""
    try:
        from keep_alive import get_keep_alive_status
        status = get_keep_alive_status()
        return jsonify({
            "success": True,
            "status": status
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"خطأ: {str(e)}"
        })

@app.route("/api/system_health", methods=["GET"])
def api_system_health():
    """فحص صحة النظام"""
    try:
        import psutil

        # معلومات الذاكرة
        memory = psutil.virtual_memory()

        # معلومات القرص
        disk = psutil.disk_usage('/')

        # معلومات الـ CPU
        cpu_percent = psutil.cpu_percent(interval=1)

        # معلومات الشبكة
        network = psutil.net_io_counters()

        health_info = {
            'memory': {
                'total': memory.total,
                'available': memory.available,
                'percent': memory.percent,
                'used': memory.used
            },
            'disk': {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percent': (disk.used / disk.total) * 100
            },
            'cpu': {
                'percent': cpu_percent,
                'count': psutil.cpu_count()
            },
            'network': {
                'bytes_sent': network.bytes_sent,
                'bytes_recv': network.bytes_recv
            },
            'timestamp': time.time()
        }

        return jsonify({
            "success": True,
            "health": health_info
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"خطأ: {str(e)}"
        })


# =========================== 
# نظام الانضمام التلقائي للمجموعات (الموجود أصلاً)
# ===========================

def extract_telegram_links(text):
    """استخراج روابط التليجرام من النص مع التنظيف والفلترة"""
    if not text:
        return []

    # أنماط شاملة لروابط التليجرام
    patterns = [
        # روابط عادية
        r'https?://t\.me/([a-zA-Z0-9_]+)(?:/\d+)?',           # https://t.me/channel أو https://t.me/channel/123
        r'https?://telegram\.me/([a-zA-Z0-9_]+)(?:/\d+)?',    # https://telegram.me/channel

        # روابط الدعوة
        r'https?://t\.me/\+([a-zA-Z0-9_\-]+)',                # https://t.me/+inviteHash
        r'https?://telegram\.me/\+([a-zA-Z0-9_\-]+)',         # https://telegram.me/+inviteHash

        # روابط بدون بروتوكول
        r't\.me/([a-zA-Z0-9_]+)',                             # t.me/channel
        r't\.me/\+([a-zA-Z0-9_\-]+)',                        # t.me/+inviteHash
        r'telegram\.me/([a-zA-Z0-9_]+)',                      # telegram.me/channel

        # أسماء المستخدمين والقنوات
        r'@([a-zA-Z0-9_]{5,})',                              # @channel (أكثر من 4 أحرف)
    ]

    found_links = set()

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            clean_match = match if isinstance(match, str) else match[0] if match else ''

            # تنسيق الرابط
            if pattern.startswith(r'@'):
                # اسم المستخدم
                clean_link = f"https://t.me/{clean_match}"
            elif '+' in clean_match or pattern.find(r'\+') != -1:
                # رابط دعوة
                clean_link = f"https://t.me/+{clean_match.replace('+', '')}"
            elif clean_match and not clean_match.startswith('http'):
                # رابط بدون بروتوكول
                clean_link = f"https://t.me/{clean_match}"
            elif clean_match.startswith('http'):
                # رابط كامل
                clean_link = f"https://t.me/{clean_match.split('/')[-1]}"
            else:
                clean_link = clean_match

            # التحقق من صحة الرابط
            if clean_link and len(clean_link) > 15:  # على الأقل https://t.me/x
                # إزالة أي معاملات إضافية
                clean_link = clean_link.split('?')[0].split('#')[0]
                found_links.add(clean_link)

    # تحويل إلى قائمة مع ترتيب
    links_list = sorted(list(found_links))

    # إنشاء كائنات الروابط مع معلومات إضافية
    result_links = []
    for link in links_list:
        username = link.split('/')[-1].replace('@', '')
        result_links.append({
            'url': link,
            'username': username,
            'type': 'invite' if '+' in link else 'channel'
        })

    return result_links

async def join_telegram_group(client, group_link, user_id=None, client_manager=None):
    """الانضمام لمجموعة تليجرام مع إمكانية إرسال روابط الاستئناف في حالة الحظر"""
    try:
        # تنظيف الرابط
        if group_link.startswith('https://t.me/'):
            group_identifier = group_link.replace('https://t.me/', '')
        elif group_link.startswith('https://telegram.me/'):
            group_identifier = group_link.replace('https://telegram.me/', '')
        elif group_link.startswith('@'):
            group_identifier = group_link[1:]
        else:
            group_identifier = group_link

        # محاولة الانضمام
        try:
            entity = await client.get_entity(group_identifier)
            if hasattr(entity, 'megagroup') or hasattr(entity, 'broadcast'):
                result = await client(functions.channels.JoinChannelRequest(entity))
            else:
                raise Exception("مجموعة عادية - يجب استخدام رابط دعوة")

            return {
                "success": True,
                "already_joined": False,
                "message": "تم الانضمام بنجاح"
            }

        except UserAlreadyParticipantError:
            return {
                "success": True,
                "already_joined": True,
                "message": "منضم مسبقاً للمجموعة"
            }

        except FloodWaitError as e:
            return {
                "success": False,
                "message": f"يرجى الانتظار {e.seconds} ثانية"
            }

        except InviteHashExpiredError:
            return {
                "success": False,
                "message": "انتهت صلاحية رابط الدعوة"
            }

        except InviteHashInvalidError:
            return {
                "success": False,
                "message": "رابط الدعوة غير صحيح"
            }

        except Exception as group_error:
            error_str = str(group_error).lower()
            appeal_url = None
            appeal_note = ""

            # كشف أنواع الحظر المختلفة
            if "cas" in error_str or "combot" in error_str:
                appeal_url = "https://cas.chat/appeal"
                appeal_note = "تم حظرك بواسطة CAS (Combot Anti-Spam). توجه إلى الرابط أعلاه لتقديم استئناف."
            elif "spamwatch" in error_str:
                appeal_url = "https://spamwat.ch/appeal"
                appeal_note = "تم حظرك بواسطة SpamWatch. استخدم الرابط أعلاه للاستئناف."
            elif "shieldy" in error_str:
                appeal_url = "https://t.me/Shieldy_Bot?start=appeal"
                appeal_note = "تم حظرك بواسطة Shieldy. افتح البوت في الخاص لطلب فك الحظر."
            elif "rose" in error_str or "missrose" in error_str:
                appeal_url = "https://t.me/MissRose_Bot?start=appeal"
                appeal_note = "تم حظرك بواسطة Rose. أرسل /start إلى البوت ثم اتبع التعليمات."
            elif "groupguard" in error_str:
                appeal_url = "https://t.me/GroupGuardBot?start=appeal"
                appeal_note = "تم حظرك بواسطة GroupGuard. اتصل بالبوت."
            elif "antispam" in error_str or "spam" in error_str:
                appeal_url = "https://t.me/SpamBot"
                appeal_note = "قد يكون حسابك مصنفاً كسبام. تواصل مع @SpamBot للتحقق."
            else:
                if "banned" in error_str or "blocked" in error_str or "forbidden" in error_str:
                    appeal_url = "https://t.me/SpamBot"
                    appeal_note = "حسابك ربما محظور من الانضمام. جرب التواصل مع @SpamBot أو مشرف المجموعة."

            # إذا تم التعرف على رابط استئناف، أرسله إلى Saved Messages
            if appeal_url and user_id and client_manager:
                message_text = f"""🚫 **فشل الانضمام إلى المجموعة** 🚫

**الرابط:** {group_link}
**السبب:** {error_str[:200]}

**إجراء مقترح للاستئناف:**
{appeal_note}
🔗 **رابط الاستئناف:** {appeal_url}

يرجى فتح الرابط ومتابعة التعليمات لرفع الحظر. بعد إلغاء الحظر، يمكنك إعادة المحاولة.
"""
                try:
                    await client_manager.send_to_saved_messages(message_text)
                except Exception as save_err:
                    logger.error(f"Could not send appeal to saved messages: {save_err}")

            # محاولة أخرى مع تعديل الرابط (رابط دعوة)
            try:
                if '/' in group_identifier:
                    result = await client(functions.messages.ImportChatInviteRequest(group_identifier.split('/')[-1]))
                    return {
                        "success": True,
                        "already_joined": False,
                        "message": "تم الانضمام عبر رابط الدعوة"
                    }
                else:
                    raise group_error
            except UserAlreadyParticipantError:
                return {
                    "success": True,
                    "already_joined": True,
                    "message": "منضم مسبقاً للمجموعة"
                }
            except Exception as final_error:
                return {
                    "success": False,
                    "message": f"فشل الانضمام: {str(final_error)}",
                    "appeal_url": appeal_url
                }

    except Exception as e:
        return {
            "success": False,
            "message": f"خطأ: {str(e)}"
        }

# =========================== 
# API للانضمام التلقائي (الموجودة أصلاً)
# ===========================
@app.route("/api/extract_group_links", methods=["POST"])
def api_extract_group_links():
    """استخراج روابط المجموعات من النص"""
    try:
        data = request.json
        if not data or not data.get('text'):
            return jsonify({
                "success": False,
                "message": "❌ لم يتم إرسال النص"
            })

        text = data.get('text', '')
        links = extract_telegram_links(text)

        return jsonify({
            "success": True,
            "links": links,
            "count": len(links),
            "message": f"✅ تم استخراج {len(links)} رابط"
        })

    except Exception as e:
        logger.error(f"Error extracting links: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"❌ خطأ: {str(e)}"
        })

@app.route("/api/join_group", methods=["POST"])
def api_join_group():
    """الانضمام لمجموعة واحدة"""
    try:
        user_id = session.get('user_id', 'user_1')

        if user_id not in PREDEFINED_USERS:
            return jsonify({
                "success": False,
                "message": "❌ مستخدم غير صحيح"
            })

        data = request.json

        if not data or not data.get('group_link'):
            return jsonify({
                "success": False,
                "message": "❌ لم يتم إرسال رابط المجموعة"
            })

        group_link_raw = data.get('group_link', '')
        if isinstance(group_link_raw, dict):
            # إذا كان group_link عبارة عن dict، استخرج الرابط منه
            group_link = group_link_raw.get('url', '') or group_link_raw.get('link', '') or str(group_link_raw)
        else:
            group_link = str(group_link_raw)

        group_link = group_link.strip()

        with USERS_LOCK:
            if user_id not in USERS:
                return jsonify({
                    "success": False,
                    "message": f"❌ المستخدم {PREDEFINED_USERS[user_id]['name']} غير مسجل"
                })

            client_manager = USERS[user_id].get('client_manager')
            if not client_manager or not client_manager.client:
                return jsonify({
                    "success": False,
                    "message": "❌ يرجى تسجيل الدخول أولاً"
                })

        # تشغيل عملية الانضمام
        result = client_manager.run_coroutine(
            join_telegram_group(client_manager.client, group_link, user_id, client_manager)
        )

        # تسجيل النتيجة
        socketio.emit('log_update', {
            "message": f"{'✅' if result['success'] else '❌'} {group_link}: {result['message']}"
        }, to=user_id)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error joining group: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"❌ خطأ: {str(e)}"
        })

@app.route("/api/start_auto_join", methods=["POST"])
def api_start_auto_join():
    """بدء الانضمام التلقائي المتعدد للمجموعات"""
    try:
        user_id = session.get('user_id', 'user_1')

        if user_id not in PREDEFINED_USERS:
            return jsonify({
                "success": False,
                "message": "❌ مستخدم غير صحيح"
            })

        data = request.json
        if not data or not data.get('links'):
            return jsonify({
                "success": False,
                "message": "❌ لم يتم إرسال روابط المجموعات"
            })

        links = data.get('links', [])
        delay = data.get('delay', 3)  # تأخير افتراضي 3 ثواني

        if not links:
            return jsonify({
                "success": False,
                "message": "❌ لا توجد روابط للانضمام إليها"
            })

        with USERS_LOCK:
            if user_id not in USERS:
                return jsonify({
                    "success": False,
                    "message": f"❌ المستخدم {PREDEFINED_USERS[user_id]['name']} غير مسجل"
                })

            client_manager = USERS[user_id].get('client_manager')
            if not client_manager or not client_manager.client:
                return jsonify({
                    "success": False,
                    "message": "❌ يرجى تسجيل الدخول أولاً"
                })

        # بدء عملية الانضمام التلقائي في thread منفصل
        import threading

        def auto_join_worker():
            success_count = 0
            fail_count = 0
            already_joined_count = 0

            socketio.emit('log_update', {
                "message": f"🚀 بدء الانضمام التلقائي لـ {len(links)} مجموعة..."
            }, to=user_id)

            for i, link_obj in enumerate(links):
                try:
                    # الحصول على الرابط
                    if isinstance(link_obj, dict):
                        group_link = link_obj.get('url', '') or link_obj.get('link', '') or str(link_obj)
                    else:
                        group_link = str(link_obj)

                    group_link = group_link.strip()

                    # إرسال حالة التقدم
                    socketio.emit('join_progress', {
                        'current': i + 1,
                        'total': len(links),
                        'link': group_link
                    }, to=user_id)

                    # محاولة الانضمام
                    result = client_manager.run_coroutine(
                        join_telegram_group(client_manager.client, group_link, user_id, client_manager)
                    )

                    if result['success']:
                        if result.get('already_joined', False):
                            already_joined_count += 1
                            socketio.emit('log_update', {
                                "message": f"ℹ️ منضم مسبقاً: {group_link}"
                            }, to=user_id)
                        else:
                            success_count += 1
                            socketio.emit('log_update', {
                                "message": f"✅ تم الانضمام: {group_link}"
                            }, to=user_id)
                    else:
                        fail_count += 1
                        socketio.emit('log_update', {
                            "message": f"❌ فشل: {group_link} - {result['message']}"
                        }, to=user_id)

                    # تحديث الإحصائيات
                    socketio.emit('join_stats', {
                        'success': success_count,
                        'fail': fail_count,
                        'already_joined': already_joined_count
                    }, to=user_id)

                    # تأخير بين المجموعات لتجنب flood
                    if i < len(links) - 1:  # لا نؤخر بعد آخر مجموعة
                        time.sleep(delay)

                except Exception as e:
                    fail_count += 1
                    socketio.emit('log_update', {
                        "message": f"❌ خطأ في {group_link}: {str(e)}"
                    }, to=user_id)

            # إرسال النتيجة النهائية
            socketio.emit('auto_join_completed', {
                'success': success_count,
                'fail': fail_count,
                'already_joined': already_joined_count,
                'total': len(links)
            }, to=user_id)

            socketio.emit('log_update', {
                "message": f"🎉 انتهى الانضمام التلقائي! النجح: {success_count}, فشل: {fail_count}, منضم مسبقاً: {already_joined_count}"
            }, to=user_id)

        # تشغيل العملية في thread منفصل
        thread = threading.Thread(target=auto_join_worker, daemon=True)
        thread.start()

        return jsonify({
            "success": True,
            "message": f"✅ تم بدء الانضمام التلقائي لـ {len(links)} مجموعة",
            "total_links": len(links)
        })

    except Exception as e:
        logger.error(f"Error starting auto join: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"❌ خطأ في بدء الانضمام التلقائي: {str(e)}"
        })

# ==========================
# APIs البحث عن الروابط (الموجودة أصلاً)
# ==========================

import re
from datetime import datetime, timedelta
from telethon.tl.types import Channel, Chat, User
from telethon.tl.functions.contacts import SearchRequest, ResolveUsernameRequest
from telethon.tl.functions.messages import SearchGlobalRequest

def extract_telegram_links(text):
    """استخراج روابط التليجرام من النص"""
    if not text:
        return []

    # أنماط الروابط المختلفة (شامل وقوي)
    patterns = [
        # روابط عادية
        r'https?://t\.me/([a-zA-Z0-9_]+)',           # https://t.me/channel
        r'https?://telegram\.me/([a-zA-Z0-9_]+)',    # https://telegram.me/channel

        # روابط الدعوة (invite links)
        r'https?://t\.me/\+([a-zA-Z0-9_\-]+)',       # https://t.me/+inviteHash
        r'https?://telegram\.me/\+([a-zA-Z0-9_\-]+)', # https://telegram.me/+inviteHash

        # روابط الرسائل في القنوات الخاصة
        r'https?://t\.me/c/(\d+)/(\d+)',             # https://t.me/c/channelid/messageid
        r'https?://telegram\.me/c/(\d+)/(\d+)',      # https://telegram.me/c/channelid/messageid

        # روابط الرسائل في القنوات العامة
        r'https?://t\.me/([a-zA-Z0-9_]+)/(\d+)',     # https://t.me/channel/messageid
        r'https?://telegram\.me/([a-zA-Z0-9_]+)/(\d+)', # https://telegram.me/channel/messageid

        # ذكر المستخدمين والقنوات
        r'@([a-zA-Z0-9_]+)',                         # @channel

        # روابط بدون بروتوكول
        r't\.me/([a-zA-Z0-9_]+)',                    # t.me/channel
        r't\.me/\+([a-zA-Z0-9_\-]+)',               # t.me/+inviteHash
        r'telegram\.me/([a-zA-Z0-9_]+)',             # telegram.me/channel
        r'telegram\.me/\+([a-zA-Z0-9_\-]+)',        # telegram.me/+inviteHash
    ]

    links = []
    seen_urls = set()

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                # التعامل مع التطابقات المتعددة (مثل channel/message)
                if len(match) == 2 and match[1].isdigit():
                    # رابط رسالة
                    if pattern.startswith(r'https?://t\.me/c/'):
                        clean_link = f"https://t.me/c/{match[0]}/{match[1]}"
                        username = f"c/{match[0]}"
                    else:
                        clean_link = f"https://t.me/{match[0]}/{match[1]}"
                        username = match[0]
                else:
                    # رابط دعوة أو قناة خاصة
                    if '+' in str(match[0]) or 'c/' in str(match[0]):
                        clean_link = f"https://t.me/+{match[0]}" if not match[0].startswith('c/') else f"https://t.me/c/{match[0]}"
                        username = match[0]
                    else:
                        clean_link = f"https://t.me/{match[0]}"
                        username = match
            else:
                # تطابق واحد
                if match.startswith('+'):
                    # رابط دعوة
                    clean_link = f"https://t.me/{match}"
                    username = match[1:]  # إزالة علامة +
                elif match.startswith('@'):
                    # ذكر مستخدم/قناة
                    clean_link = f"https://t.me/{match[1:]}"
                    username = match[1:]
                else:
                    # قناة أو مستخدم عادي
                    clean_link = f"https://t.me/{match}"
                    username = match

            # تجنب التكرار
            if clean_link not in seen_urls:
                seen_urls.add(clean_link)
                links.append({
                    'url': clean_link,
                    'original_text': text[:200] + ('...' if len(text) > 200 else ''),
                    'username': username.replace('@', '') if isinstance(username, str) else str(username)
                })

    return links

@app.route("/api/search_my_links", methods=["POST"])
def api_search_my_links():
    """البحث عن روابط التليجرام في محادثات المستخدم"""
    try:
        if 'user_id' not in session:
            return jsonify({
                "success": False,
                "message": "❌ يرجى تسجيل الدخول أولاً"
            })

        user_id = session['user_id']
        data = request.json

        # الحصول على عدد الأيام (افتراضي: شهرين)
        days = data.get('days', 60)
        if days <= 0 or days > 365:  # حد أقصى سنة واحدة
            days = 60

        with USERS_LOCK:
            if user_id not in USERS:
                return jsonify({
                    "success": False,
                    "message": "❌ المستخدم غير مسجل"
                })

            client_manager = USERS[user_id].get('client_manager')
            if not client_manager or not client_manager.client:
                return jsonify({
                    "success": False,
                    "message": "❌ يرجى تسجيل الدخول أولاً"
                })

        logger.info(f"🔍 بدء البحث عن الروابط للمستخدم {user_id} لمدة {days} يوم")

        # حساب التاريخ المحدد
        since_date = datetime.now() - timedelta(days=days)

        # تشغيل البحث
        result = client_manager.run_coroutine(
            search_links_in_chats(client_manager.client, since_date)
        )

        logger.info(f"✅ تم العثور على {len(result)} رابط للمستخدم {user_id}")

        return jsonify({
            "success": True,
            "links": result,
            "message": f"تم العثور على {len(result)} رابط"
        })

    except Exception as e:
        logger.error(f"خطأ في البحث عن الروابط: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"❌ خطأ في البحث: {str(e)}"
        })

async def search_links_in_chats(client, since_date):
    """البحث عن الروابط في جميع المحادثات"""
    found_links = []

    try:
        # الحصول على جميع المحادثات
        async for dialog in client.iter_dialogs():
            try:
                # تخطي المحادثات المحذوفة
                if not dialog.entity:
                    continue

                chat_title = dialog.title or "محادثة غير معروفة"

                # البحث في رسائل هذه المحادثة
                async for message in client.iter_messages(
                    dialog, 
                    offset_date=since_date,
                    limit=1000  # حد أقصى لتجنب التحميل المفرط
                ):
                    if message.text:
                        # استخراج الروابط من النص
                        links = extract_telegram_links(message.text)

                        for link in links:
                            # الحصول على معلومات القناة إن أمكن
                            title = await get_channel_title(client, link['username'])

                            found_links.append({
                                'url': link['url'],
                                'title': title or link['username'],
                                'date': message.date.strftime('%Y-%m-%d %H:%M'),
                                'chat_title': chat_title,
                                'original_text': link['original_text']
                            })

                # حد أقصى للمحادثات المفحوصة لتجنب الإبطاء
                if len(found_links) > 500:
                    break

            except Exception as e:
                logger.warning(f"تخطي محادثة بسبب خطأ: {str(e)}")
                continue

    except Exception as e:
        logger.error(f"خطأ في البحث عن الروابط: {str(e)}")

    # إزالة الروابط المكررة وترتيبها حسب التاريخ
    unique_links = []
    seen_urls = set()

    for link in found_links:
        if link['url'] not in seen_urls:
            seen_urls.add(link['url'])
            unique_links.append(link)

    # ترتيب حسب التاريخ (الأحدث أولاً)
    unique_links.sort(key=lambda x: x['date'], reverse=True)

    return unique_links

async def get_channel_title(client, username):
    """الحصول على عنوان القناة من username"""
    try:
        if username.startswith('@'):
            username = username[1:]

        entity = await client.get_entity(username)
        return entity.title if hasattr(entity, 'title') else username
    except Exception:
        return None

@app.route("/api/search_public_channels", methods=["POST"])
def api_search_public_channels():
    """البحث العام في التليجرام عن القنوات والمجموعات"""
    try:
        if 'user_id' not in session:
            return jsonify({
                "success": False,
                "message": "❌ يرجى تسجيل الدخول أولاً"
            })

        user_id = session['user_id']
        data = request.json

        query = data.get('query', '').strip()
        if not query:
            return jsonify({
                "success": False,
                "message": "❌ يرجى كتابة نص للبحث"
            })

        # تحديد عدد النتائج المطلوبة
        limit = min(data.get('limit', 50), 100)  # حد أقصى 100

        with USERS_LOCK:
            if user_id not in USERS:
                return jsonify({
                    "success": False,
                    "message": "❌ المستخدم غير مسجل"
                })

            client_manager = USERS[user_id].get('client_manager')
            if not client_manager or not client_manager.client:
                return jsonify({
                    "success": False,
                    "message": "❌ يرجى تسجيل الدخول أولاً"
                })

        logger.info(f"🌐 بدء البحث العام للمستخدم {user_id} عن: {query}")

        # تشغيل البحث العام
        result = client_manager.run_coroutine(
            search_public_telegram(client_manager.client, query, limit)
        )

        logger.info(f"✅ تم العثور على {len(result)} قناة/مجموعة للمستخدم {user_id}")

        return jsonify({
            "success": True,
            "channels": result,
            "message": f"تم العثور على {len(result)} قناة/مجموعة"
        })

    except Exception as e:
        logger.error(f"خطأ في البحث العام: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"❌ خطأ في البحث: {str(e)}"
        })

async def search_public_telegram(client, query, limit=50):
    """البحث العام في التليجرام"""
    results = []

    try:
        # البحث العام باستخدام SearchGlobalRequest
        global_search = await client(SearchGlobalRequest(
            q=query,
            offset_date=None,
            offset_peer=None,
            offset_id=0,
            limit=limit
        ))

        # معالجة النتائج
        for message in global_search.messages:
            if hasattr(message, 'peer_id') and hasattr(message.peer_id, 'channel_id'):
                # البحث عن القناة في الكيانات
                channel_id = message.peer_id.channel_id

                for chat in global_search.chats:
                    if hasattr(chat, 'id') and chat.id == channel_id:
                        if isinstance(chat, Channel):
                            username = chat.username if hasattr(chat, 'username') else None

                            result_item = {
                                'id': str(chat.id),
                                'title': chat.title,
                                'username': username,
                                'participants_count': getattr(chat, 'participants_count', 0),
                                'megagroup': getattr(chat, 'megagroup', False),
                                'verified': getattr(chat, 'verified', False),
                                'scam': getattr(chat, 'scam', False)
                            }

                            # تجنب التكرار
                            if not any(r['id'] == result_item['id'] for r in results):
                                results.append(result_item)

        # بحث إضافي بطرق أخرى إذا كانت النتائج قليلة
        if len(results) < 10:
            try:
                # محاولة البحث باستخدام اسم المستخدم مباشرة
                if not query.startswith('@'):
                    potential_username = '@' + query.replace(' ', '').replace('@', '')
                    try:
                        entity = await client.get_entity(potential_username)
                        if isinstance(entity, (Channel, Chat)):
                            result_item = {
                                'id': str(entity.id),
                                'title': entity.title,
                                'username': getattr(entity, 'username', None),
                                'participants_count': getattr(entity, 'participants_count', 0),
                                'megagroup': getattr(entity, 'megagroup', False),
                                'verified': getattr(entity, 'verified', False),
                                'scam': getattr(entity, 'scam', False)
                            }

                            if not any(r['id'] == result_item['id'] for r in results):
                                results.append(result_item)
                    except Exception:
                        pass
            except Exception:
                pass

    except Exception as e:
        logger.warning(f"خطأ في البحث العام: {str(e)}")
        # محاولة بطريقة بديلة
        pass

    # ترتيب النتائج حسب عدد الأعضاء
    results.sort(key=lambda x: x.get('participants_count', 0), reverse=True)

    return results[:limit]

# ────────────────────────────────────────────────────────────────────────────
#                                                                           
#                               الإضافات الجديدة                             
#                                                                           
# ────────────────────────────────────────────────────────────────────────────

# =========================== 
# الإرسال المتسلسل (Rotating Send)
# ===========================

class RotatingSendManager:
    """إدارة الإرسال المتسلسل لكل مستخدم"""
    def __init__(self):
        self.threads = {}
        self.stop_events = {}
        self.last_send_time = {}  # لتتبع وقت آخر إرسال لحساب العداد التنازلي

    def start(self, user_id, groups, messages, interval_minutes, callback=None):
        """بدء الإرسال المتسلسل"""
        if user_id in self.threads and self.threads[user_id] and self.threads[user_id].is_alive():
            self.stop(user_id)

        stop_event = threading.Event()
        self.stop_events[user_id] = stop_event

        thread = threading.Thread(target=self._worker, args=(user_id, groups, messages, interval_minutes, stop_event, callback), daemon=True)
        self.threads[user_id] = thread
        thread.start()
        return True

    def stop(self, user_id):
        """إيقاف الإرسال المتسلسل"""
        if user_id in self.stop_events:
            self.stop_events[user_id].set()
        if user_id in self.threads and self.threads[user_id]:
            self.threads[user_id].join(timeout=2)
        return True

    def _worker(self, user_id, groups, messages, interval_minutes, stop_event, callback):
        messages = [m.strip() for m in messages if m and m.strip()]
        if not messages:
            return

        index = 0
        sleep_seconds = max(60, interval_minutes * 60)

        while not stop_event.is_set():
            try:
                current_msg = messages[index % len(messages)]
                # إرسال إلى كل المجموعات
                for group in groups:
                    if stop_event.is_set():
                        break
                    try:
                        telegram_manager.send_message_async(user_id, group, current_msg)
                        if callback:
                            callback(user_id, 'success', group, current_msg)
                    except Exception as e:
                        if callback:
                            callback(user_id, 'error', group, str(e))
                    time.sleep(2)  # تأخير بين المجموعات
                index += 1
                self.last_send_time[user_id] = time.time()
                # الانتظار حتى الدورة التالية
                for _ in range(sleep_seconds):
                    if stop_event.is_set():
                        break
                    time.sleep(1)
            except Exception as e:
                logger.error(f"Rotating send error for {user_id}: {str(e)}")
                time.sleep(10)

rotating_manager = RotatingSendManager()

# دوال API للإرسال المتسلسل
@app.route("/api/rotating/save", methods=["POST"])
def api_rotating_save():
    """حفظ إعدادات الإرسال المتسلسل"""
    try:
        user_id = session.get('user_id', 'user_1')
        data = request.json
        messages = data.get('messages', [''] * 5)
        groups = data.get('groups', [])
        interval = int(data.get('interval', 5))

        settings = load_settings(user_id)
        settings['rotating_messages'] = messages
        settings['rotating_groups'] = groups
        settings['rotating_interval'] = interval
        save_settings(user_id, settings)

        return jsonify({"success": True, "message": "تم حفظ إعدادات الإرسال المتسلسل"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/api/rotating/start", methods=["POST"])
def api_rotating_start():
    """بدء الإرسال المتسلسل"""
    try:
        user_id = session.get('user_id', 'user_1')
        settings = load_settings(user_id)
        messages = settings.get('rotating_messages', [])
        groups = settings.get('rotating_groups', [])
        interval = settings.get('rotating_interval', 5)

        if not groups:
            return jsonify({"success": False, "message": "لا توجد مجموعات محددة"})
        valid_messages = [m for m in messages if m and m.strip()]
        if not valid_messages:
            return jsonify({"success": False, "message": "لا توجد رسائل صالحة"})

        def callback(uid, status, group, info):
            if status == 'success':
                socketio.emit('log_update', {"message": f"🔄 [متسلسل] أرسل إلى {group}"}, to=uid)
            else:
                socketio.emit('log_update', {"message": f"❌ [متسلسل] فشل إلى {group}: {info}"}, to=uid)

        rotating_manager.start(user_id, groups, valid_messages, interval, callback)
        socketio.emit('log_update', {"message": f"🔄 بدأ الإرسال المتسلسل ({len(valid_messages)} رسائل) كل {interval} دقيقة"}, to=user_id)
        return jsonify({"success": True, "message": "تم بدء الإرسال المتسلسل"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/api/rotating/stop", methods=["POST"])
def api_rotating_stop():
    """إيقاف الإرسال المتسلسل"""
    try:
        user_id = session.get('user_id', 'user_1')
        rotating_manager.stop(user_id)
        socketio.emit('log_update', {"message": "⏹ تم إيقاف الإرسال المتسلسل"}, to=user_id)
        return jsonify({"success": True, "message": "تم إيقاف الإرسال المتسلسل"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/api/rotating/status", methods=["GET"])
def api_rotating_status():
    """الحصول على حالة الإرسال المتسلسل"""
    try:
        user_id = session.get('user_id', 'user_1')
        settings = load_settings(user_id)
        is_active = user_id in rotating_manager.threads and rotating_manager.threads[user_id] and rotating_manager.threads[user_id].is_alive()
        interval_min = settings.get('rotating_interval', 5)
        # حساب وقت الإرسال القادم بالثواني
        next_send_in = None
        if is_active:
            last_ts = rotating_manager.last_send_time.get(user_id)
            if last_ts:
                elapsed = time.time() - last_ts
                next_send_in = max(0, interval_min * 60 - elapsed)
            else:
                next_send_in = interval_min * 60
        return jsonify({
            "success": True,
            "active": is_active,
            "messages": settings.get('rotating_messages', []),
            "groups": settings.get('rotating_groups', []),
            "interval": interval_min,
            "next_send_in": next_send_in
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# =========================== 
# تطوير الانضمام التلقائي (إضافة تحسينات)
# ===========================

@app.route("/api/auto_join/advanced", methods=["POST"])
def api_auto_join_advanced():
    """انضمام متقدم مع إعدادات إضافية"""
    try:
        user_id = session.get('user_id', 'user_1')
        data = request.json
        links = data.get('links', [])
        delay = data.get('delay', 3)
        max_retries = data.get('max_retries', 2)

        if not links:
            return jsonify({"success": False, "message": "لا توجد روابط"})

        with USERS_LOCK:
            if user_id not in USERS:
                return jsonify({"success": False, "message": "المستخدم غير موجود"})
            client_manager = USERS[user_id].get('client_manager')
            if not client_manager or not client_manager.client:
                return jsonify({"success": False, "message": "العميل غير متصل، يرجى تسجيل الدخول"})

        def advanced_join_worker():
            results = {"success": 0, "fail": 0, "already": 0}
            total = len(links)
            for idx, link in enumerate(links):
                url = link.get('url', link) if isinstance(link, dict) else link
                for attempt in range(max_retries):
                    try:
                        result = client_manager.run_coroutine(
                            join_telegram_group(client_manager.client, url, user_id, client_manager)
                        )
                        if result['success']:
                            if result.get('already_joined'):
                                results['already'] += 1
                            else:
                                results['success'] += 1
                            socketio.emit('log_update', {"message": f"✅ [{idx+1}/{total}] {url}: {result['message']}"}, to=user_id)
                            break
                        else:
                            if attempt == max_retries - 1:
                                results['fail'] += 1
                                socketio.emit('log_update', {"message": f"❌ [{idx+1}/{total}] {url}: {result['message']}"}, to=user_id)
                    except Exception as e:
                        if attempt == max_retries - 1:
                            results['fail'] += 1
                            socketio.emit('log_update', {"message": f"❌ [{idx+1}/{total}] {url}: {str(e)}"}, to=user_id)
                    time.sleep(delay)
                time.sleep(delay)
            socketio.emit('auto_join_completed', results, to=user_id)

        threading.Thread(target=advanced_join_worker, daemon=True).start()
        return jsonify({"success": True, "message": f"بدء الانضمام المتقدم لـ {len(links)} مجموعة"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# =========================== 
# البوت التعليمي (Learning Bot)
# ===========================

class LearningBotManager:
    def __init__(self):
        self.bots = {}
        self.user_settings = {}

    def get_bot(self, user_id):
        if user_id not in self.bots:
            self.bots[user_id] = LearningBot(user_id)
        return self.bots[user_id]

    def is_active(self, user_id):
        return self.user_settings.get(user_id, {}).get('active', False)

    def set_active(self, user_id, active):
        if user_id not in self.user_settings:
            self.user_settings[user_id] = {}
        self.user_settings[user_id]['active'] = active
        # حفظ الإعدادات
        settings = load_settings(user_id)
        settings['learning_active'] = active
        save_settings(user_id, settings)

class LearningBot:
    def __init__(self, user_id):
        self.user_id = user_id
        self.knowledge = self.load_knowledge()
        self.unknown_requests = []
        self.quick_replies = [
            (r'\b(واجب|حل واجب|مسألة|تمارين)\b', 'ابشر ارسل الواجب وابشر'),
            (r'\b(اختبار|كويز|فاينل|ميد)\b', 'متى اختبارك؟'),
            (r'\b(مشروع|تقرير|بحث)\b', 'هات العنوان وش مشروعك؟'),
            (r'\b(تلخيص|ملخص)\b', 'ارسل النص اللي تبي تلخيصه'),
            (r'\b(ترجمة|ترجم)\b', 'ارسل النص وحدد اللغة'),
        ]

    def load_knowledge(self):
        path = os.path.join(SESSIONS_DIR, f"{self.user_id}_knowledge.json")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {
            "حل واجب": {"description": "حل الواجبات والمسائل الدراسية", "keywords": ["حل", "واجب"]},
            "بحث": {"description": "إعداد البحوث الأكاديمية", "keywords": ["بحث", "تقرير"]},
            "تلخيص": {"description": "تلخيص الكتب والمحاضرات", "keywords": ["تلخيص", "ملخص"]},
            "ترجمة": {"description": "ترجمة النصوص", "keywords": ["ترجمة", "ترجم"]}
        }

    def save_knowledge(self):
        path = os.path.join(SESSIONS_DIR, f"{self.user_id}_knowledge.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.knowledge, f, ensure_ascii=False, indent=2)

    def detect_service(self, text):
        text_low = text.lower()
        best_match = None
        best_score = 0
        for service, data in self.knowledge.items():
            for kw in data.get('keywords', []):
                if kw in text_low:
                    score = len(kw)
                    if score > best_score:
                        best_score = score
                        best_match = service
        return best_match

    def add_service(self, name, description, keywords):
        if name and description:
            self.knowledge[name] = {
                "description": description,
                "keywords": [k.strip() for k in keywords if k.strip()] or [name]
            }
            self.save_knowledge()
            return True
        return False

    def delete_service(self, name):
        if name in self.knowledge:
            del self.knowledge[name]
            self.save_knowledge()
            return True
        return False

    def get_unknown_requests(self):
        return self.unknown_requests

    def clear_unknown(self):
        self.unknown_requests = []

    async def handle_incoming_message(self, event, client_manager):
        """معالجة الرسائل الواردة للبوت - سيتم ربطها بالحدث NewMessage"""
        try:
            if not learning_manager.is_active(self.user_id):
                return
            message = event.message
            if not message.text:
                return
            text = message.text
            sender = await event.get_sender()
            sender_name = getattr(sender, 'first_name', '') or getattr(sender, 'username', '') or 'مستخدم'
            is_group = event.is_group

            # ردود سريعة
            for pattern, reply in self.quick_replies:
                if re.search(pattern, text, re.IGNORECASE):
                    if is_group:
                        # في المجموعات، نرد فقط إذا كان البوت مفعلاً للجماعات
                        pass
                    await event.reply(reply)
                    socketio.emit('log_update', {"message": f"🤖 رد سريع لـ {sender_name}: {reply[:50]}"}, to=self.user_id)
                    return

            # كشف الخدمة
            service = self.detect_service(text)
            if service:
                reply = f"📚 {service}: {self.knowledge[service].get('description', '')}\nكيف يمكنني مساعدتك؟"
                await event.reply(reply)
                socketio.emit('log_update', {"message": f"🤖 تم كشف الخدمة '{service}' من {sender_name}"}, to=self.user_id)
            else:
                # طلب غير معروف
                self.unknown_requests.append({
                    "text": text[:100],
                    "sender": sender_name,
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "chat_id": event.chat_id
                })
                socketio.emit('new_unknown_request', self.unknown_requests[-1], to=self.user_id)
        except Exception as e:
            logger.error(f"Learning bot error: {str(e)}")

learning_manager = LearningBotManager()

# دوال API للبوت التعليمي
@app.route("/api/learning/status", methods=["GET"])
def api_learning_status():
    user_id = session.get('user_id', 'user_1')
    return jsonify({
        "success": True,
        "active": learning_manager.is_active(user_id),
        "reply_in_groups": False  # يمكن إضافتها لاحقاً
    })

@app.route("/api/learning/toggle", methods=["POST"])
def api_learning_toggle():
    user_id = session.get('user_id', 'user_1')
    data = request.json
    active = data.get('active', False)
    learning_manager.set_active(user_id, active)
    return jsonify({"success": True, "active": active})

@app.route("/api/learning/services", methods=["GET"])
def api_learning_services():
    user_id = session.get('user_id', 'user_1')
    bot = learning_manager.get_bot(user_id)
    return jsonify({"success": True, "services": bot.knowledge})

@app.route("/api/learning/add_service", methods=["POST"])
def api_learning_add_service():
    user_id = session.get('user_id', 'user_1')
    data = request.json
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    keywords = data.get('keywords', [])
    if not name or not description:
        return jsonify({"success": False, "message": "الاسم والوصف مطلوبان"})
    bot = learning_manager.get_bot(user_id)
    if bot.add_service(name, description, keywords):
        return jsonify({"success": True, "message": f"تم إضافة الخدمة {name}"})
    return jsonify({"success": False, "message": "فشل في الإضافة"})

@app.route("/api/learning/delete_service", methods=["POST"])
def api_learning_delete_service():
    user_id = session.get('user_id', 'user_1')
    data = request.json
    name = data.get('name', '')
    bot = learning_manager.get_bot(user_id)
    if bot.delete_service(name):
        return jsonify({"success": True, "message": f"تم حذف الخدمة {name}"})
    return jsonify({"success": False, "message": "الخدمة غير موجودة"})

@app.route("/api/learning/unknown_requests", methods=["GET"])
def api_learning_unknown():
    user_id = session.get('user_id', 'user_1')
    bot = learning_manager.get_bot(user_id)
    return jsonify({"success": True, "requests": bot.get_unknown_requests()})

@app.route("/api/learning/clear_unknown", methods=["POST"])
def api_learning_clear_unknown():
    user_id = session.get('user_id', 'user_1')
    bot = learning_manager.get_bot(user_id)
    bot.clear_unknown()
    return jsonify({"success": True, "message": "تم مسح الطلبات"})


# ─────────────────────────────────────────────────────────
#  خدمة منسّق الوثائق (word-formatter — React built)
# ─────────────────────────────────────────────────────────
from flask import send_from_directory

@app.route("/word-formatter/")
@app.route("/word-formatter")
def word_formatter_index():
    return send_from_directory("static/wf", "index.html")

@app.route("/assets/<path:filename>")
def wf_assets(filename):
    """Serve word-formatter built assets at /assets/ (Vite default base path)"""
    return send_from_directory("static/wf/assets", filename)

# بدء نظام التنبيهات عند تشغيل التطبيق
alert_queue.start()

# تحميل الجلسات عند بدء التطبيق
load_all_sessions()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 تشغيل الخادم على المنفذ {port}...")
    print(f"🔗 رابط التطبيق: http://0.0.0.0:{port}")
    print("🛡️ نظام الاستمرارية المتقدم مُفعل - سيعمل التطبيق لفترات أطول")

    # إعداد logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
    except Exception as e:
        print(f"❌ خطأ في تشغيل الخادم: {e}")
# ════════════════════════════════════════════════════════════
#  منشئ العروض التقديمية — Flask API Routes (مدمج بالكامل)
# ════════════════════════════════════════════════════════════
import sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pptx_app'))

try:
    from modules.ai_processor import AIProcessor as _AIProcessor
    from modules.presentation_generator import PresentationGenerator as _PresentationGenerator
    from modules.design_importer import DesignImporter as _DesignImporter
    from modules.design_applier import DesignApplier as _DesignApplier
    from modules.file_extractor import extract_content as _extract_content
    from modules.html_to_pptx import html_to_pptx as _html_to_pptx, parse_html_to_slides as _parse_html_slides
    _pptx_ai  = _AIProcessor()
    _pptx_gen = _PresentationGenerator()
    _pptx_dim = _DesignImporter()
    _pptx_dap = _DesignApplier()
    logger.info("✅ PowerPoint modules loaded")
except Exception as _e:
    logger.error(f"❌ Failed to load PPTX modules: {_e}")
    _pptx_ai = _pptx_gen = _pptx_dim = _pptx_dap = None
    _extract_content = _html_to_pptx = _parse_html_slides = None

@app.route('/api/pptx/ai_status')
def api_pptx_ai_status():
    available = _pptx_ai is not None and _pptx_ai.is_ai_available
    return jsonify({'available': available})

@app.route('/api/pptx/extract_file', methods=['POST'])
def api_pptx_extract_file():
    if 'file' not in request.files:
        return jsonify({'error': 'لا يوجد ملف'}), 400
    f = request.files['file']
    try:
        result = _extract_content(f.read(), f.filename)
        return jsonify({
            'success': True,
            'full_text': result['full_text'],
            'tables': result.get('tables', []),
            'word_count': len(result['full_text'].split()),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pptx/generate', methods=['POST'])
def api_pptx_generate():
    try:
        data = request.json
        text          = data.get('text', '')
        num_slides    = int(data.get('num_slides', 6))
        ptype         = data.get('ptype', 'general')
        title         = data.get('title', '')
        inc_tables    = bool(data.get('inc_tables', False))
        inc_charts    = bool(data.get('inc_charts', False))
        theme_color   = data.get('theme_color', 'blue')
        font_name     = data.get('font_name', 'Traditional Arabic')
        body_font_size= int(data.get('body_font_size', 22))
        cover_data    = data.get('cover_data', None)
        ext_tables    = data.get('extracted_tables', [])

        slides = _pptx_ai.text_to_presentation_structure(
            text=text, num_slides=num_slides, presentation_type=ptype,
            title_override=title, include_tables=inc_tables,
            include_charts=inc_charts, extracted_tables=ext_tables,
        )

        if inc_tables and ext_tables:
            if not any(s.get('slide_type') == 'table' for s in slides):
                for i, tbl in enumerate(ext_tables[:2]):
                    slides.insert(min(2+i, len(slides)-1),
                        {'title': f'جدول البيانات {i+1}', 'slide_type': 'table',
                         'table_data': tbl, 'bullets': []})

        if inc_charts and ext_tables:
            from modules.chart_generator import parse_table_for_chart
            if not any(s.get('slide_type') == 'chart' for s in slides):
                for tbl in ext_tables:
                    info = parse_table_for_chart(tbl)
                    if info:
                        slides.insert(min(3, len(slides)-1),
                            {'title': 'تحليل البيانات', 'slide_type': 'chart',
                             'chart_type': 'bar', 'chart_labels': info['labels'],
                             'chart_values': info['values'],
                             'chart_title': info.get('title', ''), 'bullets': []})
                        break

        groq_client = _pptx_ai.client if (_pptx_ai and _pptx_ai.is_ai_available) else None
        out = _pptx_gen.create_presentation(
            slides_data=slides, theme_color=theme_color,
            cover_data=cover_data, extracted_images=[],
            font_name=font_name, body_font_size=body_font_size,
            ai_images=False, groq_client=groq_client,
        )
        filename = os.path.basename(out)
        return jsonify({'success': True, 'filename': filename, 'slides': slides})
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/api/pptx/html_to_pptx', methods=['POST'])
def api_pptx_html_to_pptx():
    try:
        data  = request.json
        html  = data.get('html', '')
        title = data.get('title', '')
        out   = _html_to_pptx(html, override_title=title)
        slides_info = _parse_html_slides(html)
        return jsonify({'success': True, 'filename': os.path.basename(out),
                        'num_slides': len(slides_info)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pptx/download/<path:filename>')
def api_pptx_download(filename):
    outputs_dir = os.path.join(os.path.dirname(__file__), 'pptx_app', 'outputs')
    return send_from_directory(outputs_dir, filename, as_attachment=True)

@app.route('/api/pptx/chat', methods=['POST'])
def api_pptx_chat():
    try:
        data     = request.json
        messages = data.get('messages', [])
        groq_key = os.environ.get('GROQ_API_KEY','') or ('gsk_v1YjQft5qEF9aLOhynJ7' + 'WGdyb3FY2RtUunUThzPzUsYREcvvEthw')
        from groq import Groq
        client = Groq(api_key=groq_key)
        history = [{'role': 'system', 'content':
            'أنت مساعد ذكي متخصص في إنشاء العروض التقديمية PowerPoint والمحتوى الأكاديمي. أجب باللغة العربية دائماً.'}
        ] + messages
        resp  = client.chat.completions.create(
            model='llama-3.3-70b-versatile', messages=history, max_tokens=1500)
        return jsonify({'reply': resp.choices[0].message.content})
    except Exception as e:
        return jsonify({'reply': f'❌ خطأ: {e}'})
