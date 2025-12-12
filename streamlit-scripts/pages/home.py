"""
Home Dashboard - Overview of all tools
"""
import streamlit as st

# Custom CSS for dashboard cards
st.markdown("""
<style>
    .dashboard-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 8px 24px rgba(102, 126, 234, 0.3);
        transition: all 0.3s ease;
        border: none;
    }

    .dashboard-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 32px rgba(102, 126, 234, 0.4);
    }

    .card-icon {
        font-size: 3rem;
        margin-bottom: 1rem;
        display: block;
    }

    .card-title {
        font-size: 1.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        color: white;
    }

    .card-description {
        font-size: 1rem;
        opacity: 0.95;
        color: white;
    }

    .welcome-banner {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 3rem 2rem;
        border-radius: 20px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 10px 40px rgba(245, 87, 108, 0.3);
    }

    .welcome-title {
        font-size: 3rem;
        font-weight: 900;
        color: white;
        margin: 0;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }

    .welcome-subtitle {
        font-size: 1.2rem;
        color: white;
        opacity: 0.95;
        margin-top: 0.5rem;
    }

    .stats-box {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        border-left: 4px solid #667eea;
    }

    .stat-value {
        font-size: 2.5rem;
        font-weight: 800;
        color: #667eea;
        margin: 0;
    }

    .stat-label {
        font-size: 0.9rem;
        color: #718096;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-top: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Welcome Banner
st.markdown("""
<div class="welcome-banner">
    <h1 class="welcome-title">⚡ Lambda Admin Dashboard</h1>
    <p class="welcome-subtitle">Manage your dating platform with powerful admin tools</p>
</div>
""", unsafe_allow_html=True)

# Quick Stats
st.subheader("📊 Quick Overview")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
    <div class="stats-box">
        <p class="stat-value">🚀</p>
        <p class="stat-label">Active Tools</p>
        <p class="stat-value">8</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="stats-box" style="border-left-color: #f5576c;">
        <p class="stat-value">👥</p>
        <p class="stat-label">User Mgmt</p>
        <p class="stat-value">6</p>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="stats-box" style="border-left-color: #4CAF50;">
        <p class="stat-value">📈</p>
        <p class="stat-label">Analytics</p>
        <p class="stat-value">1</p>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
    <div class="stats-box" style="border-left-color: #ff9800;">
        <p class="stat-value">🏠</p>
        <p class="stat-label">Dashboard</p>
        <p class="stat-value">1</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Available Tools Section
st.subheader("🛠️ Available Tools")

# User Management Tools
st.markdown("### 👥 User Management")
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class="dashboard-card">
        <span class="card-icon">📋</span>
        <h3 class="card-title">Waitlist Review</h3>
        <p class="card-description">Review and approve/reject waitlist applications. Filter by gender, tier, and status.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="dashboard-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
        <span class="card-icon">🗑️</span>
        <h3 class="card-title">Remove Users</h3>
        <p class="card-description">Manage and remove unnecessary users from the platform.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="dashboard-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
        <span class="card-icon">💑</span>
        <h3 class="card-title">Match Status</h3>
        <p class="card-description">Monitor and manage user matches and relationship status.</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="dashboard-card" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);">
        <span class="card-icon">✅</span>
        <h3 class="card-title">Human Approval</h3>
        <p class="card-description">Approve profile matches before Temporal processing.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="dashboard-card" style="background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);">
        <span class="card-icon">🖼️</span>
        <h3 class="card-title">Image Manager</h3>
        <p class="card-description">Review and manage user profile images.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="dashboard-card" style="background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);">
        <span class="card-icon">💪</span>
        <h3 class="card-title">Physical Compatibility</h3>
        <p class="card-description">Manage physical compatibility settings and preferences.</p>
    </div>
    """, unsafe_allow_html=True)

# Analytics Tools
st.markdown("### 📊 Analytics")
st.markdown("""
<div class="dashboard-card" style="background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%); color: #2d3748;">
    <span class="card-icon">💬</span>
    <h3 class="card-title" style="color: #2d3748;">Chat Viewer</h3>
    <p class="card-description" style="color: #2d3748;">Search users and view their chat messages. Monitor conversations.</p>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Quick Actions
st.markdown("---")
st.subheader("⚡ Quick Start")
st.info("👈 Select a tool from the sidebar navigation to get started!")

# Footer
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align: center; color: #718096; font-size: 0.9rem;">
    <p>Lambda Admin Dashboard • Built with ❤️ using Streamlit</p>
</div>
""", unsafe_allow_html=True)
