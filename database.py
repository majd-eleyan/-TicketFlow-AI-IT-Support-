import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
import config

STATE_TRANSITIONS = {
    "RECEIVED": {"RECEIVED", "VALIDATED", "WAITING_FOR_INFO", "CLASSIFIED", "PENDING_HUMAN_REVIEW", "ESCALATED", "REJECTED"},
    "VALIDATED": {"VALIDATED", "WAITING_FOR_INFO", "CLASSIFIED", "PENDING_HUMAN_REVIEW", "ESCALATED", "REJECTED"},
    "WAITING_FOR_INFO": {"WAITING_FOR_INFO", "CLASSIFIED", "PENDING_HUMAN_REVIEW", "ESCALATED", "REJECTED"},
    "CLASSIFIED": {"CLASSIFIED", "PENDING_HUMAN_REVIEW", "APPROVED", "REJECTED", "ESCALATED", "CLOSED"},
    "DRAFT_READY": {"DRAFT_READY", "PENDING_HUMAN_REVIEW", "APPROVED", "REJECTED", "ESCALATED", "CLOSED"},
    "PENDING_HUMAN_REVIEW": {"PENDING_HUMAN_REVIEW", "APPROVED", "REJECTED", "ESCALATED", "CLOSED"},
    "ESCALATED": {"ESCALATED", "CLOSED"},
    "APPROVED": {"APPROVED", "CLOSED"},
    "REJECTED": {"REJECTED", "CLOSED"},
    "CLOSED": {"CLOSED"},
}


def _validate_transition(old_status, new_status):
    if old_status is None:
        return
    allowed = STATE_TRANSITIONS.get(old_status, set())
    if new_status not in allowed:
        raise ValueError(f"Invalid ticket state transition: {old_status} -> {new_status}")


ALLOWED_UPDATE_COLUMNS = {
    "message", "category", "classification_reason", "priority", "priority_reason",
    "status", "agent_action", "action_reason", "missing_information",
    "follow_up_question", "draft_response", "review_needed", "escalation_reason",
    "recommended_reviewer_action", "approved_response", "reviewer_decision",
    "reviewer_note", "reviewed_at",
}

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@contextmanager
def connect(db_path=None):
    # فتح الاتصال وإغلاقه بأمان
    path = db_path or config.DB_PATH
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def initialize_database(db_path=None):
    # إنشاء جدول التذاكر وجدول سجل الحالات
    with connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                contact_detail TEXT,
                department TEXT,
                device_or_system TEXT,
                message TEXT NOT NULL,
                category TEXT,
                classification_reason TEXT,
                priority TEXT,
                priority_reason TEXT,
                status TEXT NOT NULL,
                agent_action TEXT,
                action_reason TEXT,
                missing_information TEXT,
                follow_up_question TEXT,
                draft_response TEXT,
                review_needed INTEGER,
                escalation_reason TEXT,
                recommended_reviewer_action TEXT,
                reviewer_decision TEXT,
                reviewer_note TEXT,
                reviewed_at TEXT,
                approved_response TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ticket_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                changed_at TEXT NOT NULL,
                old_status TEXT,
                new_status TEXT,
                note TEXT
            )
        """)
    initialize_messages_table(db_path)  #   جدول المحادثة

def _record_history(conn, ticket_id, old_status, new_status, note):
    # تسجيل حدث بسجل حالات التذكرة
    conn.execute(
        "INSERT INTO ticket_history (ticket_id, changed_at, old_status, new_status, note) VALUES (?, ?, ?, ?, ?)",
        (ticket_id, now(), old_status, new_status, note)
    )

def create_ticket(ticket, db_path=None):
    # إنشاء وحفظ تذكرة جديدة وإرجاع رقمها الفريد
    today = datetime.now().strftime("%Y%m%d")
    prefix = f"TKT-{today}-"
    timestamp = now()

    with connect(db_path) as conn:
        # جلب أحدث رقم تذكرة لإنشاء الرقم التالي
        last = conn.execute(
            "SELECT MAX(ticket_id) FROM tickets WHERE ticket_id LIKE ?", (prefix + "%",)
        ).fetchone()[0]
        number = int(last[-4:]) + 1 if last else 1
        ticket_id = f"{prefix}{number:04d}"

        # إدخال البيانات  
        conn.execute(
            """INSERT INTO tickets
               (ticket_id, created_at, updated_at, customer_id, contact_detail, department, device_or_system,
                message, category, classification_reason, priority, priority_reason, status, agent_action,
                action_reason, missing_information, follow_up_question, draft_response, review_needed,
                escalation_reason, recommended_reviewer_action)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ticket_id,
                timestamp,
                timestamp,
                ticket.get("customer_id", ""),
                ticket.get("contact_detail") or None,
                ticket.get("department") or None,
                ticket.get("device_or_system") or None,
                ticket.get("clean_message") or ticket.get("message", ""),
                ticket.get("category", "Other"),
                ticket.get("classification_reason", ""),
                ticket.get("priority", "LOW"),
                ticket.get("priority_reason", ""),
                ticket.get("status", "RECEIVED"),
                ticket.get("agent_action") or ticket.get("action", ""),
                ticket.get("action_reason", ""),
                ticket.get("missing_information", ""),
                ticket.get("follow_up_question", ""),
                ticket.get("draft_response") or ticket.get("message_to_user", ""),
                int(bool(ticket.get("review_needed", False))),
                ticket.get("escalation_reason", ""),
                ticket.get("recommended_reviewer_action", ""),
            )
        )
        _record_history(conn, ticket_id, None, ticket.get("status", "RECEIVED"), "Ticket created.")
        return ticket_id

