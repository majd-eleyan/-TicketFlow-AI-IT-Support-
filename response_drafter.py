#  صياغة ردود آمنة ومحايدة للمستخدم
# يتدخل بعد أن يعرف النظام حالة التذكرة
import re

GREETING = "Hello,"
SIGNATURE = "Kind regards,\n\nIT Support Team"

# 1. الخطوات القادمة الآمنة حسب القسم
NEXT_STEPS = {
    "Software": "A support team member will review your report. Please save your open work and note any exact error text (without passwords).",
    "Hardware": "A support team member will review your report. Please keep the device available and note any lights or on-screen messages.",
    "Network": "A support team member will review your report. Please note the time of the issue and if nearby colleagues are affected.",
    "Authentication": "A support team member will review your report. Avoid repeated login attempts and never share passwords or codes with anyone.",
    "General": "A support team member will review your request and reply shortly.",
    "Other": "A support team member will review your request and reply shortly.",
}

# 2. رسائل الانتظار والتصعيد للموظف
HOLDING_MESSAGES = {
    "credential_request": "For security reasons, IT Support cannot share or ask for credentials in this channel. A human reviewer will follow up.",
    "security_incident": "Thank you for reporting. Your message has been routed to human review as a possible security matter. Do not enter credentials on suspicious pages.",
    "security_exception": "Permission changes cannot be approved through this channel. A human reviewer will contact you.",
    "threat_or_safety": "Your message has been passed to a human reviewer as a priority. If anyone is in immediate danger, contact emergency services.",
    "legal": "Your message has been forwarded to a human reviewer to determine proper handling.",
    "out_of_scope": "This request appears to be outside the scope of IT Support. A human reviewer will guide you to the right department.",
}
DEFAULT_HOLDING = "Thank you for your message. It has been passed to a human reviewer who will contact you."

# 3. العبارات المحظورة تماماً من الخروج للعميل
FORBIDDEN_PHRASES = [
    "password is", "has been fixed", "is now fixed", "we fixed", "has been resolved",
    "is resolved", "we have reset", "access has been granted", "refund", "exception approved"
]


def _wrap(body):
    """تغليف نص الرسالة بالترويسة والتوقيع"""
    return f"{GREETING}\n\n{body}\n\n{SIGNATURE}"


# خطوات حل ذاتي آمنة وجاهزة لكل قسم (تُستخدم للتذاكر العادية، وكاحتياط إذا فشل الـ LLM أو رفضنا خطواته)
SELF_SERVICE_STEPS = {
    "Software": [
        "Save your work, then close the application completely and open it again.",
        "Restart your computer if the problem continues.",
        "Check that the application is up to date, and note the exact error text if one appears.",
    ],
    "Hardware": [
        "Check that the power cable and all connections are firmly plugged in.",
        "Restart the device.",
        "Try a different port, cable or power outlet if possible, and note any lights or messages you see.",
    ],
    "Network": [
        "Turn Wi-Fi off and on again, or unplug and replug the network cable.",
        "Check whether other websites or systems are also unreachable.",
        "Restart your computer and test again.",
    ],
    "Authentication": [
        "Make sure Caps Lock is off and you are using the correct account name.",
        "Wait a few minutes before trying again; repeated attempts can lock the account.",
        "Never share passwords or codes with anyone, including IT Support.",
    ],
    "General": [
        "Restart the affected application or device and try again.",
        "Note exactly what happens and when it started.",
    ],
}

AUTO_CLOSING = ("If the problem continues after these steps, reply here in this chat. "
                "Your ticket stays open and the support team can see the full conversation.")

# خطوات الـ LLM لا تُقبل إلا إذا مرّت من هذا الفلتر الصارم
UNSAFE_STEP = re.compile(
    r"(registry|regedit|reinstall|re-install|factory reset|format(ting)?\b|disable|turn off (the )?(antivirus|firewall)|"
    r"sudo|rm -rf|\bbios\b|firmware|open (the )?(case|laptop|device)|unscrew|"
    r"password|passcode|credential|api key|secret|verification code|\botp\b|"
    r"https?://|powershell|\bcmd\b|command prompt|terminal|script)", re.I)


def clean_llm_steps(steps):
    """يتحقق من خطوات الحل التي اقترحها الـ LLM. يرجع قائمة نظيفة أو None إذا لم تكن آمنة."""
    if not isinstance(steps, list):
        return None
    cleaned = []
    for step in steps:
        step = " ".join(str(step).split()).lstrip("-•0123456789.) ").strip()
        if step:
            cleaned.append(step)
    if not 2 <= len(cleaned) <= 4:
        return None
    for step in cleaned:
        if len(step) > 160 or UNSAFE_STEP.search(step):
            return None
        if any(phrase in step.lower() for phrase in FORBIDDEN_PHRASES):
            return None
    return cleaned


