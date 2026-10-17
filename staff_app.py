"""تطبيق الموظفين: لوحة التذاكر والمراجعة."""
import hmac
import logging
import streamlit as st
import config
import database
import ui_common as ui

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="IT Support - Staff", page_icon="📋", layout="wide")
try:
    database.initialize_database()
except Exception:
    logger.exception("Database initialization failed")
    st.error("The database could not be opened. Please contact the administrator.")
    st.stop()
ui.inject_css()

MAX_ATTEMPTS = 5

def login_screen():
    ui.page_header("🔒 Staff login", "The ticket dashboard is only for the IT support team.")
    if not config.STAFF_PASSWORD:
        st.error("STAFF_PASSWORD is not set. Add it to the .env file and restart this app.")
        st.stop()
    attempts = st.session_state.get("login_attempts", 0)
    if attempts >= MAX_ATTEMPTS:
        st.error("Too many wrong attempts. Please restart the page later.")
        st.stop()
    with st.form("staff_login"):
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")
    if submitted:
        if hmac.compare_digest(password.encode(), config.STAFF_PASSWORD.encode()):
            st.session_state["staff_ok"] = True
            st.session_state["login_attempts"] = 0
            st.rerun()
        st.session_state["login_attempts"] = attempts + 1
        st.error("Wrong password.")
    st.stop()

if not st.session_state.get("staff_ok"):
    login_screen()
if st.sidebar.button("🚪 Log out"):
    st.session_state["staff_ok"] = False
    st.rerun()

# """واجهة الموظف: لوحة التذاكر والمراجعة (Ticket Dashboard)"""
import pandas as pd
import agent
import notifications


