# نقطة دخول واحدة للنشر على Streamlit Cloud: التطبيقان يعملان بنفس الحاوية ونفس قاعدة البيانات
import streamlit as st

pg = st.navigation([
    st.Page("app.py", title="Employee - Submit a ticket", icon="💬", default=True),
    st.Page("staff_app.py", title="Support Staff", icon="📋"),
])
pg.run()
