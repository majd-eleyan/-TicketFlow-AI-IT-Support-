"""
أدوات مشتركة بين واجهتي New Ticket و Dashboard (ستايل + دوال مساعدة)
"""
import logging
import streamlit as st
import config
import database

logger = logging.getLogger(__name__)

PRIORITY_ICONS = {"HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🟢"}

# ألوان شارات الحالة
STATUS_COLORS = {
    "WAITING_FOR_INFO": "#d97706", "CLASSIFIED": "#2563eb", "PENDING_HUMAN_REVIEW": "#7c3aed",
    "ESCALATED": "#dc2626", "APPROVED": "#16a34a", "REJECTED": "#6b7280", "CLOSED": "#374151",
}

CSS = """
<style>
.block-container {padding-top: 2rem; max-width: 1100px;}
.page-header {background: linear-gradient(135deg, #4f46e5, #7c3aed); color: #fff;
              padding: 1.1rem 1.5rem; border-radius: 16px; margin-bottom: 1.2rem;}
.ph-title {font-size: 1.7rem; font-weight: 700; line-height: 1.2;}
.ph-sub {opacity: .9; margin-top: .25rem;}
.badge {display: inline-block; padding: 2px 12px; border-radius: 999px; font-size: .78rem;
        font-weight: 600; color: #fff; margin-right: 6px;}
/*   شكل الشات: رد النظام بطاقة ملونة ناعمة، ورسالة المستخدم فقاعة متدرجة على اليمين */
[data-testid="stChatMessage"] {background: transparent; border: none; padding: .55rem 0; gap: .8rem;}
[data-testid="stChatMessageAvatarAssistant"], [data-testid="stChatMessageAvatarCustom"] {
        background: linear-gradient(135deg, #4f46e5, #a855f7); border-radius: 50%;
        width: 2.4rem; height: 2.4rem; box-shadow: 0 4px 12px rgba(124,58,237,.35);}
[data-testid="stChatMessageAvatarUser"] {display: none;}
/* رد النظام */
[data-testid="stChatMessageContent"] {
        background: linear-gradient(135deg, rgba(79,70,229,.09), rgba(168,85,247,.07));
        border: 1px solid rgba(124,58,237,.22); border-radius: 6px 20px 20px 20px;
        padding: .8rem 1.2rem; box-shadow: 0 2px 10px rgba(79,70,229,.07);}
[data-testid="stChatMessageContent"] p {line-height: 1.65; margin-bottom: .35rem;}
/* رد موظف الدعم (أخضر) */
[data-testid="stChatMessage"]:has(.staff-mark) [data-testid="stChatMessageContent"] {
        background: linear-gradient(135deg, rgba(16,185,129,.12), rgba(5,150,105,.06)); border-color: rgba(16,185,129,.4);}
[data-testid="stChatMessage"]:has(.staff-mark) [data-testid="stChatMessageAvatarCustom"] {
        background: linear-gradient(135deg, #059669, #34d399); box-shadow: 0 4px 12px rgba(16,185,129,.35);}
/* رسالة المستخدم */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {flex-direction: row-reverse;}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] {
        flex: 0 1 auto; width: fit-content; max-width: 78%;
        background: linear-gradient(135deg, #4f46e5, #7c3aed); border: none; border-radius: 20px 6px 20px 20px;
        box-shadow: 0 6px 16px rgba(79,70,229,.35);}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] * {
        color: #fff !important;}
.staff-mark {display: none;}
.staff-name {font-size: .78rem; font-weight: 700; color: #10b981; letter-spacing: .02em; margin-bottom: .2rem;}
/* مربع الكتابة */
[data-testid="stChatInput"] {border-radius: 30px; border: 1.5px solid rgba(124,58,237,.35);
        box-shadow: 0 8px 28px rgba(79,70,229,.18); transition: all .2s;}
[data-testid="stChatInput"]:focus-within {border-color: #7c3aed; box-shadow: 0 8px 32px rgba(124,58,237,.38);}
[data-testid="stChatInputSubmitButton"] {background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
        color: #fff !important; border-radius: 50% !important;}
/* مؤشر "يكتب..." */
.typing {display: inline-flex; gap: 6px; padding: .5rem .2rem;}
.typing span {width: 9px; height: 9px; border-radius: 50%; background: #7c3aed; animation: bounce 1.2s infinite ease-in-out;}
.typing span:nth-child(2) {animation-delay: .15s; background: #a855f7;}
.typing span:nth-child(3) {animation-delay: .3s; background: #c084fc;}
@keyframes bounce {0%, 80%, 100% {transform: translateY(0); opacity: .45;} 40% {transform: translateY(-7px); opacity: 1;}}
/* شاشة الترحيب */
.hero {text-align: center; padding: 2.2rem 0 1.4rem; animation: fadeUp .7s ease;}
.hero-icon {font-size: 3.2rem; width: 5.2rem; height: 5.2rem; line-height: 5.2rem; margin: 0 auto 1rem; border-radius: 28px;
        background: linear-gradient(135deg, #4f46e5, #a855f7); box-shadow: 0 14px 34px rgba(124,58,237,.45);}
.hero-title {font-size: 2.3rem; font-weight: 800; line-height: 1.2;
        background: linear-gradient(90deg, #4f46e5, #a855f7, #ec4899); -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;}
.hero-sub {opacity: .7; margin: .6rem 0 1.4rem; font-size: 1.05rem;}
.chips {display: flex; flex-wrap: wrap; gap: .6rem; justify-content: center;}
.chip {padding: .45rem 1rem; border-radius: 999px; font-size: .88rem; font-weight: 600;
        background: rgba(124,58,237,.12); border: 1px solid rgba(124,58,237,.3);}
@keyframes fadeUp {from {opacity: 0; transform: translateY(14px);} to {opacity: 1; transform: translateY(0);}}
/* شريط التذكرة */
.ticket-bar {display: flex; align-items: center; gap: .5rem; padding: .55rem 1rem; border-radius: 14px; margin: .6rem 0 .8rem;
        background: linear-gradient(135deg, rgba(79,70,229,.12), rgba(168,85,247,.08)); border: 1px solid rgba(124,58,237,.25);}
div[data-testid="stMetric"] {background: rgba(128,128,128,.07); border-radius: 12px; padding: .6rem .9rem;}
footer {visibility: hidden;}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(title, subtitle):
    st.markdown(
        f'<div class="page-header"><div class="ph-title">{title}</div><div class="ph-sub">{subtitle}</div></div>',
        unsafe_allow_html=True,
    )


def badge(text, color):
    return f'<span class="badge" style="background:{color}">{text}</span>'


def status_badge(status):
    return badge(status, STATUS_COLORS.get(status, "#6b7280"))


def safe_call(func, *args):
    """تنفيذ دالة بأمان دون إظهار أخطاء برمجية للمستخدم"""
    try:
        return True, func(*args)
    except ValueError as exc:
        st.error(str(exc))
    except Exception:
        logger.exception("Database call failed")
        st.error("Something went wrong while accessing the ticket database. Please try again.")
    return False, None


def show_draft(text, title="AI draft"):
    """عرض مسودة الرد مع التنبيه بأنها تنتظر المراجعة البشرية"""
    st.markdown(f"**{title}**")
    st.warning(config.DRAFT_LABEL, icon="✍️")
    st.info(text)


def get_conversation(ticket):
    """رسائل المحادثة؛ وللتذاكر القديمة (قبل الشات) نعرض رسالتها الأصلية فقط"""
    messages = database.get_messages(ticket["ticket_id"])
    if not messages:
        messages = [{"role": "user", "content": ticket["message"], "created_at": ticket["created_at"]}]
    return messages


def render_chat(messages, staff_label="Support team"):
    """رسم المحادثة: المستخدم / النظام / موظف الدعم"""
    for m in messages:
        if m["role"] == "user":
            with st.chat_message("user"):
                st.markdown(m["content"])
        elif m["role"] == "staff":
            with st.chat_message("assistant", avatar="🧑‍💻"):
                st.markdown(f"<span class='staff-mark'></span><div class='staff-name'>{staff_label.upper()} · {m['created_at']}</div>",
                            unsafe_allow_html=True)
                st.markdown(m["content"])
        else:
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(m["content"])


def typing_indicator():
    """نقاط متحركة تظهر أثناء ما النظام يجهز الرد"""
    st.markdown("<div class='typing'><span></span><span></span><span></span></div>", unsafe_allow_html=True)
