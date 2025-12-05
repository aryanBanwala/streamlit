"""
Home Dashboard - Overview of all tools
"""
import streamlit as st

st.title("Lambda Admin Dashboard")
st.markdown("---")

st.markdown("""
### Available Tools

| Tool | Description |
|------|-------------|
| **Waitlist Review** | Review and approve/reject waitlist applications |
| **Human Approval** | Approve profile matches before Temporal processing |
| **Chat Viewer** | Search users and view their chat messages |
| **Remove Users** | Manage and remove unnecessary users |

---

*Select a tool from the sidebar to get started.*
""")