def get_ticket_by_id(ticket_id, db_path=None):
    # جلب تذكرة برقمها
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
    return dict(row) if row else None

def list_tickets(status=None, category=None, priority=None, db_path=None):
    # عرض التذاكر مع إمكانية الفلترة حسب الحالة/التصنيف/الأولوية
    query = "SELECT * FROM tickets WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if category:
        query += " AND category = ?"
        params.append(category)
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    query += " ORDER BY created_at DESC"

    with connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]

def update_ticket_fields(ticket_id, fields, note="", db_path=None):
    # تحديث مجموعة من الحقول دفعة وحدة (يُستخدم عند إضافة توضيح من المستخدم)
    if not fields:
        return
    with connect(db_path) as conn:
        current = conn.execute("SELECT status FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
        old_status = current["status"] if current else None

        columns = list(fields.keys())
        invalid = set(columns) - ALLOWED_UPDATE_COLUMNS
        if invalid:
            raise ValueError(f"Invalid ticket update fields: {sorted(invalid)}")
        new_status = fields.get("status", old_status)
        _validate_transition(old_status, new_status)
        values = list(fields.values())
        set_clause = ", ".join(f"{col} = ?" for col in columns)
        conn.execute(
            f"UPDATE tickets SET {set_clause}, updated_at = ? WHERE ticket_id = ?",
            (*values, now(), ticket_id)
        )
        _record_history(conn, ticket_id, old_status, fields.get("status", old_status), note)

def update_ticket_status(ticket_id, new_status, note="", db_path=None):
    # تغيير حالة التذكرة فقط (تصعيد يدوي أو إغلاق)
    with connect(db_path) as conn:
        current = conn.execute("SELECT status FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
        old_status = current["status"] if current else None
        _validate_transition(old_status, new_status)
        conn.execute(
            "UPDATE tickets SET status = ?, updated_at = ? WHERE ticket_id = ?",
            (new_status, now(), ticket_id)
        )
        _record_history(conn, ticket_id, old_status, new_status, note)

def save_reviewer_decision(ticket_id, decision, note="", db_path=None, approved_text=None):
    # حفظ قرار المراجع البشري (اعتماد أو رفض المسودة)
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, draft_response FROM tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        old_status = row["status"] if row else None
        new_status = "APPROVED" if decision == "APPROVED" else "REJECTED"
        _validate_transition(old_status, new_status)
        #  لو الموظف كتب ملاحظة بتصير هي الرد المعتمد، وإلا بنعتمد المسودة
        approved_response = (approved_text or row["draft_response"]) if (row and decision == "APPROVED") else None

        conn.execute(
            """UPDATE tickets
               SET status = ?, reviewer_decision = ?, reviewer_note = ?, reviewed_at = ?,
                   approved_response = ?, updated_at = ?
               WHERE ticket_id = ?""",
            (new_status, decision, note, now(), approved_response, now(), ticket_id)
        )
        _record_history(conn, ticket_id, old_status, new_status, note or f"Reviewer {decision.lower()} the draft.")

def get_ticket_history(ticket_id, db_path=None):
    # جلب سجل تغييرات حالة التذكرة
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM ticket_history WHERE ticket_id = ? ORDER BY changed_at ASC, id ASC",
            (ticket_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ======================================================================
#  سجل المحادثة لكل تذكرة (History) - يُستخدم لإدارة الـ context
# ======================================================================
def initialize_messages_table(db_path=None):
    # جدول رسائل المحادثة: user (المستخدم) / ai (النظام) / staff (الموظف)
    with connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ticket_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL
            )
        """)

def add_message(ticket_id, role, content, db_path=None):
    # حفظ رسالة جديدة بمحادثة التذكرة
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO ticket_messages (ticket_id, created_at, role, content) VALUES (?, ?, ?, ?)",
            (ticket_id, now(), role, content)
        )

def get_messages(ticket_id, db_path=None):
    # جلب كل رسائل التذكرة بالترتيب (الـ Full history)
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY id ASC", (ticket_id,)
        ).fetchall()
    return [dict(r) for r in rows]
