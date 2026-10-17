"""
 إدارة الـ Context قبل إرسال أي شي للنموذج:
Context = System Prompt + Ticket Facts + آخر N رسائل (Sliding Window) + السؤال الجديد
"""
import config
from prompts import CHAT_SYSTEM_PROMPT


def sliding_window_strategy(history, last_n=None):
    """بنرسل بس آخر N رسائل، والباقي يضل مخزّن بقاعدة البيانات"""
    last_n = last_n or config.CONTEXT_WINDOW
    return history[-last_n:]


def ticket_facts(ticket):
    """Fact Memory: معلومات التذكرة الثابتة (بدل ما نعتمد على المحادثة كلها)"""
    return (
        "# Ticket facts\n"
        f"- Ticket: {ticket['ticket_id']}\n"
        f"- Category: {ticket['category']} | Priority: {ticket['priority']} | Status: {ticket['status']}\n"
        f"- Department: {ticket['department'] or '-'} | Device/system: {ticket['device_or_system'] or '-'}\n"
        f"- Original problem: {(ticket['message'] or '')[:config.MAX_CONTEXT_CHARS]}"
    )


def build_context(ticket, history, question):
    """تجهيز الرسائل النهائية للنموذج"""
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT + "\n\n" + ticket_facts(ticket)}]

    for m in sliding_window_strategy(history):
        text = m["content"][:config.MAX_CONTEXT_CHARS]       # تنظيف: قص الرسائل الطويلة
        if m["role"] == "user":
            messages.append({"role": "user", "content": text})
        elif m["role"] == "staff":
            messages.append({"role": "assistant", "content": f"[Support staff] {text}"})
        else:
            messages.append({"role": "assistant", "content": text})

    messages.append({"role": "user", "content": question})
    return messages