def show_ticket_detail(ticket_id):
    ok, ticket = ui.safe_call(database.get_ticket_by_id, ticket_id)
    if not ok or not ticket:
        return

    st.divider()
    st.subheader(f"Ticket {ticket_id}")
    left, right = st.columns(2)
    left.markdown(
        f"**Customer:** {ticket['customer_id']}  \n**Contact:** {ticket['contact_detail'] or '-'}  \n"
        f"**Department:** {ticket['department'] or '-'}  \n**Device/system:** {ticket['device_or_system'] or '-'}  \n"
        f"**Created:** {ticket['created_at']}  \n**Updated:** {ticket['updated_at']}"
    )
    right.markdown(
        f"**Category:** {ticket['category']}  \n"
        f"**Priority:** {ui.PRIORITY_ICONS.get(ticket['priority'], '')} {ticket['priority']}  \n"
        f"**Status:** {ui.status_badge(ticket['status'])}  \n**Agent action:** `{ticket['agent_action']}`",
        unsafe_allow_html=True,
    )

    #   محادثة المستخدم كاملة (نفس اللي بيشوفها بالشات)
    st.markdown("**Conversation with the user**")
    with st.container(height=320, border=True):
        ui.render_chat(ui.get_conversation(ticket), staff_label="Support team (you)")

    st.markdown("**Agent decision and reasons**")
    st.markdown(
        f"- Action: {ticket['action_reason']}\n"
        f"- Classification: {ticket['classification_reason']}\n"
        f"- Priority: {ticket['priority_reason']}"
    )
    if ticket["follow_up_question"]:
        st.info(f"Follow-up question: {ticket['follow_up_question']}")
    if ticket["escalation_reason"]:
        st.error(f"Escalation reason: {ticket['escalation_reason']}")
        st.markdown(f"**Recommended reviewer action:** {ticket['recommended_reviewer_action']}")

    # المسودة المجهزة مقارنة بالرد المعتمد
    col_draft, col_approved = st.columns(2)
    with col_draft:
        if ticket["draft_response"]:
            ui.show_draft(ticket["draft_response"], "AI draft (not approved)")
        else:
            st.markdown("**AI draft**")
            st.caption("This ticket has no draft.")

    with col_approved:
        st.markdown("**Approved response (sent to the user)**")
        if ticket["approved_response"]:
            st.success(f"Sent to the user in the chat. Reviewed on {ticket['reviewed_at'] or ticket['updated_at']}")
            st.info(ticket["approved_response"])
        elif ticket["reviewer_decision"] == "REJECTED":
            st.error("The reviewer rejected the draft. No response is approved.")
        else:
            st.caption("Nothing approved yet. Write a note or approve the draft to reply to the user.")

    if ticket["reviewer_note"]:
        st.caption(f"Reviewer note: {ticket['reviewer_note']}")

    # إجراءات المراجع المتاحة
    st.markdown("**Reviewer actions**")
    note = st.text_area(
        "Reviewer note (internal for Reject/Escalate/Close; user reply for Approve)",
        key=f"note_{ticket_id}",
    )
    closed = ticket["status"] == "CLOSED"
    has_draft = bool(ticket["draft_response"])
    b1, b2, b3, b4 = st.columns(4)

    #   كل زر بيستدعي agent.staff_action: بينفذ القرار وبيرسل الملاحظة للمستخدم
    buttons = [
        (b1, "✅ Approve Draft", "APPROVE", "approved.", closed or not (has_draft or note.strip())),
        (b2, "❌ Reject Draft", "REJECT", "draft rejected.", closed or not has_draft),
        (b3, "⚠️ Escalate", "ESCALATE", "escalated.", closed or ticket["status"] == "ESCALATED"),
        (b4, "🔒 Close Ticket", "CLOSE", "closed.", closed),
    ]
    for col, label, action, done, disabled in buttons:
        if col.button(label, key=f"{action}_{ticket_id}", disabled=disabled):
            ok, outcome = ui.safe_call(agent.staff_action, ticket_id, action, note)
            if ok:
                sent = " Reply sent to the user." if note.strip() and action == "APPROVE" else ""
                #   حالة إرسال الإيميل للمستخدم
                if outcome.get("emailed"):
                    sent += " Email sent."
                elif notifications.is_valid_email(ticket["contact_detail"]) and (note.strip() or action == "APPROVE"):
                    sent += " (Email was NOT sent: check the EMAIL_* settings in .env.)"
                st.session_state["flash"] = f"{ticket_id}: {done}{sent}"
                st.rerun()

    ok, history = ui.safe_call(database.get_ticket_history, ticket_id)
    if ok and history:
        st.markdown("**Status history**")
        st.dataframe(pd.DataFrame(history), hide_index=True)


ui.page_header("📋 Ticket Dashboard", "Review tickets, read the conversation and reply to users with a note.")

flash = st.session_state.pop("flash", None)
if flash:
    st.success(flash)

ok, all_tickets = ui.safe_call(database.list_tickets)
if ok and all_tickets:
    #   ملخص سريع
    count = lambda s: sum(1 for t in all_tickets if t["status"] == s)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("All tickets", len(all_tickets))
    m2.metric("Pending review", count("PENDING_HUMAN_REVIEW"))
    m3.metric("Waiting for info", count("WAITING_FOR_INFO"))
    m4.metric("Escalated", count("ESCALATED"))

f1, f2, f3 = st.columns(3)
status = f1.selectbox("Status", ["All"] + config.STATUSES)
category = f2.selectbox("Category", ["All"] + config.CATEGORIES)
priority = f3.selectbox("Priority", ["All"] + config.PRIORITIES)

ok, tickets = ui.safe_call(
    database.list_tickets,
    None if status == "All" else status,
    None if category == "All" else category,
    None if priority == "All" else priority,
)
if not ok:
    st.stop()
if not tickets:
    st.info("No tickets found yet.")
    st.stop()

st.caption(f"{len(tickets)} ticket(s)")
table = pd.DataFrame(tickets)[["ticket_id", "category", "priority", "status", "customer_id", "created_at"]]
st.dataframe(table, hide_index=True)

selected = st.selectbox("Select a ticket to review", [t["ticket_id"] for t in tickets])
show_ticket_detail(selected)
