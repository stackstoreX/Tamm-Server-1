#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import nest_asyncio
nest_asyncio.apply()

import html
import logging
import os
import json
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

try:
    import httpx
except ImportError:
    raise ImportError("مكتبة httpx غير مثبتة. شغل: pip install httpx")

from dotenv import load_dotenv
from supabase_client import supabase  # ملف مشترك للاتصال بـ Supabase

# تحميل متغيرات البيئة
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_SECRET = os.getenv("ADMIN_SECRET")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
SERVER_URL = os.getenv("SERVER_URL")  # الرابط الذي ستنشئه على Render

# إعداد السجلات
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== دوال مساعدة ====================

def generate_auto_description(product_name: str) -> str:
    """توليد وصف تلقائي بسيط"""
    name = product_name.lower()
    if any(x in name for x in ["capcut", "كاب كات", "كابكات"]):
        return "🎬 تعديل فيديو احترافي بدون علامة مائية مع كل الفلاتر والمؤثرات والأدوات المتاحة للمحترفين."
    elif any(x in name for x in ["netflix", "نتفليكس"]):
        return "🎬 مشاهدة الأفلام والمسلسلات بجودة UHD 4K على 4 شاشات في نفس الوقت بدون أي إعلانات."
    elif any(x in name for x in ["spotify", "سبوتيفاي"]):
        return "🎵 استماع بدون إعلانات بجودة عالية جداً مع إمكانية التحميل للاستماع بدون إنترنت."
    elif any(x in name for x in ["chatgpt", "chat gpt", "شات جي بي تي", "gpt"]):
        return "🤖 الوصول الكامل لـ GPT-4 و GPT-4o مع إنشاء صور DALL-E وتصفح سريع بدون تقطيع."
    elif any(x in name for x in ["canva", "كانفا"]):
        return "🎨 كل القوالب الاحترافية مع أدوات Brand Kit وBackground Remover وتصميم فوري."
    elif any(x in name for x in ["youtube", "يوتيوب", "يوتيوب بريميوم"]):
        return "📺 مشاهدة بدون إعلانات مع خلفية مشغلة وتحميل الفيديوهات للمشاهدة بدون إنترنت."
    elif any(x in name for x in ["crunchyroll", "كرنشي", "انمي"]):
        return "🎌 مشاهدة الأنمي بجودة عالية مع ترجمة فورية وحلقات جديدة فوراً."
    elif any(x in name for x in ["apple", "آبل", "ايفون"]):
        return "🍎 خدمة أبل المميزة مع كل المزايا الحصرية والتحديثات المستمرة."
    elif any(x in name for x in ["steam", "ستيم", "لعبة"]):
        return "🎮 عالم الألعاب الرقمية مع كل الإضافات والمحتويات الحصرية."
    elif any(x in name for x in ["adobe", "أدوبي", "فوتوشوب"]):
        return "🎨 أدوات التصميم الاحترافية من أدوبي مع كل التحديثات والميزات الجديدة."
    elif any(x in name for x in ["vpn", "في بي ان"]):
        return "🔒 تصفح آمن وخاص مع سرعات عالية وخوادم في كل أنحاء العالم."
    else:
        return f"✨ خدمة {product_name} مميزة بأعلى جودة وأفضل سعر في السوق مع ضمان كامل وتسليم فوري."

# ==================== دوال قاعدة البيانات (Supabase) ====================

def get_user(user_id: int):
    """جلب مستخدم من Supabase"""
    try:
        resp = supabase.table('users').select('*').eq('user_id', user_id).execute()
        return resp.data[0] if resp.data else None
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return None

def get_or_create_user(user_id: int, username: str, first_name: str, last_name: str):
    """إرجاع المستخدم أو إنشائه إذا لم يوجد"""
    user = get_user(user_id)
    if user:
        return user

    new_user = {
        'user_id': user_id,
        'username': username,
        'first_name': first_name,
        'last_name': last_name,
        'balance': 0.0,
        'join_date': datetime.now().isoformat(),
        'is_banned': 0,
        'language': 'ar'
    }
    try:
        supabase.table('users').insert(new_user).execute()
        return get_user(user_id)
    except Exception as e:
        logger.error(f"Error creating user {user_id}: {e}")
        return None

def get_product(product_id: int):
    try:
        resp = supabase.table('products').select('*').eq('id', product_id).execute()
        return resp.data[0] if resp.data else None
    except Exception as e:
        logger.error(f"Error getting product {product_id}: {e}")
        return None

def get_products(page: int = 0, per_page: int = 5, active_only: bool = True):
    query = supabase.table('products').select('*', count='exact')
    if active_only:
        query = query.eq('is_active', 1)
    query = query.order('display_order').range(page * per_page, (page + 1) * per_page - 1)
    try:
        resp = query.execute()
        return resp.data, resp.count
    except Exception as e:
        logger.error(f"Error getting products: {e}")
        return [], 0

def get_all_categories():
    try:
        resp = supabase.table('categories').select('*').eq('is_active', 1).order('display_order').execute()
        return resp.data
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        return []

def get_user_orders(user_id: int, limit: int = 10):
    try:
        resp = supabase.table('orders').select('*, products(name)').eq('user_id', user_id).order('order_date', desc=True).limit(limit).execute()
        return resp.data
    except Exception as e:
        logger.error(f"Error getting orders for user {user_id}: {e}")
        return []

def get_user_orders_count(user_id: int) -> int:
    try:
        resp = supabase.table('orders').select('id', count='exact').eq('user_id', user_id).execute()
        return resp.count
    except Exception as e:
        logger.error(f"Error counting orders for user {user_id}: {e}")
        return 0

def get_user_total_spent(user_id: int) -> float:
    try:
        resp = supabase.table('orders').select('total_price').eq('user_id', user_id).eq('status', 'completed').execute()
        return sum([o['total_price'] for o in resp.data]) if resp.data else 0.0
    except Exception as e:
        logger.error(f"Error getting total spent for user {user_id}: {e}")
        return 0.0

def update_user_balance(user_id: int, amount: float):
    try:
        current = get_user(user_id)
        if current:
            new_balance = current['balance'] + amount
            supabase.table('users').update({'balance': new_balance}).eq('user_id', user_id).execute()
    except Exception as e:
        logger.error(f"Error updating balance for user {user_id}: {e}")

def update_order_status(order_id: int, status: str):
    try:
        supabase.table('orders').update({'status': status}).eq('id', order_id).execute()
    except Exception as e:
        logger.error(f"Error updating order {order_id}: {e}")

