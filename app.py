"""تطبيق الموظفين: إنشاء ومتابعة التذاكر."""
import logging
import streamlit as st
import database
import ui_common as ui

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="IT Support", page_icon="💬", layout="wide")
try:
    database.initialize_database()
except Exception:
    logger.exception("Database initialization failed")
    st.error("The database could not be opened. Please contact the administrator.")
    st.stop()
ui.inject_css()

import agent
import notifications

DETAIL_KEYS = ("customer_id", "contact_detail", "department", "device_or_system")

st.markdown("""<style>
.block-container {max-width: 820px;}
.stApp {background-image: radial-gradient(900px 420px at 90% -5%, rgba(168,85,247,.16), transparent),
                          radial-gradient(800px 420px at 0% 0%, rgba(79,70,229,.14), transparent);}
</style>""", unsafe_allow_html=True)


def new_chat():
    """بدء تذكرة جديدة (تفريغ الشات الحالي)"""
    for key in ("chat_ticket_id", "last_steps", "last_warning", "llm_notice"):
        st.session_state.pop(key, None)


def open_existing():
    """  فتح تذكرة قديمة: رقم التذكرة + Customer ID (لازم يتطابقوا) عشان يشوف ردود الموظف"""
    ticket_id = st.session_state.get("existing_id", "").strip().upper()
    customer = st.session_state.get("customer_id", "").strip().lower()
    try:
        found = database.get_ticket_by_id(ticket_id) if ticket_id else None
    except Exception:
        found = None
    if found and customer and found["customer_id"].strip().lower() == customer:
        st.session_state["chat_ticket_id"] = found["ticket_id"]
        st.session_state["last_steps"] = []
        st.session_state["llm_notice"] = ""
    else:
        # نفس الرسالة بالحالتين عشان ما حدا يخمّن أرقام تذاكر غيره
        st.session_state["open_error"] = "Ticket not found, or the Customer ID above does not match it."


def details_form():
    """حقول بيانات المستخدم (بنتذكر آخر قيم عشان التذكرة الجديدة)"""
    for key in DETAIL_KEYS:
        st.session_state.setdefault(key, st.session_state.get("saved_details", {}).get(key, ""))
    a, b = st.columns(2)
    a.text_input("Customer ID *", key="customer_id", placeholder="employee_1042")
    b.text_input("Email (optional, to get the support reply by email)", key="contact_detail",
                 placeholder="name@gmail.com")
    c, d = st.columns(2)
    c.text_input("Department (optional)", key="department", placeholder="Finance")
    d.text_input("Device / system (optional)", key="device_or_system", placeholder="Company laptop / Outlook / VPN")
    st.caption("Please never type passwords, verification codes, secret keys or card numbers.")


def show_details(ticket):
    """تفاصيل التذكرة وكيف قرر النظام (للشفافية)"""
    with st.expander("Ticket details and how the agent decided"):
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"**Action**\n\n`{ticket['agent_action']}`")
        c2.markdown(f"**Category**\n\n{ticket['category']}")
        c3.markdown(f"**Priority**\n\n{ui.PRIORITY_ICONS.get(ticket['priority'], '')} {ticket['priority']}")
        c4.markdown(f"**Status**\n\n`{ticket['status']}`")
        st.markdown(f"**Why this action:** {ticket['action_reason']}")
        st.markdown(f"**Classification reason:** {ticket['classification_reason']}")
        st.markdown(f"**Priority reason:** {ticket['priority_reason']}")
        if ticket["missing_information"]:
            st.markdown(f"**Missing information:** {ticket['missing_information']}")
        if ticket["escalation_reason"]:
            st.error(f"⚠️ Escalated: {ticket['escalation_reason']}")
        for step in st.session_state.get("last_steps", []):
            st.write(f"• {step}")


@st.fragment(run_every=4)
def live_conversation(ticket_id):
    """  المحادثة بتتحدث لحالها كل 4 ثواني، فرد الموظف بيظهر للمستخدم مباشرة"""
    current = database.get_ticket_by_id(ticket_id)
    if current:
        ui.render_chat(ui.get_conversation(current))


ticket_id = st.session_state.get("chat_ticket_id")
ticket = None
if ticket_id:
    ok, ticket = ui.safe_call(database.get_ticket_by_id, ticket_id)

