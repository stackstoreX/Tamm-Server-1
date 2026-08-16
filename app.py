import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import httpx
from supabase_client import supabase
from telegram import Bot

load_dotenv()

app = Flask(__name__)

# إعدادات التليجرام للسيرفر (لإرسال الإشعارات للمستخدمين مباشرة)
TELEGRAM_BOT = Bot(token=os.getenv("BOT_TOKEN"))
SERVER_URL = os.getenv("SERVER_URL")
FAWATERK_BASE = "https://app.fawaterk.com"

# ==========================================
# دوال مساعدة لـ فواتيرك
# ==========================================

async def get_fawaterk_token():
    """الحصول على توكن الوصول من فواتيرك"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{FAWATERK_BASE}/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": os.getenv("FAWATERK_CLIENT_ID"),
                "client_secret": os.getenv("FAWATERK_CLIENT_SECRET"),
            },
            timeout=30.0
        )
        resp.raise_for_status()
        return resp.json().get("access_token")

async def create_fawaterk_invoice(token, amount, description, user_id):
    """إنشاء فاتورة دفع عبر فواتيرك"""
    async with httpx.AsyncClient() as client:
        payload = {
            "cartTotal": amount,
            "currency": "EGP",
            "customer": {
                "first_name": f"User{user_id}",
                "last_name": "Client",
                "email": f"user{user_id}@tamm.bot",
                "phone": "01000000000"  # يمكنك جعلها متغيرة
            },
            "redirectionUrls": {
                "successUrl": f"https://t.me/YOUR_BOT_USERNAME",
                "failUrl": f"https://t.me/YOUR_BOT_USERNAME",
                "pendingUrl": f"https://t.me/YOUR_BOT_USERNAME"
            },
            "cartItems": [
                {"name": description, "price": amount, "quantity": 1}
            ]
        }
        resp = await client.post(
            f"{FAWATERK_BASE}/api/v3/createTransaction",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=30.0
        )
        resp.raise_for_status()
        return resp.json()

# ==========================================
# نقاط النهاية (Endpoints)
# ==========================================

@app.route('/')
def home():
    return "Tamm System API is Running!"

@app.route('/api/order/create', methods=['POST'])
def create_order():
    """إنشاء طلب جديد (للدفع من الرصيد)"""
    data = request.json
    try:
        order_data = {
            'user_id': data['user_id'],
            'product_id': data['product_id'],
            'quantity': data['quantity'],
            'total_price': data['total_price'],
            'payment_method': data['payment_method'],
            'client_email': data.get('client_email', ''),
            'coupon_code': data.get('coupon_code', ''),
            'discount_amount': data.get('discount_amount', 0),
            'status': 'pending',
            'order_date': datetime.now().isoformat()
        }
        response = supabase.table('orders').insert(order_data).execute()
        order_id = response.data[0]['id']
        return jsonify({'status': 'success', 'order_id': order_id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/order/create_invoice', methods=['POST'])
async def create_invoice():
    """إنشاء فاتورة دفع آلي (فودافون كاش/انستاباي)"""
    data = request.json
    try:
        user_id = data['user_id']
        product_id = data['product_id']
        total_price = data['total_price']
        description = f"Product {product_id}"

        # 1. الحصول على توكن فواتيرك
        token = await get_fawaterk_token()
        
        # 2. إنشاء الفاتورة
        invoice_resp = await create_fawaterk_invoice(token, total_price, description, user_id)
        invoice_data = invoice_resp.get('data', {})
        invoice_id = invoice_data.get('intent_key') or invoice_data.get('invoice_id')
        payment_url = invoice_data.get('url') or invoice_data.get('payment_url')

        if not invoice_id or not payment_url:
            return jsonify({'status': 'error', 'message': 'فشل في استخراج بيانات الفاتورة'}), 500

        # 3. تسجيل الطلب في قاعدة البيانات مع معرف الفاتورة
        order_data = {
            'user_id': user_id,
            'product_id': product_id,
            'quantity': data['quantity'],
            'total_price': total_price,
            'payment_method': data['payment_method'],
            'client_email': data.get('client_email', ''),
            'fawaterk_invoice_id': invoice_id,
            'status': 'pending',
            'order_date': datetime.now().isoformat()
        }
        db_resp = supabase.table('orders').insert(order_data).execute()
        order_id = db_resp.data[0]['id']

        return jsonify({
            'status': 'success',
            'order_id': order_id,
            'invoice_id': invoice_id,
            'payment_url': payment_url
        })
    except Exception as e:
        print(f"Error creating invoice: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/fawaterk-webhook', methods=['POST'])
async def fawaterk_webhook():
    """يستقبل إشعار الدفع من فواتيرك"""
    payload = request.json
    # ملاحظة: يجب التحقق من توقيع الطلب هنا حسب توثيق فواتيرك (لنضيفه لاحقاً)
    
    invoice_id = payload.get('intent_key') or payload.get('invoice_id')
    status = payload.get('status')  # افترض أن الحالة تأتي باسم 'status'

    if status and status.lower() == 'paid' and invoice_id:
        # 1. البحث عن الطلب في قاعدة البيانات
        db_resp = supabase.table('orders').select('*').eq('fawaterk_invoice_id', invoice_id).execute()
        if not db_resp.data:
            return jsonify({'status': 'ignored', 'message': 'Order not found'}), 200
        
        order = db_resp.data[0]
        if order['status'] == 'completed':
            return jsonify({'status': 'ignored', 'message': 'Already completed'}), 200

        # 2. تحديث حالة الطلب إلى مكتمل
        supabase.table('orders').update({'status': 'completed'}).eq('id', order['id']).execute()

        # 3. تحديث المخزون والمبيعات
        product = supabase.table('products').select('*').eq('id', order['product_id']).execute().data[0]
        supabase.table('products').update({
            'stock': product['stock'] - order['quantity']
        }).eq('id', order['product_id']).execute()
        
        supabase.table('products').update({
            'sales_count': product['sales_count'] + order['quantity']
        }).eq('id', order['product_id']).execute()

        # 4. إرسال إشعار للمستخدم عبر البوت
        try:
            msg = (f"✅ تم تأكيد طلبك وتفعيل الخدمة!\n\n"
                   f"🛍 الطلب رقم: #{order['id']}\n"
                   f"💰 المبلغ: {order['total_price']:.0f} ج.م")
            await TELEGRAM_BOT.send_message(chat_id=order['user_id'], text=msg)
        except Exception as e:
            print(f"Error sending Telegram message: {e}")

        return jsonify({'status': 'success'}), 200
    
    return jsonify({'status': 'ignored'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)