def get_order(order_id: int):
    try:
        resp = supabase.table('orders').select('*').eq('id', order_id).execute()
        return resp.data[0] if resp.data else None
    except Exception as e:
        logger.error(f"Error getting order {order_id}: {e}")
        return None

def update_product_stock(product_id: int, quantity: int):
    try:
        product = get_product(product_id)
        if product:
            new_stock = product['stock'] - quantity
            supabase.table('products').update({'stock': new_stock}).eq('id', product_id).execute()
    except Exception as e:
        logger.error(f"Error updating stock for product {product_id}: {e}")

def increment_product_sales(product_id: int, quantity: int):
    try:
        product = get_product(product_id)
        if product:
            new_sales = product['sales_count'] + quantity
            supabase.table('products').update({'sales_count': new_sales}).eq('id', product_id).execute()
    except Exception as e:
        logger.error(f"Error incrementing sales for product {product_id}: {e}")

def update_order_notes(order_id: int, notes: str):
    try:
        supabase.table('orders').update({'admin_notes': notes}).eq('id', order_id).execute()
    except Exception as e:
        logger.error(f"Error updating notes for order {order_id}: {e}")

def get_pending_orders():
    try:
        resp = supabase.table('orders').select('*, products(name), users(username, first_name)').eq('status', 'pending').order('order_date', desc=True).execute()
        return resp.data
    except Exception as e:
        logger.error(f"Error getting pending orders: {e}")
        return []

def get_all_coupons():
    try:
        resp = supabase.table('coupons').select('*').order('created_at', desc=True).execute()
        return resp.data
    except Exception as e:
        logger.error(f"Error getting coupons: {e}")
        return []

# ==================== دوال إرسال الطلبات للسيرفر ====================

async def send_to_server(endpoint: str, data: dict) -> dict:
    """إرسال طلب POST إلى سيرفر Flask"""
    url = f"{SERVER_URL}/{endpoint}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=data)
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.error(f"Server returned {resp.status_code}: {resp.text}")
                return None
    except Exception as e:
        logger.error(f"Error calling server {url}: {e}")
        return None

# ==================== دوال الكيبوردات (كما هي) ====================

def main_menu_keyboard(user_id=None):
    rows = [["🏠 الرئيسية", "🛍 المنتجات"]]
    if user_id and (user_id in ADMIN_IDS or is_admin_session_active(user_id)):
        rows.append(["🔐 لوحة التحكم المتقدمة"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def main_inline_menu_keyboard(user_id):
    buttons = [
        [InlineKeyboardButton("🛍 تصفح المنتجات", callback_data="browse_products")],
        [InlineKeyboardButton("🛒 طلباتي", callback_data="my_orders"), InlineKeyboardButton("💰 محفظتي", callback_data="my_wallet")],
        [InlineKeyboardButton("💳 شحن رصيد", callback_data="recharge_balance"), InlineKeyboardButton("🎟 الكوبونات", callback_data="my_coupons")],
        [InlineKeyboardButton("💬 الدعم الفني", callback_data="support"), InlineKeyboardButton("📖 شرح البوت", callback_data="tutorial")],
    ]
    return InlineKeyboardMarkup(buttons)

def wallet_inline_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏦 محفظة إلكترونية (يدوي)", callback_data="recharge_manual_wallet")],
        [InlineKeyboardButton("🅱️ بينانس (USDT)", callback_data="recharge_binance")],
        [InlineKeyboardButton("⬅️ رجوع للقائمة الرئيسية", callback_data="main_menu")],
    ])

def admin_dashboard_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍 إدارة المنتجات", callback_data="admin_products_menu")],
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users_menu")],
        [InlineKeyboardButton("📦 الطلبيات", callback_data="admin_orders_menu")],
        [InlineKeyboardButton("💳 شحن الرصيد", callback_data="admin_recharges_menu")],
        [InlineKeyboardButton("🎟 الكوبونات", callback_data="admin_coupons_menu")],
        [InlineKeyboardButton("📂 الفئات", callback_data="admin_categories_menu")],
        [InlineKeyboardButton("⚙️ إعدادات البوت", callback_data="admin_settings_menu")],
        [InlineKeyboardButton("📢 إرسال إشعار", callback_data="admin_broadcast_menu")],
        [InlineKeyboardButton("📊 الإحصائيات المتقدمة", callback_data="admin_stats_advanced")],
        [InlineKeyboardButton("📋 سجل العمليات", callback_data="admin_logs_menu")],
        [InlineKeyboardButton("💾 نسخ احتياطي", callback_data="admin_backup")],
        [InlineKeyboardButton("🚪 خروج من لوحة التحكم", callback_data="admin_exit")],
    ])

def admin_products_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة منتج", callback_data="admin_add_product")],
        [InlineKeyboardButton("📋 قائمة المنتجات", callback_data="admin_list_products")],
        [InlineKeyboardButton("✏️ تعديل منتج", callback_data="admin_edit_product")],
        [InlineKeyboardButton("🗑️ حذف/استرجاع منتج", callback_data="admin_delete_product")],
        [InlineKeyboardButton("📂 إدارة الفئات", callback_data="admin_categories_menu")],
        [InlineKeyboardButton("📊 أكثر المنتجات مبيعاً", callback_data="admin_top_products")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="admin_back")],
    ])

def admin_users_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 قائمة المستخدمين", callback_data="admin_list_users")],
        [InlineKeyboardButton("🔍 بحث عن مستخدم", callback_data="admin_search_user")],
        [InlineKeyboardButton("💰 تعديل رصيد مستخدم", callback_data="admin_edit_balance")],
        [InlineKeyboardButton("🚫 حظر/فك حظر", callback_data="admin_ban_user")],
        [InlineKeyboardButton("📊 إحصائيات المستخدمين", callback_data="admin_users_stats")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="admin_back")],
    ])

def admin_orders_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 الطلبات المعلقة", callback_data="admin_pending_orders")],
        [InlineKeyboardButton("✅ الطلبات المكتملة", callback_data="admin_completed_orders")],
        [InlineKeyboardButton("❌ الطلبات المرفوضة", callback_data="admin_rejected_orders")],
        [InlineKeyboardButton("🔍 بحث عن طلب", callback_data="admin_search_order")],
        [InlineKeyboardButton("📊 إحصائيات الطلبات", callback_data="admin_orders_stats")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="admin_back")],
    ])

def admin_recharges_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏳ طلبات الشحن المعلقة", callback_data="admin_pending_recharges")],
        [InlineKeyboardButton("✅ طلبات الشحن المكتملة", callback_data="admin_completed_recharges")],
        [InlineKeyboardButton("❌ طلبات الشحن المرفوضة", callback_data="admin_rejected_recharges")],
        [InlineKeyboardButton("📊 إحصائيات الشحن", callback_data="admin_recharges_stats")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="admin_back")],
    ])

