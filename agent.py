"""
الكنترول
full System 
Workflow:
Submit -> Validate -> Security check -> Classify -> Missing details
       -> Priority policy -> Draft or Escalate -> Human review -> Save
ملف agent.py 
هو الكنترول و المدبر لكل العملية؛
 أول ما توصل رسالة الزبون بياخدها
 بعدين بيفحصها أمنياً حتى يضمن إنه ما فيها خطورة
 ولو كانت خطيرة بيحولها فوراً للموظف
 أما لو آمنة، بروح بيكشف شو نوع المشكلة
 وإذا شافها غامضة ومش مفهومة بيرجع يسأل الزبون ويفهم منه أكتر
 وإذا كانت واضحة بيحدد أولوية التذكرة وبيكتب لها مسودة رد جاهزة
 وآخر إشي بيحفظ كل إشي بقاعدة البيانات
"""

import logging
import re
import sqlite3
import config
import notifications
import database
import llm_client
import policy
import response_drafter
import validation
from memory_store import MemoryStore  
from models import Decision

logger = logging.getLogger(__name__)

# ما منسمح لسؤال النموذج يطلب كلمات سر أو أكواد
FORBIDDEN_QUESTION = re.compile(r"(password|passcode|credential|secret|api key|verification code|كلمة)", re.I)


def conversation_text(history, new_answer=""):
    """  تحويل المحادثة لنص (الموظف/المساعد) ليفهم النموذج السؤال الذي أجاب عليه المستخدم"""
    names = {"user": "Employee", "ai": "IT assistant", "staff": "Support staff"}
    lines = [f"{names.get(m['role'], 'IT assistant')}: {m['content']}" for m in history
             if not m["content"].startswith("✅")]
    if new_answer:
        lines.append(f"Employee: {new_answer}")
    return "\n".join(lines)


def _auto_reject(d, why, reply, first_step):
    """  رفض تلقائي للطلبات الخارجة عن نطاق الدعم التقني (بدون موظف)"""
    d.action = "reject"
    d.status = "REJECTED"
    d.category = "Other"
    d.classification_reason = why
    d.priority, d.priority_reason = "LOW", why
    d.draft_response = reply
    d.action_reason = "Clearly not an IT request, so it is classified and rejected automatically."
    d.review_needed = False
    d.steps.append(first_step)
    d.steps.append("Action: reject automatically (no human review needed).")