# waiting = النظام سأل سؤال وينتظر الجواب | غير هيك التذكرة انتهت والواجهة جاهزة لتذكرة جديدة
waiting = bool(ticket and ticket["status"] == "WAITING_FOR_INFO")

# ---------- شريط علوي بسيط: بيانات المستخدم + حالة التذكرة ----------
top_left, top_right = st.columns([5, 1])
with top_left.expander("👤 Your details", expanded=not st.session_state.get("customer_id")):
    details_form()
if ticket:
    top_right.button("➕ New chat", on_click=new_chat, use_container_width=True)
    st.markdown(
        f"<div class='ticket-bar'><b>🎫 {ticket['ticket_id']}</b> {ui.status_badge(ticket['status'])} "
        f"{ui.PRIORITY_ICONS.get(ticket['priority'], '')} {ticket['priority']} · {ticket['category']}</div>",
        unsafe_allow_html=True,
    )

#   فتح تذكرة موجودة (بدون تعقيد): رقم التذكرة + الـ Customer ID اللي فوق
if not waiting:
    with st.expander("🔎 Open an existing ticket (to read the support reply)"):
        st.text_input("Ticket ID", key="existing_id", placeholder="TKT-20261010-0001")
        st.button("Open ticket", on_click=open_existing)
        if st.session_state.get("open_error"):
            st.error(st.session_state.pop("open_error"))

# ---------- إدخال الشات ----------
if waiting:
    placeholder = "Type your answer..."
elif ticket:
    placeholder = "Describe a new problem to open another ticket..."
else:
    placeholder = "Describe your IT problem..."

prompt = st.chat_input(placeholder)

# ---------- عرض المحادثة ----------
if ticket and (waiting or not prompt):
    if st.session_state.get("last_warning"):
        st.warning(st.session_state["last_warning"])
    if st.session_state.get("llm_notice"):
        st.warning(f"⚠️ The AI model could not be used , Check the internet conection")
    live_conversation(ticket["ticket_id"])
elif not ticket and not prompt:
    st.markdown(
        "<div class='hero'><div class='hero-icon'>💬</div>"
        "<div class='hero-title'>TicketFlow AI </div>"
        "<div class='hero-title'>Safe, policy-driven IT support</div>"
        "<div class='hero-sub'>Turn IT problems into safe, reviewable tickets</div>"
        "<div class='hero-sub'>Describe your IT problem and I will open a ticket for you</div>"
        "<div class='chips'><span class='chip'>⚡ Instant triage</span><span class='chip'>🧠 Smart follow-up questions</span>"
        "<span class='chip'>🛡️ Human review when needed</span></div></div>",
        unsafe_allow_html=True)

# ---------- معالجة الرسالة (تظهر رسالة المستخدم فوراً + مؤشر تفكير) ----------
if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant", avatar="🤖"):
        typing = st.empty()
        with typing.container():
            ui.typing_indicator()      #   نقاط متحركة أثناء المعالجة
        if waiting:
            # جواب سؤال النظام (بينضم للتذكرة نفسها)
            result = agent.handle_user_message(ticket["ticket_id"], prompt)
        else:
            # رسالة جديدة = تذكرة جديدة
            metadata = {key: st.session_state.get(key, "") for key in DETAIL_KEYS[1:]}
            email = metadata["contact_detail"].strip()
            if email and not notifications.is_valid_email(email):      #   إيميل غير صحيح
                result = {"ok": False, "error": "Please enter a valid email address, or leave the email field empty."}
            else:
                result = agent.submit_ticket(st.session_state.get("customer_id", ""), prompt, metadata)
            if result["ok"]:
                st.session_state["saved_details"] = {key: st.session_state.get(key, "") for key in DETAIL_KEYS}
        typing.empty()

    if result["ok"]:
        st.session_state["chat_ticket_id"] = result["ticket"]["ticket_id"]
        st.session_state["last_steps"] = result["steps"]
        st.session_state["last_warning"] = result["warning"]
        #   إذا النموذج ما اشتغل بنوضح السبب بالشات بدل ما يبين كأنه يشتغل
        marker = "AI model not used:"
        notice = next((step for step in result["steps"] if marker in step), "")
        st.session_state["llm_notice"] = notice.split(marker)[1].strip(" .") if notice else ""
        st.rerun()
    else:
        st.error(result["error"])

if ticket and not prompt:
    show_details(ticket)