def admin_coupons_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إنشاء كوبون", callback_data="admin_add_coupon")],
        [InlineKeyboardButton("📋 قائمة الكوبونات", callback_data="admin_list_coupons")],
        [InlineKeyboardButton("🗑️ حذف كوبون", callback_data="admin_delete_coupon")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="admin_back")],
    ])

def admin_settings_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 تعديل رقم المحفظة", callback_data="admin_set_wallet")],
        [InlineKeyboardButton("🅱️ تعديل عنوان USDT", callback_data="admin_set_usdt")],
        [InlineKeyboardButton("💬 تعديل يوزر الدعم", callback_data="admin_set_support")],
        [InlineKeyboardButton("🏷 تعديل اسم البوت", callback_data="admin_set_botname")],
        [InlineKeyboardButton("📩 تعديل رسالة الترحيب", callback_data="admin_set_welcome")],
        [InlineKeyboardButton("🔧 وضع الصيانة", callback_data="admin_maintenance")],
        [InlineKeyboardButton("💱 تعديل سعر الدولار", callback_data="admin_set_usd_rate")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="admin_back")],
    ])

def admin_broadcast_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 رسالة للجميع", callback_data="admin_broadcast_all")],
        [InlineKeyboardButton("👤 رسالة لمستخدم محدد", callback_data="admin_broadcast_user")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="admin_back")],
    ])

def admin_logs_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 آخر 20 عملية", callback_data="admin_logs_20")],
        [InlineKeyboardButton("📋 آخر 50 عملية", callback_data="admin_logs_50")],
        [InlineKeyboardButton("🔍 بحث في السجل", callback_data="admin_logs_search")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="admin_back")],
    ])

def products_inline_keyboard(products, page, total):
    buttons = []
    for p in products:
        stock_emoji = "✅" if p['stock'] > 5 else "⚠️" if p['stock'] > 0 else "❌"
        btn_text = f"{p['emoji']} {p['name']} | {p['price']:.0f} ج.م | {stock_emoji} {p['stock']}"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"product_{p['id']}")])

    total_pages = (total + 4) // 5
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"page_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"page_{page+1}"))

    if nav_buttons:
        buttons.append(nav_buttons)
    buttons.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)

def product_detail_keyboard(product_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 شراء الآن", callback_data=f"buy_{product_id}")],
        [InlineKeyboardButton("⬅️ رجوع للمتجر", callback_data="back_to_products")],
    ])

def quantity_keyboard(product_id, stock):
    quantities = [1, 2, 3, 5]
    buttons = []
    row = []
    for q in quantities:
        if q <= stock:
            row.append(InlineKeyboardButton(f"{q} 📦", callback_data=f"qty_{product_id}_{q}"))
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🎯 كمية مخصصة", callback_data=f"custom_qty_{product_id}")])
    buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"product_{product_id}")])
    return InlineKeyboardMarkup(buttons)

def payment_methods_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 ادفع من رصيدك", callback_data="pay_wallet")],
        [InlineKeyboardButton("📱 فودافون كاش (آلي)", callback_data="pay_vodafone")],
        [InlineKeyboardButton("💳 انستا باي (آلي)", callback_data="pay_instapay")],
        [InlineKeyboardButton("🅱️ بينانس (يدوي)", callback_data="pay_binance")],
        [InlineKeyboardButton("🎟 تطبيق كوبون خصم", callback_data="apply_coupon")],
        [InlineKeyboardButton("📥 شحن رصيد", callback_data="recharge")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="back_to_summary")],
    ])

def admin_order_notification_keyboard(order_id, requires_account=0):
    if requires_account == 1:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🎁 تسليم حساب", callback_data=f"admin_deliver_{order_id}")],
            [InlineKeyboardButton("❌ رفض الطلب", callback_data=f"admin_reject_order_{order_id}")],
            [InlineKeyboardButton("📝 إضافة ملاحظة", callback_data=f"admin_note_order_{order_id}")]
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأكيد الطلب", callback_data=f"admin_confirm_order_{order_id}"),
         InlineKeyboardButton("❌ رفض الطلب", callback_data=f"admin_reject_order_{order_id}")],
        [InlineKeyboardButton("📝 إضافة ملاحظة", callback_data=f"admin_note_order_{order_id}")]
    ])

def admin_recharge_notification_keyboard(recharge_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأكيد الشحن", callback_data=f"admin_confirm_recharge_{recharge_id}"),
         InlineKeyboardButton("❌ رفض الشحن", callback_data=f"admin_reject_recharge_{recharge_id}")],
        [InlineKeyboardButton("📝 إضافة ملاحظة", callback_data=f"admin_note_recharge_{recharge_id}")]
    ])

# ==================== دوال الإدارة (Admin Sessions) ====================

def is_admin(user_id):
    return user_id in ADMIN_IDS

def grant_admin_session(user_id, role="admin"):
    try:
        supabase.table('admin_sessions').upsert({
            'user_id': user_id,
            'is_active': 1,
            'granted_at': datetime.now().isoformat(),
            'role': role
        }).execute()
    except Exception as e:
        logger.error(f"Error granting admin session to {user_id}: {e}")

def revoke_admin_session(user_id):
    try:
        supabase.table('admin_sessions').delete().eq('user_id', user_id).execute()
    except Exception as e:
        logger.error(f"Error revoking admin session from {user_id}: {e}")

def is_admin_session_active(user_id):
    try:
        resp = supabase.table('admin_sessions').select('is_active').eq('user_id', user_id).execute()
        return resp.data and resp.data[0]['is_active'] == 1
    except Exception:
        return False

def get_admin_role(user_id):
    try:
        resp = supabase.table('admin_sessions').select('role').eq('user_id', user_id).execute()
        return resp.data[0]['role'] if resp.data else "admin"
    except Exception:
        return "admin"

# ==================== إشعارات الأدمن ====================

