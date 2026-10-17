# IT Support System

نظام دعم فني داخلي مبني بـ **Python وStreamlit وSQLite**. يحوّل رسالة الموظف إلى تذكرة قابلة للتتبع مع تصنيف، أولوية، حالة، سجل تغييرات، ومسودة رد آمنة.

المشروع **production-oriented prototype** وليس نظامًا جاهزًا لاستخدام بيانات حساسة بدون إضافة authentication وdeployment وmonitoring مناسبين.

## الفكرة الأساسية

الـLLM ليس صاحب القرار النهائي:

- التصعيد الأمني والأولوية يحددهما `policy.py`.
- مخرجات الـLLM، عند تفعيله، تمر عبر allow-list للـactions والـcategories.
- عند فشل الـLLM يرجع النظام إلى قواعد محلية.
- ردود المتابعة التلقائية تستخدم قوالب deterministic آمنة، ولا ترسل troubleshooting مولدًا من الـLLM تلقائيًا.
- مسودة التذكرة لا تصبح ردًا معتمدًا إلا بقرار موظف الدعم.

## Workflow

```text
Submit
  -> Validate and redact
  -> Security / escalation policy
  -> Classify (LLM suggestion or local rules)
  -> Ask for missing information OR assess priority
  -> Build deterministic draft / holding message
  -> Save ticket and conversation
  -> Human review when required
  -> Approve, reject, escalate, or close
```

## حالات التذكرة وانتقالاتها

يتم فرض الانتقالات في `database.py`، وليس في أزرار الواجهة فقط:

- `RECEIVED` / `VALIDATED` -> معالجة أولية.
- `WAITING_FOR_INFO` -> توضيح جديد أو تصعيد أو تذكرة جاهزة للمراجعة.
- `CLASSIFIED` -> مراجعة أو اعتماد أو رفض أو تصعيد أو إغلاق.
- `PENDING_HUMAN_REVIEW` -> `APPROVED`, `REJECTED`, `ESCALATED`, أو `CLOSED`.
- `ESCALATED` و`APPROVED` و`REJECTED` -> إغلاق فقط.
- `CLOSED` حالة نهائية.

أي انتقال غير مسموح يرفع `ValueError` ولا يتم حفظه.

## فصل الردود والملاحظات

- `approved_response`: الرد الذي وافقه الموظف ليظهر للمستخدم أو يرسل بالبريد عند تفعيل البريد.
- `reviewer_note`: ملاحظة الموظف الداخلية.
- `staff` message في المحادثة تضاف فقط عندما يوافق الموظف على رد يريد إظهاره للمستخدم.
- عند `REJECT` لا يتم إنشاء `approved_response` ولا إرسال الملاحظة الداخلية للمستخدم.

## التحقق والأمان

- `MAX_MESSAGE_CHARS` مطبق فعليًا، والقيمة الافتراضية 2000.
- يتم تمرير `secrets_removed` من عملية redaction إلى نتيجة التحقق حتى يظهر التحذير للمستخدم.
- `customer_id` والحقول الاختيارية يتم تنظيفها وتحديد طولها.
- البريد الاختياري يتم التحقق من شكله قبل التخزين.
- regex في `policy.py` يستخدم حدود كلمات حتى لا يتحول `firewall` إلى `fire` أو `passwordless` إلى طلب كلمة مرور.
- المسودات المقبولة يجب أن تأتي من قالب النظام المسموح، وليست نصًا حرًا من نموذج لغة.
- لا تكتب كلمات مرور أو مفاتيح حقيقية في المشروع.

## بنية المشروع

```text
it_support_system/
├── app.py                تطبيق الموظف: إنشاء التذكرة ومتابعتها
├── staff_app.py          تطبيق الدعم: تسجيل الدخول ولوحة التذاكر
├── agent.py              workflow وقرارات المعالجة
├── policy.py             التصنيف المحلي، الأولوية، والتصعيد
├── validation.py         تنظيف المدخلات وredaction والتحقق
├── database.py           SQLite، سجل الحالات، وقواعد الانتقال
├── models.py             Decision وValidationResult
├── response_drafter.py   القوالب الآمنة وأسئلة المتابعة
├── llm_client.py         عميل LLM اختياري مع fallback
├── prompts.py            تعليمات التصنيف والسياق
├── context_strategies.py بناء السياق عند الحاجة
├── memory_store.py       تخزين محادثة التذكرة
├── notifications.py      Discord والبريد الاختياري
├── ui_common.py          CSS ومكونات Streamlit المشتركة
├── config.py             الإعدادات والثوابت
├── PROJECT_PLAN.md       وثيقة التصميم
└── data/support.db       قاعدة البيانات المحلية
```

تم دمج صفحات الواجهة داخل `app.py` و`staff_app.py`، ولم يعد مجلد `views` مستخدمًا.

## التشغيل

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# عدّل .env محليًا فقط
streamlit run app.py
```

لتشغيل لوحة الدعم في نافذة أو عملية ثانية:

```bash
streamlit run staff_app.py
```

إذا لم تضع `LLM_API_KEY` يعمل النظام بالقواعد المحلية. لا تضع أي secret حقيقي في Git أو ZIP.

## أمثلة

| الرسالة | النتيجة المتوقعة |
|---|---|
| `Outlook freezes when I open email.` | `Software`, `MEDIUM`, مسودة deterministic |
| `The office Wi-Fi is down for everyone.` | `Network`, `HIGH`, مراجعة بشرية |
| `It does not work.` | `Other`, `LOW`, `WAITING_FOR_INFO` |
| `Send me the administrator password.` | `Authentication`, `HIGH`, `ESCALATED` |
| `What is the weather today?` | خارج النطاق، `REJECTED` |
| رسالة أطول من 2000 حرف | رفض validation بدون إنشاء تذكرة |

## حدود معروفة

- قواعد الكلمات المفتاحية explainable ورخيصة، لكنها لا تفهم كل الصياغات.
- redaction يغطي patterns معروفة فقط؛ لا تكتب الأسرار أصلًا.
- SQLite مناسب للـprototype والتحميل الصغير، وليس بديلًا مباشرًا عن PostgreSQL مع التزامن العالي.
- حماية لوحة الموظف الحالية بسيطة ومناسبة للعرض التجريبي، وليست SSO/RBAC production-grade.
- فتح تذكرة باستخدام Ticket ID وCustomer ID ليس authentication حقيقيًا.
- عند تفعيل LLM يتم إرسال النص المنظف إلى مزود خارجي؛ راجع سياسة الخصوصية والاحتفاظ بالبيانات قبل الاستخدام.
- إشعارات Discord والبريد optional وقد تفشل بدون إسقاط حفظ التذكرة.