def decide(message, device_or_system="", allow_ask=True, conversation="", asked=0):
    """دالة اتخاذ القرار: تمشي في 4 خطوات واضحة لتحديد مصير التذكرة"""
    d = Decision()

    # 1. فحص الأمان 
    # بيفحص المعنى والخطورة
    rule = policy.check_escalation(message)
    if rule and rule["name"] == "out_of_scope":
        #   طلب واضح إنه مو تقني: نصنفه ونرفضه تلقائياً بدون ما يروح للموظف
        _auto_reject(d, rule["reason"], response_drafter.make_rejection_message(),
                     f"Security check: rule '{rule['name']}' matched.")
        return d
    if rule:
        d.action = "escalate"
        d.status = "ESCALATED"
        if rule["name"] == "out_of_scope":
            d.category = "Other"
            d.classification_reason = "The request is outside the IT Support scope."
        else:
            d.category, d.classification_reason = policy.classify_message(message)
        d.priority, d.priority_reason = policy.assess_priority(message, d.category, rule)
        d.draft_response = response_drafter.make_holding_message(rule["name"])
        d.escalation_reason = rule["reason"]
        d.recommended_reviewer_action = rule["reviewer_action"]
        d.action_reason = "The message matched a security/safety escalation rule, so it is routed to a human reviewer without troubleshooting."
        d.review_needed = True
        d.steps.append(f"Security check: escalation rule '{rule['name']}' matched.")
        d.steps.append("Action: escalate to a human reviewer with a safe holding message.")
        return d
    d.steps.append("Security check: no escalation rule matched.")

    # 2. التصنيف (سؤال الذكاء الاصطناعي أو القواعد عن قسم المشكلة)
    llm_res = llm_client.get_llm_decision(message, conversation)   #  مع المحادثة كاملة
    if llm_res and llm_res["action"] == "OUT_OF_SCOPE":
        # النموذج اكتشف إن الطلب مو تقني: رد مهذب من النموذج ورفض تلقائي
        reply = llm_res["reply"]
        if not reply or not response_drafter.is_allowlisted_draft(reply) or FORBIDDEN_QUESTION.search(reply):
            reply = response_drafter.make_rejection_message()
        _auto_reject(d, llm_res["reason"], reply, "Classification (AI model): not an IT request.")
        return d
    if llm_res:
        d.category, d.classification_reason = llm_res["category"], llm_res["reason"]
        d.steps.append(f"Classification (AI model): {d.category}.")
    else:
        d.category, d.classification_reason = policy.classify_message(message)
        d.steps.append(f"Classification (local rules): {d.category}. AI model not used: {llm_client.last_error}.")

    # 3. فحص الغموض (إذا كانت المشكلة غير مفهومة نهائياً 'Other')
    if allow_ask and d.category == "Other":
        d.priority, d.priority_reason = policy.assess_priority(message, d.category)
        d.action = "ask_for_info"
        d.status = "WAITING_FOR_INFO"
        d.action_reason = "The problem is unclear, so the copilot asks one specific follow-up question before proceeding."
        d.missing_information = "The message does not contain enough detail to classify the problem."
        # السؤال من النموذج حسب مشكلة المستخدم؛ وإذا ما توفر نطلبه بطلب منفصل، وآخر شي السؤال الجاهز
        question = (llm_res or {}).get("question", "")
        if llm_res and not question:
            question = llm_client.get_follow_up_question(conversation or message) or ""
        if not question or FORBIDDEN_QUESTION.search(question):
            question = response_drafter.make_follow_up_question(message, asked)
        d.follow_up_question = question
        d.review_needed = False
        d.steps.append("Action: ask the user for more information.")
        return d

    # 4. تجهيز الرد والأولوية للمشاكل الواضحة
    d.priority, d.priority_reason = policy.assess_priority(message, d.category)
    d.action = "draft_response"
    d.steps.append(f"Priority: {d.priority}.")

    # مو كل تذكرة بتروح للموظف: بس الأولوية العالية أو المشاكل غير الواضحة
    needs_human = d.priority == "HIGH" or d.category == "Other"

    if needs_human:
        # مسودة مقترحة للموظف (بدون خطوات حل)، والمستخدم يستلم رسالة "تم الاستلام" فقط
        d.draft_response = response_drafter.make_draft_response(message, d.category, device_or_system)
    else:
        # تذكرة عادية: خطوات حل ذاتي. الـ LLM يقترحها وتمر على فلتر أمان، وإلا نستخدم القوالب الجاهزة
        steps = response_drafter.clean_llm_steps(
            llm_client.get_troubleshooting_steps(message, d.category, device_or_system))
        source = "AI model (validated)" if steps else "curated templates"
        steps = steps or response_drafter.fallback_steps(d.category)
        d.draft_response = response_drafter.make_draft_response(message, d.category, device_or_system, steps)
        d.steps.append(f"Self-service steps: {source}.")
        if not response_drafter.is_allowlisted_draft(d.draft_response):
            needs_human = True

    if needs_human:
        d.status = "PENDING_HUMAN_REVIEW"
        d.review_needed = True
        d.action_reason = "High priority or unclear problem, so a human reviewer must look at it."
        d.steps.append("Action: send to a human reviewer.")
    else:
        d.status = "CLASSIFIED"
        d.review_needed = False
        d.action_reason = "Standard problem, so the user gets safe self-service steps right away. Staff can still follow up."
        d.steps.append("Action: reply to the user directly with self-service steps (no human review needed).")
    return d


def messages_for_user(decision, ticket, history, question):
    """  رسائل النظام للمستخدم بالشات حسب القرار
    - ask_for_info: السؤال الثابت من النظام (ما بيتغير)
    - غير هيك: رد + رسالة "تم" مع شكر، وبعدها الواجهة جاهزة لتذكرة جديدة"""
    ticket_id = ticket["ticket_id"]
    if decision.action == "ask_for_info":
        return [decision.follow_up_question]

    if decision.status == "PENDING_HUMAN_REVIEW":
        body = response_drafter.make_received_message(ticket_id, decision.priority)
    elif decision.status == "CLASSIFIED":
        # الرد التلقائي: قالب محلي + خطوات حل ذاتي (من الـ LLM بعد الفحص، أو من القوالب الجاهزة)
        body = decision.draft_response
    else:                                  # ESCALATED أو REJECTED
        body = decision.draft_response

    if decision.status == "REJECTED":
        done = f"✅ Done. Your request was recorded as ticket {ticket_id} and closed as not an IT request. Thank you!"
    else:
        done = f"✅ Done. Your ticket {ticket_id} has been created. Thank you for contacting IT Support!"
    done += " If you have another problem, just describe it below to open a new ticket."
    return [body, done]