async def notify_admins_order(context, order_id, user, product, quantity, total_price, payment_method, client_email=""):
    safe_name = html.escape(user.first_name) if user.first_name else "مستخدم"
    user_mention = f"@{html.escape(user.username)}" if user.username else f'<a href="tg://user?id={user.id}">{safe_name}</a>'
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    requires_account = product.get('requires_account', 0)
    product_type = "🎁 أكونت جاهز" if requires_account == 1 else "🔧 تفعيل على أكونت شخصي"

    text = (
        f"🔔 طلب جديد (بانتظار المراجعة)!\n\n"
        f"👤 المستخدم: {user_mention}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"🛍 المنتج: {html.escape(product['name'])}\n"
        f"🏷️ النوع: {product_type}\n"
        f"🔢 الكمية: {quantity}\n"
        f"💰 الإجمالي: {total_price:.0f} ج.م\n"
        f"💳 طريقة الدفع: {html.escape(payment_method)}\n"
    )
    if client_email:
        text += f"📧 إيميل العميل: <code>{html.escape(client_email)}</code>\n"
    text += f"📅 التاريخ: {date_str}"

    for admin_id in ADMIN_IDS:
        try:
            kb = admin_order_notification_keyboard(order_id, requires_account)
            await context.bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode="HTML",
                reply_markup=kb
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

async def notify_admins_recharge(context, user, amount, sender_info, recharge_id):
    safe_name = html.escape(user.first_name) if user.first_name else "مستخدم"
    user_mention = f"@{html.escape(user.username)}" if user.username else f'<a href="tg://user?id={user.id}">{safe_name}</a>'
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    text = (
        f"💳 طلب شحن رصيد جديد (بانتظار التأكيد)!\n\n"
        f"👤 المستخدم: {user_mention}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"💰 المبلغ: {amount:.0f} ج.م\n"
        f"📱 تفاصيل التحويل: <code>{html.escape(sender_info)}</code>\n"
        f"📅 التاريخ: {date_str}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode="HTML",
                reply_markup=admin_recharge_notification_keyboard(recharge_id)
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

# ==================== معالجات الأوامر ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user = update.effective_user

    u = get_user(user.id)
    if u and u.get('is_banned', 0) == 1:
        await update.message.reply_text("🚫 تم حظرك من استخدام البوت. تواصل مع الدعم.")
        return

    # في حالة الصيانة، يمكن إضافة دالة get_setting من Supabase أو تجاهلها حالياً
    # سنفترض أن الصيانة غير مفعلة حالياً

    user_data = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    balance = user_data['balance'] if user_data else 0
    bot_name = "Tamm Shop"  # يمكن جلبها من الإعدادات

    text = (
        f"✨ متجر {bot_name} • تسليم فوري\n"
        f"🏛 أهلاً بيك يا {user.first_name or 'عزيزي'} في {bot_name}\n\n"
        f"🛍 رصيدك الحالي: {balance:.0f} ج.م\n\n"
        f"👇 اختار من القائمة اللي تحت"
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard(user.id))

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = get_user(user.id)
    balance = user_data['balance'] if user_data else 0
    order_count = get_user_orders_count(user.id)

    text = (
        f"*🏠 القائمة الرئيسية*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👋 مرحباً *{user.first_name or 'عزيزي'}*\n"
        f"💰 *رصيدك:* `{balance:.0f}` ج.م\n"
        f"🛒 *طلباتك:* `{order_count}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👇 *اختر ما تريد:*"
    )

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=main_inline_menu_keyboard(user.id)
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=main_inline_menu_keyboard(user.id)
        )

async def wallet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = get_user(user.id)
    balance = user_data['balance'] if user_data else 0
    spent = get_user_total_spent(user.id)
    order_count = get_user_orders_count(user.id)

    text = (
        f"*💰 محفظتي*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 *{user.first_name or 'عزيزي'}*\n\n"
        f"💵 *الرصيد الحالي:*\n"
        f"`{balance:.0f}` *ج.م* 💎\n\n"
        f"📊 *إحصائيات سريعة:*\n"
        f"• الطلبات: `{order_count}`\n"
        f"• إجمالي المشتريات: `{spent:.0f}` ج.م\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💳 *اختر طريقة الشحن:*"
    )

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=wallet_inline_keyboard()
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=wallet_inline_keyboard()
        )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    if not args:
        await update.message.reply_text("❌ استخدم: /admin [الكود السري]", reply_markup=main_menu_keyboard(user.id))
        return

    provided_code = args[0]

    if provided_code != ADMIN_SECRET and not is_admin(user.id):
        await update.message.reply_text("❌ كود غير صحيح!", reply_markup=main_menu_keyboard(user.id))
        return

    if is_admin(user.id) or provided_code == ADMIN_SECRET:
        grant_admin_session(user.id, "super_admin" if is_admin(user.id) else "admin")
        context.user_data["admin_mode"] = True
        context.user_data["admin_state"] = "menu"

        text = (
            f"🔐 تم تسجيل الدخول كأدمن!\n\n"
            f"👤 مرحباً {user.first_name}\n"
            f"🆔 ID: {user.id}\n"
            f"⚡️ الدور: {get_admin_role(user.id)}\n\n"
            f"👇 اختار الإجراء المطلوب:"
        )
        await update.message.reply_text(text, reply_markup=admin_dashboard_keyboard())

async def exit_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    revoke_admin_session(user.id)
    context.user_data.clear()
    await update.message.reply_text(
        "🚪 تم تسجيل الخروج من لوحة التحكم.\n\n👋 رجعت للوضع العادي.",
        reply_markup=main_menu_keyboard(user.id)
    )

# ==================== منتجات المستخدم ====================

async def products_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    page = context.user_data.get("product_page", 0)
    products, total = get_products(page)
    text = f"🛍 اختار المنتج اللي عايزه:"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=products_inline_keyboard(products, page, total))
    else:
        await update.message.reply_text(text, reply_markup=products_inline_keyboard(products, page, total))

async def product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_id = int(query.data.split("_")[1])
    product = get_product(product_id)
    if not product:
        await query.edit_message_text("❌ المنتج مش موجود!")
        return

    features = product.get('features', '').split("|") if product.get('features') else []
    features_text = "\n".join([f"• {f}" for f in features])
    discount_text = f"📉 خصم: {product['discount']}%\n" if product.get('discount', 0) > 0 else ""
    final_price = product['price'] * (1 - product.get('discount', 0) / 100)
    price_text = f"💰 السعر: {final_price:.0f} ج.م" if product.get('discount', 0) > 0 else f"💰 السعر: {product['price']:.0f} ج.م"

    text = (
        f"🛍 {product['name']}\n\n"
        f"{price_text}\n"
        f"{discount_text}"
        f"📦 المتوفر: {product['stock']}\n"
        f"⏳ الضمان: {product['warranty']} يوم\n"
        f"🏷️ الفئة: {product['category']}\n\n"
        f"✨ مميزات {product['name']}:\n"
        f"{features_text}\n\n"
        f"🚀 التسليم تلقائي فوري بعد تأكيد الدفع"
    )

    image_file_id = product.get('image_file_id', '')
    if image_file_id:
        try:
            await query.delete_message()
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=image_file_id,
                caption=text,
                reply_markup=product_detail_keyboard(product_id)
            )
            return
        except Exception as e:
            logger.error(f"Failed to send photo: {e}")

    await query.edit_message_text(text, reply_markup=product_detail_keyboard(product_id))

