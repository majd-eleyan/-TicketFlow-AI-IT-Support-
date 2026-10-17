"""
  تخزين محادثة التذكرة (History) - نفس فكرة MemoryStore بالكورس
بس محفوظة بقاعدة البيانات بدل list بالذاكرة، فالمحادثة تضل موجودة بعد إعادة التشغيل.
الأدوار: user (المستخدم) / ai (النظام) / staff (موظف الدعم)
"""
import database


class MemoryStore:
    def __init__(self, ticket_id):
        self.ticket_id = ticket_id

    def add_user_message(self, message):
        database.add_message(self.ticket_id, "user", message)

    def add_ai_message(self, message):
        database.add_message(self.ticket_id, "ai", message)

    def add_staff_message(self, message):
        database.add_message(self.ticket_id, "staff", message)

    def get_history(self):
        return database.get_messages(self.ticket_id)