def _notify_if_needed(ticket):
    """  إشعار ديسكورد بس للتذاكر اللي بتحتاج موظف"""
    if ticket and ticket["review_needed"]:
        notifications.send_discord_notification(ticket)


# workflow الكامل
def submit_ticket(customer_id, message, metadata=None):
    """دالة استقبال التذكرة وإدخالها للنظام وقاعدة البيانات"""
    metadata = metadata or {}
    contact_detail = validation.clean_optional_field(metadata.get("contact_detail", ""))
    department = validation.clean_optional_field(metadata.get("department", ""))
    device_or_system = validation.clean_optional_field(metadata.get("device_or_system", ""))
    customer_id = validation.normalize_whitespace(customer_id)
    if contact_detail and not notifications.is_valid_email(contact_detail):
        return {"ok": False, "error": "Invalid email address."}

    # فحص وتنظيف النص من كلمات السر
    result = validation.validate_input(customer_id, message)
    if not result.ok:
        return {"ok": False, "error": result.error}

    # اتخاذ القرار
    decision = decide(result.clean_message, device_or_system)

    # تجهيز التذكرة وحفظها
    ticket = {
        "customer_id": customer_id,
        "contact_detail": contact_detail or None,
        "department": department or None,
        "message": result.clean_message,
        "device_or_system": device_or_system or None,
        **decision.to_ticket_fields()
    }

    warning = (
        "Some sensitive information (passwords, keys, or card numbers) was automatically removed from your message."
        if result.secrets_removed else None
    )

    try:
        ticket_id = database.create_ticket(ticket)
        saved = database.get_ticket_by_id(ticket_id)
        #  نحفظ بداية المحادثة: رسالة المستخدم + رد النظام
        memory = MemoryStore(ticket_id)
        replies = messages_for_user(decision, saved, [], result.clean_message)
        memory.add_user_message(result.clean_message)
        for reply in replies:
            memory.add_ai_message(reply)
        _notify_if_needed(saved)
        return {"ok": True, "ticket": saved, "steps": decision.steps, "warning": warning}
    except sqlite3.Error:
        logger.exception("Could not save ticket")
        return {"ok": False, "error": "Database error occurred."}


def add_clarification(ticket_id, clarification):
    """دالة استقبال التوضيح من المستخدم عند إعادة السؤال"""
    try:
        ticket = database.get_ticket_by_id(ticket_id)
    except sqlite3.Error:
        return {"ok": False, "error": "Database error."}

    if not ticket:
        return {"ok": False, "error": "Ticket not found."}

    #نفحص التوضيح وننظفه من كلمات السر قبل استخدامه
    result = validation.validate_input(ticket["customer_id"], clarification, min_chars=1)
    if not result.ok:
        return {"ok": False, "error": result.error}

    # دمج النص القديم مع التوضيح الجديد وإعادة التقييم
    combined = f"{ticket['message']} - Additional info: {result.clean_message}"
    memory = MemoryStore(ticket_id)
    history = memory.get_history()      # المحادثة قبل التوضيح الجديد (الـ context)

    #  كل رسالة مستخدم سابقة = سؤال تم طرحه؛ نسأل مرة ثانية إذا المعلومات لسا ناقصة (بحد أقصى)
    asked = sum(1 for m in history if m["role"] == "user")
    decision = decide(combined, ticket["device_or_system"] or "",
                      allow_ask=asked < config.MAX_FOLLOW_UPS,
                      conversation=conversation_text(history, result.clean_message), asked=asked)

    fields = {"message": combined, **decision.to_ticket_fields()}

    try:
        database.update_ticket_fields(ticket_id, fields, "Clarification received.")
        saved = database.get_ticket_by_id(ticket_id)
        # نحفظ التوضيح ورد النظام بالمحادثة
        replies = messages_for_user(decision, saved, history, result.clean_message)
        memory.add_user_message(result.clean_message)
        for reply in replies:
            memory.add_ai_message(reply)
        _notify_if_needed(saved)
        return {"ok": True, "ticket": saved, "steps": decision.steps, "warning": None}
    except sqlite3.Error:
        return {"ok": False, "error": "Database error."}


