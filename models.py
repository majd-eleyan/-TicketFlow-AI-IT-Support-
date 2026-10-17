
#   لنقل المعلومات بين ملفات المشروع
from dataclasses import dataclass, field

@dataclass
# فحص مدخلات المستخدم قبل معالجتها
class ValidationResult:
    ok: bool                      # هل الرسالة صالحة؟ (True/False)
    clean_message: str = ""       # النص بعد التنظيف
    error: str = ""               # رسالة الخطأ إن وجدت
    secrets_removed: bool = False # هل تم حذف بيانات حساسة من الرسالة؟

@dataclass
# تخزن نتائج قرارات الوكيل
class Decision:
    action: str = ""                          # القرار (ask_for_info | draft_response | escalate | reject)
    category: str = "Other"                   # التصنيف
    classification_reason: str = ""           # سبب التصنيف
    priority: str = "LOW"                     # الأولوية
    priority_reason: str = ""                 # سبب الأولوية
    status: str = "RECEIVED"                  # الحالة
    action_reason: str = ""                   # سبب اختيار هذا الإجراء
    missing_information: str = ""             # وصف المعلومة الناقصة (عند الغموض)
    follow_up_question: str = ""              # سؤال المتابعة للمستخدم
    draft_response: str = ""                  # مسودة الرد الموجهة للمستخدم
    review_needed: bool = False               # هل تحتاج مراجعة بشرية
    escalation_reason: str = ""               # سبب التصعيد
    recommended_reviewer_action: str = ""     # الإجراء المقترح للمراجع البشري
    steps: list = field(default_factory=list) # خطوات القرار لعرضها بالواجهة

    def to_ticket_fields(self):
        """تحويل البيانات لشكل يفهمه جدول قاعدة البيانات ببساطة"""
        return {
            "category": self.category,
            "classification_reason": self.classification_reason,
            "priority": self.priority,
            "priority_reason": self.priority_reason,
            "status": self.status,
            "agent_action": self.action,
            "action_reason": self.action_reason,
            "missing_information": self.missing_information,
            "follow_up_question": self.follow_up_question,
            "draft_response": self.draft_response,
            "review_needed": self.review_needed,
            "escalation_reason": self.escalation_reason,
            "recommended_reviewer_action": self.recommended_reviewer_action,
        }