async def buy_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_id = int(query.data.split("_")[1])
    product = get_product(product_id)
    if not product or product['stock'] <= 0:
        await query.answer("❌ المنتج نفذ من المخزون!", show_alert=True)
        return
    context.user_data["selected_product"] = product_id
    text = (
        f"🛒 اختر الكمية\n"
        f"🛍 {product['name']}\n"
        f"💰 سعر الوحدة: {product['price']:.0f} ج.م\n"
        f"📦 المتوفر: {product['stock']}\n\n"
        f"👇 هتشتري كام؟"
    )
    await query.edit_message_text(text, reply_markup=quantity_keyboard(product_id, product['stock']))

async def select_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    product_id = int(parts[1])
    quantity = int(parts[2])
    product = get_product(product_id)
    user = update.effective_user
    user_data = get_user(user.id)
    balance = user_data['balance'] if user_data else 0

    unit_price = product['price']
    total_price = unit_price * quantity
    usd_rate = 50  # يمكن جلبها من الإعدادات
    usd_price = total_price / usd_rate
    requires_account = product.get('requires_account', 0)

    context.user_data["order"] = {
        "product_id": product_id,
        "quantity": quantity,
        "total_price": total_price,
        "unit_price": unit_price,
        "discount_amount": 0,
    }

    if requires_account == 0:
        context.user_data["awaiting_client_email"] = True
        await query.edit_message_text(
            f"📧 الخدمة دي بتتفعل على أكونتك الشخصي.\n\n"
            f"🛍 {product['name']}\n"
            f"🔢 الكمية: {quantity}\n"
            f"🧮 الإجمالي: {total_price:.0f} ج.م\n\n"
            f"✍️ ارسل الإيميل/الإيميلات اللي هيتفعل عليها (إيميل في كل سطر):"
        )
        return

    text = (
        f"🧾 ملخص الطلب\n"
        f"🛍 {product['name']}\n"
        f"🔢 الكمية: {quantity}\n"
        f"💰 سعر الوحدة: {unit_price:.0f} ج.م\n"
        f"🧮 الإجمالي: {total_price:.0f} ج.م\n"
        f"💵 يعادل بالدولار: ${usd_price:.2f}\n"
        f"💳 رصيدك: {balance:.0f} ج.م\n\n"
        f"👇 اختار طريقة الدفع"
    )
    await query.edit_message_text(text, reply_markup=payment_methods_keyboard())

# ==================== طرق الدفع ====================

async def pay_from_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    await query.answer()

    user_data = get_user(user.id)
    if not user_data:
        await query.edit_message_text("❌ حدث خطأ في جلب بيانات المستخدم.")
        return

    balance = user_data['balance']
    order_data = context.user_data.get("order")
    if not order_data:
        await query.edit_message_text("❌ مفيش طلب نشط!")
        return

    total_price = order_data["total_price"]
    if balance < total_price:
        remaining = total_price - balance
        await query.edit_message_text(
            f"⚠️ رصيدك غير كافي!\n\n"
            f"💰 المطلوب: {total_price:.0f} ج.م\n"
            f"💳 رصيدك: {balance:.0f} ج.م\n"
            f"📉 النقص: {remaining:.0f} ج.م\n\n"
            f"👇 لتعبئة محفظتك 'شحن رصيد' اضغط على",
            reply_markup=wallet_inline_keyboard()
        )
        return

    # 1. خصم الرصيد
    update_user_balance(user.id, -total_price)

    # 2. إرسال الطلب للسيرفر
    payload = {
        'user_id': user.id,
        'product_id': order_data['product_id'],
        'quantity': order_data['quantity'],
        'total_price': total_price,
        'payment_method': 'رصيد',
        'client_email': context.user_data.get('client_email', ''),
        'coupon_code': context.user_data.get('applied_coupon', ''),
        'discount_amount': context.user_data.get('coupon_discount', 0),
    }
    server_resp = await send_to_server('api/order/create', payload)

    if server_resp and server_resp.get('order_id'):
        order_id = server_resp['order_id']
        product = get_product(order_data['product_id'])
        await query.edit_message_text(
            f"✅ تم خصم المبلغ وإرسال طلبك للأدمن.\n🆔 الطلب: #{order_id}\n⏳ في انتظار المراجعة."
        )
        await notify_admins_order(context, order_id, user, product, order_data['quantity'], total_price, 'رصيد', context.user_data.get('client_email', ''))
    else:
        # إعادة الرصيد في حالة الفشل
        update_user_balance(user.id, total_price)
        await query.edit_message_text("❌ حدث خطأ في السيرفر، حاول مرة أخرى.")

    context.user_data.pop("order", None)
    context.user_data.pop("client_email", None)
    context.user_data.pop("applied_coupon", None)
    context.user_data.pop("coupon_discount", None)

async def binance_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_data = context.user_data.get("order")
    if not order_data:
        await query.edit_message_text("❌ مفيش طلب نشط!")
        return

    total_price = order_data["total_price"]
    usd_rate = 50  # يمكن جلبها من الإعدادات
    usd_price = total_price / usd_rate
    usdt_addr = os.getenv("USDT_ADDRESS", "YOUR_USDT_TRC20_ADDRESS_HERE")

    text = (
        f"✅ تمام. ادفع ${usd_price:.2f} USDT على شبكة USDT TRC20:\n\n"
        f"🅱️ عنوان المحفظة:\n"
        f"<code>{usdt_addr}</code>\n\n"
        f"⚠️ لازم تبعت نفس المبلغ بالظبط\n"
        f"⚠️ شبكة USDT TRC20 فقط — لو حوّلت على شبكة تانية فلوسك هتضيع\n\n"
        f"وبعد التحويل، ابعت Order ID هنا للمراجعة 👇"
    )
    await query.edit_message_text(text, parse_mode="HTML")
    context.user_data["awaiting_payment_confirmation"] = True
    context.user_data["payment_type"] = "order"

