"""
SEO Blog Writer Agent — Streamlit Application
==============================================
Multi-page app entry point.

Run with:
    streamlit run app/main.py
"""
from __future__ import annotations

import streamlit as st

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="SEO Blog Writer Agent",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Navigation")
    st.page_link("main.py", label="🏠 Home", icon="🏠")
    st.page_link("pages/generate.py", label="✍️ Generate Blog", icon="✍️")
    st.page_link("pages/results.py", label="📊 Results & Export", icon="📊")

# ── Home page ─────────────────────────────────────────────────────────────────
st.title("✍️ SEO Blog Writer Agent")
st.caption("Powered by LangGraph + CrewAI · Gemini · Mistral · Groq")

st.markdown("""
Welcome to the **SEO Blog Writer Agent** — a fully autonomous, AI-powered pipeline
that researches, outlines, writes, optimises, and edits SEO-optimised blog posts.

---

### 🔄 How it works

| Phase | Agent | Description |
|-------|-------|-------------|
| 1️⃣ Research | Senior SEO Research Analyst | Keyword research, SERP analysis, competitor gaps |
| 2️⃣ Strategy | Content Strategist & SEO Architect | Outline generation with search-intent mapping |
| 3️⃣ Writing | Expert SEO Content Writer | Section-by-section writing with readability loops |
| 4️⃣ SEO Optimisation | Technical SEO Specialist | Meta tags, schema markup, keyword density |
| 5️⃣ Editing | Senior Content Editor & Fact Checker | Fact-checking, QA, final polish |

---

### 🚀 Get started

1. Go to **✍️ Generate Blog** to enter your topic and settings
2. Watch the agents work in real-time, then download the final post from **📊 Results & Export**

---
""")

col1, col2 = st.columns(2)
with col1:
    if st.button("✍️ Start Generating →", type="primary", use_container_width=True):
        st.switch_page("pages/generate.py")
with col2:
    if st.session_state.get("last_blog_post"):
        if st.button("📊 View Last Results →", use_container_width=True):
            st.switch_page("pages/results.py")
