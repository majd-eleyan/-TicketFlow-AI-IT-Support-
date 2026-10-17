#  إرسال الإشعارات:
#  1) ديسكورد للموظفين عند وجود تذكرة تحتاج مراجعة
#  2)  إيميل Gmail للمستخدم عند رد الموظف على تذكرته

import logging
import re
import smtplib
import ssl
from email.message import EmailMessage

import config

logger = logging.getLogger(__name__)

PRIORITY_COLORS = {
    "HIGH": 15158332,   # Red
    "MEDIUM": 15105570, # Orange
    "LOW": 3066993      # Blue
}


def send_discord_notification(ticket):
    
    # 1. التثبت من تفعيل الإشعارات وجود رابط الـ Webhook
    if not config.DISCORD_ENABLED or not config.DISCORD_WEBHOOK_URL:
        return False

    # 2. تجهيز كرت الإشعار (محتوى آمن خالي من بيانات العميل)
    payload = {
        "embeds": [{
            "title": f"New Support Ticket: {ticket.get('ticket_id')}",
            "color": PRIORITY_COLORS.get(ticket.get("priority"), PRIORITY_COLORS["LOW"]),
            "fields": [
                {"name": "Category", "value": str(ticket.get("category") or "-"), "inline": True},
                {"name": "Priority", "value": str(ticket.get("priority") or "-"), "inline": True},
                {"name": "Status", "value": str(ticket.get("status") or "-"), "inline": True},
                {"name": "Agent action", "value": str(ticket.get("agent_action") or "-"), "inline": True},
            ],
        }]
    }

    # 3. محاولة الإرسال مع حماية النظام من الانهيار
    try:
        import requests
        response = requests.post(config.DISCORD_WEBHOOK_URL, json=payload, timeout=5)
        
        if response.status_code in (200, 204):
            return True
            
        logger.warning("Discord notification failed with HTTP status %s", response.status_code)
    except Exception as exc:
        logger.warning("Discord notification error occurred: %s", type(exc).__name__)

    return False


# ======================================================================
#  إرسال رد الموظف للمستخدم عبر Gmail
# ======================================================================
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(value):
    """فحص بسيط لشكل الإيميل (يُستخدم بالواجهة وقبل الإرسال)"""
    value = (value or "").strip()
    return bool(value) and len(value) <= 254 and bool(EMAIL_PATTERN.match(value))


def open_smtp_connection(port=None):
    """فتح اتصال Gmail"""
    port = port or config.SMTP_PORT
    context = ssl.create_default_context()
    if port == 587:
        server = smtplib.SMTP(config.SMTP_HOST, port, timeout=15)
        server.starttls(context=context)
        return server
    return smtplib.SMTP_SSL(config.SMTP_HOST, port, timeout=15, context=context)


def send_email_notification(ticket, reply_text):
    """يرسل رد الدعم لإيميل المستخدم (لو كتبه). يرجع صح إذا انرسل، وما بيوقّف النظام عند أي فشل"""
    # 1. التأكد من التفعيل ومن وجود إيميل صحيح للمستخدم
    if not (config.EMAIL_ENABLED and config.EMAIL_ADDRESS and config.EMAIL_APP_PASSWORD):
        return False
    to_address = (ticket.get("contact_detail") or "").strip()
    if not reply_text or not is_valid_email(to_address):
        return False

    # 2. تجهيز الرسالة
    ticket_id = ticket.get("ticket_id")
    message = EmailMessage()
    message["Subject"] = f"IT Support - reply to your ticket {ticket_id}"
    message["From"] = config.EMAIL_ADDRESS
    message["To"] = to_address
    message.set_content(
        f"Hello,\n\nThe IT support team replied to your ticket {ticket_id}:\n\n"
        f"{reply_text}\n\n"
        "You can also read it in the IT Support chat: open the ticket with its ID and your Customer ID.\n\n"
        "IT Support Team"
    )

    # 3. الإرسال عبر Gmail (SSL) مع حماية النظام من الانهيار
    try:
        with open_smtp_connection() as server:
            server.login(config.EMAIL_ADDRESS, config.EMAIL_APP_PASSWORD)
            server.send_message(message)
        return True
    except Exception as exc:
        logger.warning("Email notification failed: %s", type(exc).__name__)
        return False