async def initiate_fawaterk_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, method_name: str):
    query = update.callback_query
    await query.answer()
    order_data = context.user_data.get("order")
    if not order_data:
        await query.edit_message_text("❌ مفيش طلب نشط!")
        return

    # إرسال الطلب للسيرفر لإنشاء الفاتورة
    payload = {
        'user_id': update.effective_user.id,
        'product_id': order_data['product_id'],
        'quantity': order_data['quantity'],
        'total_price': order_data['total_price'],
        'payment_method': method_name,
        'client_email': context.user_data.get('client_email', ''),
        'coupon_code': context.user_data.get('applied_coupon', ''),
        'discount_amount': context.user_data.get('coupon_discount', 0),
    }
    server_resp = await send_to_server('api/order/create_invoice', payload)

    if server_resp and server_resp.get('payment_url'):
        payment_url = server_resp['payment_url']
        invoice_id = server_resp['invoice_id']
        await query.edit_message_text(
            f"⚡ تم إنشاء فاتورة الدفع عبر {method_name}!\n\n"
            f"🔗 رابط الدفع الآمن:\n{payment_url}\n\n"
            f"بعد إتمام الدفع، سيتم تأكيد طلبك تلقائياً.",
            disable_web_page_preview=True
        )
    else:
        await query.edit_message_text("❌ فشل في إنشاء الفاتورة. حاول مرة أخرى.")

# ==================== شحن الرصيد ====================

async def recharge_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "💳 اختار طريقة شحن الرصيد:",
        reply_markup=wallet_inline_keyboard()
    )

async def recharge_manual_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["recharge_flow"] = True
    context.user_data["recharge_step"] = "amount"
    context.user_data["recharge_method"] = "wallet"
    wallet = os.getenv("WALLET_NUMBER", "01018484572")
    wallet_name = os.getenv("WALLET_NAME", "محمود")
    await query.edit_message_text(
        f"📱 شحن رصيد — محفظة إلكترونية\n\n"
        f"💳 المحفظة: <code>{wallet}</code> — {wallet_name}\n"
        f"💰 اكتب المبلغ اللي عايز تحوله (بالجنيه):\n"
        f"*(للإلغاء أرسل /start)*",
        parse_mode="HTML"
    )

async def recharge_binance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["recharge_flow"] = True
    context.user_data["recharge_step"] = "amount"
    context.user_data["recharge_method"] = "binance"
    usdt_addr = os.getenv("USDT_ADDRESS", "YOUR_USDT_TRC20_ADDRESS_HERE")
    await query.edit_message_text(
        f"💳 شحن رصيد — بينانس (USDT)\n\n"
        f"🅱️ عنوان USDT TRC20:\n<code>{usdt_addr}</code>\n\n"
        f"💰 ارسل المبلغ بالجنيه (رقم فقط):\n"
        f"*(للإلغاء أرسل /start)*",
        parse_mode="HTML"
    )

async def recharge_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # يتم استدعاؤها من text_handler عند وجود recharge_flow
    pass

# ==================== الأوامر الأخرى ====================

async def orders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    orders = get_user_orders(user.id)
    if not orders:
        text = "🛒 ماعندكش طلبات لسه!\n\nروح للمنتجات واشتري 🛍"
    else:
        text = "🛒 طلباتك:\n\n"
        for o in orders:
            status_emoji = "✅" if o['status'] == "completed" else "⏳" if o['status'] == "pending" else "❌"
            product_name = o.get('products', {}).get('name', 'Unknown')
            text += f"{status_emoji} #{o['id']} | {product_name} | {o['quantity']} قطعة | {o['total_price']:.0f} ج.م | {o['payment_method']}\n"

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=main_inline_menu_keyboard(user.id))
    else:
        await update.message.reply_text(text, reply_markup=main_menu_keyboard(user.id))

async def support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    support_user = os.getenv("SUPPORT_USERNAME", "@SupportUsername")
    text = (
        f"💬 الدعم الفني\n\n"
        f"عندك مشكلة؟ محتاج مساعدة؟\n"
        f"تواصل معانا مباشرة:\n"
        f"{support_user}\n\n"
        f"⏰ مواعيد الرد: من 10 ص لـ 12 ص"
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=main_inline_menu_keyboard(update.effective_user.id))
    else:
        await update.message.reply_text(text, reply_markup=main_menu_keyboard(update.effective_user.id))

async def tutorial_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"📖 شرح استخدام البوت\n\n"
        '1️⃣ اضغط "المنتجات 🛍" عشان تشوف كل اللي عندنا\n'
        "2️⃣ اختار المنتج اللي عايزه\n"
        '3️⃣ اضغط "شراء الآن" واختار الكمية\n'
        "4️⃣ اختار طريقة الدفع (رصيدك، أو دفع مباشر)\n"
        "5️⃣ بعد الدفع، المنتج هيوصلك فوري! 🚀\n\n"
        '💡 تقدر تشحن رصيدك من "شحن رصيد 💳"\n'
        '💡 تقدر تشوف طلباتك من "طلباتي 🛒"\n\n'
        "سهل صح؟ 😎"
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=main_inline_menu_keyboard(update.effective_user.id))
    else:
        await update.message.reply_text(text, reply_markup=main_menu_keyboard(update.effective_user.id))

async def coupons_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    coupons = get_all_coupons()
    now = datetime.now().strftime("%Y-%m-%d")
    active_coupons = []
    for c in coupons:
        if c.get('is_active', 1) == 1 and (not c.get('expires_at') or c['expires_at'] >= now) and c.get('used_count', 0) < c.get('max_uses', 0):
            active_coupons.append(c)

    if not active_coupons:
        text = "🎟 مفيش كوبونات متاحة حالياً!\n\nتابعنا عشان تعرف الكوبونات الجديدة أول بأول."
    else:
        text = "🎟 الكوبونات المتاحة:\n\n"
        for c in active_coupons:
            text += f"• <code>{c['code']}</code> — خصم {c['discount_percent']}% (حد أدنى {c.get('min_order_amount', 0):.0f}ج)\n"
        text += "\n✨ اضغط على المنتجات واستخدم الكوبون أثناء الدفع!"

    await update.message.reply_text(text, reply_markup=main_menu_keyboard(update.effective_user.id), parse_mode="HTML")

