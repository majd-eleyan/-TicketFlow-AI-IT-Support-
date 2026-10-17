
#  القواعد الحاسمة للتصنيف والأولوية والتصعيد لموظف
import re

# 1. كلمات التصنيف المفتاحية
CATEGORY_KEYWORDS = {
    "Authentication": ["log in", "login", "password", "vpn", "mfa", "2fa", "account", "تسجيل الدخول", "كلمة المرور"],
    "Network": ["wi-fi", "wifi", "network", "internet", "disconnect", "router", "الشبكة", "واي فاي", "انترنت"],
    "Hardware": ["laptop", "computer", "pc", "monitor", "screen", "keyboard", "printer", "battery", "charger"],
    "Software": ["outlook", "excel", "teams", "zoom", "chrome", "app", "software", "update", "email", "server", "database"],
    "General": ["how do i", "how to", "question", "policy", "training", "guide"],
}

# 2. قواعد التصعيد الأمني (تُفحص قبل كل شيء)
ESCALATION_RULES = [
    {
        "name": "credential_request",
        "pattern": r"\b(admin|password|credentials|api[ -]?key|secret[ -]?key)\b|كلمة السر|كلمة المرور|باسورد",
        "priority": "HIGH",
        "reason": "The message asks for a password or sensitive credentials.",
        "reviewer_action": "Do not share any credentials. Verify identity with security team."
    },
    {
        "name": "security_incident",
        "pattern": r"(hack|compromise|phishing|malware|ransomware|virus|breach|unauthorized|suspicious)",
        "priority": "HIGH",
        "reason": "Suspected security incident, malware, or unauthorized access.",
        "reviewer_action": "Forward to the security team immediately."
    },
    {
        "name": "threat_or_safety",
        "pattern": r"\b(threat|violence|bomb|weapon|fire|smoke|burning)\b|swollen battery|electric shock",
        "priority": "HIGH",
        "reason": "The message mentions physical safety risks or threats.",
        "reviewer_action": "Contact a manager or safety officer right away."
    },
    {
        "name": "out_of_scope",
        "pattern": r"\b(weather|recipe|joke|horoscope|lottery|football|movie|homework|salary|vacation)\b",
        "priority": "LOW",
        "reason": "The request is outside the IT Support scope.",
        "reviewer_action": "Inform the user that this is not an IT request."
    }
]


def classify_message(message):
    """تصنيف الرسالة بناءً على الكلمات الأكثر مطابقة"""
    text = message.lower()
    best_cat, max_hits = "Other", 0

    def keyword_hit(keyword):
        # كلمات متعددة مثل wi-fi تحتاج substring؛ الكلمات العادية تحتاج حدود كلمة.
        if re.search(r"[^\w]", keyword) or " " in keyword or "-" in keyword:
            return keyword in text
        return bool(re.search(r"(?<!\w)" + re.escape(keyword) + r"(?!\w)", text))

    for category, keywords in CATEGORY_KEYWORDS.items():
        hits = sum(1 for k in keywords if keyword_hit(k))
        if hits > max_hits:
            best_cat, max_hits = category, hits

    if max_hits == 0:
        return "Other", "No known IT keywords found; problem is unclear."
    return best_cat, f"Matched keywords for {best_cat} category."


def check_escalation(message):
    """التحقق من وجود أي خطر يستدعي التصعيد الفوري"""
    text = message.lower()
    for rule in ESCALATION_RULES:
        if re.search(rule["pattern"], text):
            return rule
    return None


def assess_priority(message, category, escalation=None):
    """تحديد أولوية التذكرة (HIGH / MEDIUM / LOW)"""
    if escalation:
        return escalation["priority"], escalation["reason"]

    text = message.lower()

    # أولوية عالية: توقف كامل أو أثر على كل الموظفين
    if re.search(r"(everyone|all users|company-wide|outage|network down|production down)", text):
        return "HIGH", "Wide-impact issue or total service outage reported."

    # أولوية منخفضة: استفسارات وأسئلة عامة
    if re.search(r"(how to|question|suggestion|not urgent|no rush)", text) or category == "Other":
        return "LOW", "General question or low-impact non-urgent request."

    # أولوية متوسطة: مشكلة اعتيادية لموظف واحد
    return "MEDIUM", f"Standard IT issue affecting single user in {category}."