def handle_user_message(ticket_id, text):
    """أي رسالة من المستخدم داخل الشات بعد إنشاء التذكرة"""
    try:
        ticket = database.get_ticket_by_id(ticket_id)
    except sqlite3.Error:
        return {"ok": False, "error": "Database error."}
    if not ticket:
        return {"ok": False, "error": "Ticket not found."}
    if ticket["status"] == "CLOSED":
        return {"ok": False, "error": "This ticket is closed. Please open a new ticket."}

    # لو النظام كان ينتظر معلومات، هاي الرسالة هي الجواب
    if ticket["status"] == "WAITING_FOR_INFO":
        return add_clarification(ticket_id, text)

    result = validation.validate_input(ticket["customer_id"], text, min_chars=1)
    if not result.ok:
        return {"ok": False, "error": result.error}

    memory = MemoryStore(ticket_id)
    history = memory.get_history()          # الـ history قبل الرسالة الجديدة
    steps = []

    try:
        rule = policy.check_escalation(result.clean_message)
        if rule:
            # رسالة خطيرة: نصعّد التذكرة مباشرة برسالة انتظار آمنة
            database.update_ticket_fields(ticket_id, {
                "status": "ESCALATED", "agent_action": "escalate", "priority": rule["priority"],
                "priority_reason": rule["reason"], "escalation_reason": rule["reason"],
                "recommended_reviewer_action": rule["reviewer_action"], "review_needed": 1,
            }, "Escalated after a follow-up message.")
            reply = response_drafter.make_holding_message(rule["name"])
            steps.append(f"Security check: escalation rule '{rule['name']}' matched.")
        else:
            # المتابعة لا ترسل troubleshooting مولدًا تلقائيًا؛ الرد هنا deterministic فقط.
            reply = response_drafter.make_simple_chat_reply(ticket)
            steps.append("Reply used a deterministic safe template; no automatic LLM troubleshooting.")

        memory.add_user_message(result.clean_message)
        memory.add_ai_message(reply)
        saved = database.get_ticket_by_id(ticket_id)
        if rule:
            _notify_if_needed(saved)
        return {"ok": True, "ticket": saved, "steps": steps, "warning": None}
    except sqlite3.Error:
        logger.exception("Could not save message")
        return {"ok": False, "error": "Database error occurred."}


def staff_action(ticket_id, action, note=""):
    """  قرار الموظف (APPROVE / REJECT / ESCALATE / CLOSE)
    ملاحظة الموظف = الرد على المستخدم: بتنحفظ كـ Approved response وبتنرسل بالشات"""
    ticket = database.get_ticket_by_id(ticket_id)
    if not ticket:
        return {"ok": False, "error": "Ticket not found."}

    note, _ = validation.redact_secrets(validation.normalize_whitespace(note))
    memory = MemoryStore(ticket_id)
    if action not in {"APPROVE", "REJECT", "ESCALATE", "CLOSE"}:
        return {"ok": False, "error": "Unknown action."}

    if action == "APPROVE":
        # لو في ملاحظة بتصير هي الرد المعتمد، وإلا بنعتمد مسودة النظام
        database.save_reviewer_decision(ticket_id, "APPROVED", note, approved_text=note or None)
    elif action == "REJECT":
        database.save_reviewer_decision(ticket_id, "REJECTED", note)
    elif action == "ESCALATE":
        database.update_ticket_status(ticket_id, "ESCALATED", note or "Escalated by reviewer")
    elif action == "CLOSE":
        database.update_ticket_status(ticket_id, "CLOSED", note or "Closed by reviewer")
    reply_text = ""
    # الرد المعتمد (للشات وللإيميل) هو نفسه دائماً:
    #   APPROVE + ملاحظة  -> نص الموظف
    #   APPROVE بدون ملاحظة -> مسودة النظام
    # REJECT / ESCALATE / CLOSE: الملاحظة داخلية فقط ولا يُرسل أي رد للمستخدم.
    if note:
        database.update_ticket_fields(ticket_id, {"reviewer_note": note}, "Staff note saved.")
    if action == "APPROVE":
        if note:
            reply_text = note
            memory.add_staff_message(note)
        elif ticket["draft_response"]:
            reply_text = ticket["draft_response"]
            sent = [m["content"] for m in memory.get_history() if m["role"] == "ai"]
            if reply_text not in sent:
                memory.add_ai_message(reply_text)

    #  إذا المستخدم كتب إيميله، نفس الرد المعتمد بينبعت له على الإيميل
    emailed = notifications.send_email_notification(ticket, reply_text) if reply_text else False
    return {"ok": True, "emailed": emailed}