# ==================== معالج الاستدعاءات ====================

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user = update.effective_user

    # التعامل مع أوامر الأدمن
    if data.startswith("admin_"):
        if not is_admin(user.id) and not is_admin_session_active(user.id):
            await query.answer("❌ ممنوع!", show_alert=True)
            return

        if data == "admin_products_menu":
            await query.edit_message_text("🛍 إدارة المنتجات\n\n👇 اختار الإجراء المطلوب:", reply_markup=admin_products_menu_keyboard())
        elif data == "admin_users_menu":
            await query.edit_message_text("👥 إدارة المستخدمين\n\n👇 اختار الإجراء المطلوب:", reply_markup=admin_users_menu_keyboard())
        elif data == "admin_orders_menu":
            await query.edit_message_text("📦 الطلبيات\n\n👇 اختار الإجراء المطلوب:", reply_markup=admin_orders_menu_keyboard())
        elif data == "admin_recharges_menu":
            await query.edit_message_text("💳 شحن الرصيد\n\n👇 اختار الإجراء المطلوب:", reply_markup=admin_recharges_menu_keyboard())
        elif data == "admin_coupons_menu":
            await query.edit_message_text("🎟 إدارة الكوبونات\n\n👇 اختار الإجراء المطلوب:", reply_markup=admin_coupons_menu_keyboard())
        elif data == "admin_categories_menu":
            # يمكنك إضافة منطق عرض الفئات
            await query.edit_message_text("📂 الفئات (قيد التطوير)")
        elif data == "admin_settings_menu":
            await query.edit_message_text("⚙️ إعدادات البوت (قيد التطوير)")
        elif data == "admin_back":
            await query.edit_message_text("🔐 لوحة تحكم الأدمن", reply_markup=admin_dashboard_keyboard())
        elif data == "admin_exit":
            context.user_data.clear()
            await exit_admin(update, context)
        # باقي أوامر الأدمن (إضافة منتج، قائمة منتجات، إلخ) يمكن إضافتها بنفس المنطق
        return

    # القائمة الرئيسية
    if data == "main_menu":
        await query.answer()
        # تنظيف البيانات
        for key in ["awaiting_client_email", "awaiting_custom_qty", "awaiting_coupon",
                    "awaiting_payment_confirmation", "order", "client_email", "applied_coupon", "coupon_discount"]:
            context.user_data.pop(key, None)
        await main_menu_handler(update, context)
    elif data == "browse_products":
        await query.answer()
        context.user_data.pop("order", None)
        await products_handler(update, context)
    elif data == "my_orders":
        await query.answer()
        await orders_handler(update, context)
    elif data == "my_wallet":
        await query.answer()
        await wallet_handler(update, context)
    elif data == "recharge_balance":
        await query.answer()
        await recharge_balance(update, context)
    elif data == "my_coupons":
        await query.answer()
        await coupons_handler(update, context)
    elif data == "support":
        await query.answer()
        await support_handler(update, context)
    elif data == "tutorial":
        await query.answer()
        await tutorial_handler(update, context)
    elif data.startswith("page_"):
        page = int(data.split("_")[1])
        context.user_data["product_page"] = page
        await products_handler(update, context)
    elif data == "back_to_products":
        await query.answer()
        context.user_data.pop("order", None)
        await products_handler(update, context)
    elif data.startswith("product_"):
        await product_detail(update, context)
    elif data.startswith("buy_"):
        await buy_product(update, context)
    elif data.startswith("qty_"):
        await select_quantity(update, context)
    elif data.startswith("custom_qty_"):
        await query.answer("✍️ ارسل الكمية اللي عايزها (رقم فقط):")
        context.user_data["awaiting_custom_qty"] = int(data.split("_")[2])
    elif data == "pay_wallet":
        await pay_from_wallet(update, context)
    elif data == "pay_vodafone":
        await initiate_fawaterk_payment(update, context, "فودافون كاش")
    elif data == "pay_instapay":
        await initiate_fawaterk_payment(update, context, "انستا باي")
    elif data == "pay_binance":
        await binance_payment(update, context)
    elif data == "apply_coupon":
        await query.answer()
        order_data = context.user_data.get("order")
        if not order_data:
            await query.edit_message_text("❌ مفيش طلب نشط!")
            return
        context.user_data["awaiting_coupon"] = True
        await query.edit_message_text("🎟 ارسل كود الكوبون:")
    elif data == "recharge":
        await recharge_balance(update, context)
    elif data == "recharge_manual_wallet":
        await recharge_manual_wallet(update, context)
    elif data == "recharge_binance":
        await recharge_binance(update, context)
    elif data == "back_to_summary":
        await query.answer()
        # إعادة عرض ملخص الطلب
        order_data = context.user_data.get("order")
        if order_data:
            product = get_product(order_data["product_id"])
            user_data = get_user(user.id)
            balance = user_data['balance'] if user_data else 0
            total_price = order_data["total_price"]
            usd_rate = 50  # يمكن جلبها من الإعدادات
            usd_price = total_price / usd_rate
            text = (
                f"🧾 ملخص الطلب\n"
                f"🛍 {product['name']}\n"
                f"🔢 الكمية: {order_data['quantity']}\n"
                f"💰 سعر الوحدة: {order_data['unit_price']:.0f} ج.م\n"
                f"🧮 الإجمالي: {total_price:.0f} ج.م\n"
                f"💵 يعادل بالدولار: ${usd_price:.2f}\n"
                f"💳 رصيدك: {balance:.0f} ج.م\n\n"
                f"👇 اختار طريقة الدفع"
            )
            await query.edit_message_text(text, reply_markup=payment_methods_keyboard())
    elif data == "noop":
        await query.answer()