def fallback_steps(category):
    return SELF_SERVICE_STEPS.get(category, SELF_SERVICE_STEPS["General"])


def make_draft_response(message, category, device_or_system="", steps=None):
    """صياغة مسودة رد للتذاكر العادية والكاملة.
    steps موجودة  -> تذكرة عادية يرد عليها النظام مباشرة بخطوات حل ذاتي.
    steps غير موجودة -> مسودة مقترحة لموظف الدعم (تذكرة عالية الأولوية)."""
    summary = message[:300] + "..." if len(message) > 300 else message
    where = f" (device/system: {device_or_system})" if device_or_system else ""

    body = (
        f"Thank you for contacting IT Support. We received your report about a {category.lower()} issue{where}.\n\n"
        f"Summary of what you reported: \"{summary}\"\n\n"
    )
    if steps:
        numbered = "\n".join(f"{i}. {step}" for i, step in enumerate(steps, 1))
        body += f"Steps you can try now:\n{numbered}\n\nNext step: {AUTO_CLOSING}"
    else:
        body += f"Next step: {NEXT_STEPS.get(category, NEXT_STEPS['Other'])}"
    return _wrap(body)


def make_holding_message(rule_name):
    """صياغة رسالة انتظار آمنة عند وجود تصعيد """
    return _wrap(HOLDING_MESSAGES.get(rule_name, DEFAULT_HOLDING))


#  أسئلة جاهزة حسب نوع المشكلة (تُستخدم لما الذكاء الاصطناعي غير متاح)
QUESTION_HINTS = [
    (["error", "exception"], "What is the exact error message you see, and in which application does it appear? (Please do not include passwords.)"),
    (["slow", "freez", "lag", "hang", "crash"], "Which application or website is slow or freezing, and does it happen all the time or only at certain moments?"),
    (["print", "scanner"], "Which printer is it, and what happens when you try to print (an error, nothing happens, or a wrong result)?"),
    (["wifi", "wi-fi", "internet", "network", "connect"], "Is the problem on Wi-Fi or a wired connection, and which sites or systems can you not reach?"),
    (["log in", "login", "sign in", "account", "vpn", "mfa"], "Which system or app are you trying to sign in to, and what message appears when it fails? (Please do not include passwords.)"),
    (["email", "outlook", "mail"], "Is the problem with sending, receiving or opening emails, and do you see any error message?"),
    (["down", "not working", "does not work", "doesn't work", "not work"], "Which specific system or application is not working, and what happens when you try to use it?"),
]


def make_follow_up_question(message, asked=0):
    """توليد سؤال محدد حسب مشكلة المستخدم؛ ولو سبق وسألنا نطلب تفاصيل أكثر"""
    if asked > 0:
        return ("Thanks, I still need a bit more detail: which device or application is affected, "
                "what exactly do you see on the screen (any error text), and when did it start?")
    text = message.lower()
    for keywords, question in QUESTION_HINTS:
        #  المطابقة من بداية الكلمة فقط: "change" ما بتطابق "hang"
        if any(re.search(r"\b" + re.escape(k), text) for k in keywords):
            return question
    return "Which device, application, or system is affected, and what exactly happens when the problem occurs?"


def is_allowlisted_draft(text, category=None):
    """يتأكد أن المسودة من القالب المحلي المسموح، وليست نصًا مولدًا حرًا."""
    if not isinstance(text, str) or not text.strip() or len(text) > 1600:
        return False
    lowered = text.lower()
    if any(phrase in lowered for phrase in FORBIDDEN_PHRASES):
        return False
    if not text.startswith(f"{GREETING}\n\n") or not text.endswith(f"\n\n{SIGNATURE}"):
        return False
    if category and category not in NEXT_STEPS:
        return False
    return "Next step:" in text and "Summary of what you reported:" in text

def make_received_message(ticket_id, priority):
    """رسالة للمستخدم لما التذكرة تنتظر مراجعة موظف"""
    return (
        f"Your ticket {ticket_id} was received and marked {priority} priority. "
        "A support team member will review it and reply here in this chat."
    )


def make_simple_chat_reply(ticket):
    """  رد بسيط للمتابعة لما الذكاء الاصطناعي غير متاح"""
    return (
        f"Thanks, your message was added to ticket {ticket['ticket_id']} (status: {ticket['status']}). "
        "A support team member can see the full conversation."
    )


def make_rejection_message():
    """  رد للطلبات الواضح إنها خارج نطاق الدعم التقني (تُرفض تلقائياً)"""
    return _wrap("This request is outside the scope of IT Support, so we cannot handle it here. "
                 "Please contact the relevant department.")