# ==================== معالج النصوص ====================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    # معالجة إدخال الإيميل
    if context.user_data.get("awaiting_client_email"):
        context.user_data["client_email"] = text.strip()
        context.user_data.pop("awaiting_client_email", None)
        order_data = context.user_data.get("order")
        if order_data:
            product = get_product(order_data["product_id"])
            user_data = get_user(user.id)
            balance = user_data['balance'] if user_data else 0
            total_price = order_data["total_price"]
            usd_rate = 50
            usd_price = total_price / usd_rate
            msg = (
                f"🧾 ملخص الطلب\n"
                f"🛍 {product['name']}\n"
                f"🔢 الكمية: {order_data['quantity']}\n"
                f"💰 سعر الوحدة: {order_data['unit_price']:.0f} ج.م\n"
                f"🧮 الإجمالي: {total_price:.0f} ج.م\n"
                f"💵 يعادل بالدولار: ${usd_price:.2f}\n"
                f"📧 الإيميل: {text.strip()}\n"
                f"💳 رصيدك: {balance:.0f} ج.م\n\n"
                f"👇 اختار طريقة الدفع"
            )
            await update.message.reply_text(msg, reply_markup=payment_methods_keyboard())
        return

    # معالجة إدخال الكمية المخصصة
    if context.user_data.get("awaiting_custom_qty"):
        try:
            qty = int(text.strip())
            product_id = context.user_data.pop("awaiting_custom_qty")
            product = get_product(product_id)
            if qty > product['stock'] or qty < 1:
                await update.message.reply_text("❌ الكمية غير متاحة!")
                return
            user_data = get_user(user.id)
            balance = user_data['balance'] if user_data else 0
            unit_price = product['price']
            total_price = unit_price * qty
            usd_rate = 50
            usd_price = total_price / usd_rate

            context.user_data["order"] = {
                "product_id": product_id,
                "quantity": qty,
                "total_price": total_price,
                "unit_price": unit_price,
                "discount_amount": 0,
            }
            requires_account = product.get('requires_account', 0)
            if requires_account == 0:
                context.user_data["awaiting_client_email"] = True
                await update.message.reply_text(
                    f"📧 الخدمة دي بتتفعل على أكونتك الشخصي.\n\n"
                    f"🛍 {product['name']}\n"
                    f"🔢 الكمية: {qty}\n"
                    f"🧮 الإجمالي: {total_price:.0f} ج.م\n\n"
                    f"✍️ ارسل الإيميل/الإيميلات اللي هيتفعل عليها (إيميل في كل سطر):"
                )
            else:
                msg = (
                    f"🧾 ملخص الطلب\n"
                    f"🛍 {product['name']}\n"
                    f"🔢 الكمية: {qty}\n"
                    f"💰 سعر الوحدة: {unit_price:.0f} ج.م\n"
                    f"🧮 الإجمالي: {total_price:.0f} ج.م\n"
                    f"💵 يعادل بالدولار: ${usd_price:.2f}\n"
                    f"💳 رصيدك: {balance:.0f} ج.م\n\n"
                    f"👇 اختار طريقة الدفع"
                )
                await update.message.reply_text(msg, reply_markup=payment_methods_keyboard())
        except ValueError:
            await update.message.reply_text("❌ لازم رقم!")
        return

    # معالجة إدخال الكوبون
    if context.user_data.get("awaiting_coupon"):
        context.user_data.pop("awaiting_coupon", None)
        coupon_code = text.strip()
        # يمكن إرسال الكوبون للسيرفر للتحقق منه، لكن سنبسطها حالياً
        await update.message.reply_text("🎟 تم استلام الكوبون، سيتم تطبيقه عند الدفع.")
        context.user_data["applied_coupon"] = coupon_code
        # يمكن إعادة عرض ملخص الطلب مع الخصم إذا أردت
        return

    # معالجة إدخال تأكيد الدفع (بينانس)
    if context.user_data.get("awaiting_payment_confirmation"):
        context.user_data.pop("awaiting_payment_confirmation", None)
        await update.message.reply_text(
            "✅ تم استلام التأكيد! الأدمن هيراجع التحويل ويوافق عليه قريباً.\n⏳ هنرد عليك في خلال دقايق."
        )
        return

    # معالجة شحن الرصيد
    if context.user_data.get("recharge_flow"):
        step = context.user_data.get("recharge_step")
        if step == "amount":
            try:
                amount = float(text.strip())
                min_recharge = 5  # يمكن جلبها من الإعدادات
                if amount < min_recharge:
                    await update.message.reply_text(f"❌ الحد الأدنى للشحن: {min_recharge:.0f} ج.م")
                    return
                context.user_data["recharge_amount"] = amount
                context.user_data["recharge_step"] = "phone"
                method = context.user_data.get("recharge_method", "wallet")
                if method == "wallet":
                    wallet = os.getenv("WALLET_NUMBER", "01018484572")
                    wallet_name = os.getenv("WALLET_NAME", "محمود")
                    await update.message.reply_text(
                        f"💰 المبلغ: {amount:.0f} ج.م\n\n"
                        f"📱 ارسل رقم المحفظة اللي حوّلت منها:\n"
                        f"*(أو اسمك + رقم التحويل)*"
                    )
                else:
                    usd_rate = 50
                    usd_amount = amount / usd_rate
                    usdt_addr = os.getenv("USDT_ADDRESS", "YOUR_USDT_TRC20_ADDRESS_HERE")
                    await update.message.reply_text(
                        f"💰 المبلغ: {amount:.0f} ج.م ≈ ${usd_amount:.2f} USDT\n\n"
                        f"🅱️ عنوان USDT TRC20:\n"
                        f"<code>{usdt_addr}</code>\n\n"
                        f"📱 بعد التحويل، ارسل رقم المحفظة/التفاصيل هنا للتأكيد:",
                        parse_mode="HTML"
                    )
            except ValueError:
                await update.message.reply_text("❌ لازم رقم!")
            return
        elif step == "phone":
            sender_info = text.strip()
            amount = context.user_data.get("recharge_amount", 0)
            # إرسال طلب الشحن إلى السيرفر أو إنشائه محلياً
            # للتبسيط سنقوم بإنشاء طلب شحن في قاعدة البيانات
            try:
                recharge_data = {
                    'user_id': user.id,
                    'amount': amount,
                    'phone_number': sender_info,
                    'status': 'pending',
                    'request_date': datetime.now().isoformat()
                }
                resp = supabase.table('recharges').insert(recharge_data).execute()
                recharge_id = resp.data[0]['id']
                await notify_admins_recharge(context, user, amount, sender_info, recharge_id)
                context.user_data.pop("recharge_flow", None)
                context.user_data.pop("recharge_step", None)
                context.user_data.pop("recharge_amount", None)
                context.user_data.pop("recharge_method", None)
                await update.message.reply_text(
                    f"⏳ تم إرسال طلب الشحن للأدمن!\n"
                    f"💰 المبلغ: {amount:.0f} ج.م\n"
                    f"📱 التفاصيل: {sender_info}\n\n"
                    f"✅ هنرد عليك في خلال دقايق."
                )
            except Exception as e:
                logger.error(f"Error creating recharge: {e}")
                await update.message.reply_text("❌ حدث خطأ أثناء إنشاء طلب الشحن.")
            return

    # أزرار القائمة السفلية
    if text == "🏠 الرئيسية":
        await main_menu_handler(update, context)
    elif text == "🛍 المنتجات":
        await products_handler(update, context)
    elif text == "🔐 لوحة التحكم المتقدمة":
        if is_admin(user.id) or is_admin_session_active(user.id):
            context.user_data["admin_mode"] = True
            context.user_data["admin_state"] = "menu"
            await update.message.reply_text("🔐 أهلاً بك في لوحة تحكم الأدمن، الإجراء مطلوب:", reply_markup=admin_dashboard_keyboard())
        else:
            await update.message.reply_text("❌ ممنوع دخول هذه اللوحة!", reply_markup=main_menu_keyboard(user.id))
    else:
        await update.message.reply_text("👇 اختر من القائمة التي تحت:", reply_markup=main_menu_keyboard(user.id))

# ==================== الدالة الرئيسية ====================

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_command))

    # الاستدعاءات
    application.add_handler(CallbackQueryHandler(callback_handler))

    # الرسائل النصية
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    logger.info("🤖 Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()