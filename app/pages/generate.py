"""
Generate Blog Page
==================
User input form → triggers the SEOBlogCrew pipeline with live progress.
"""
from __future__ import annotations

import time

import streamlit as st

st.set_page_config(
    page_title="Generate Blog | SEO Blog Agent",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar navigation ────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Configuration")
    st.page_link("main.py", label="🏠 Home", icon="🏠")
    st.page_link("pages/generate.py", label="✍️ Generate Blog", icon="✍️")
    st.page_link("pages/results.py", label="📊 Results & Export", icon="📊")

# ── Page header ───────────────────────────────────────────────────────────────
st.title("✍️ Generate a Blog Post")
st.caption("Fill in the details below and click **Generate** to start the autonomous pipeline.")

# ── Input form ────────────────────────────────────────────────────────────────
with st.form("blog_form", clear_on_submit=False):
    st.subheader("📝 Blog Topic")
    col1, col2 = st.columns([2, 1])
    with col1:
        topic = st.text_input(
            "Blog Topic *",
            placeholder="e.g. Best Python Web Frameworks in 2025",
            help="Describe what the blog post should be about.",
        )
        target_keywords = st.text_area(
            "Target Keywords (comma-separated)",
            placeholder="e.g. python web frameworks, django vs flask, fastapi tutorial",
            help="Optional. The research agent will also discover keywords automatically.",
            height=80,
        )
    with col2:
        blog_type = st.selectbox(
            "Blog Type",
            options=[
                "How-To Guide",
                "Listicle",
                "Product Comparison",
                "In-Depth Review",
                "Opinion / Thought Leadership",
                "News & Trends",
                "Tutorial",
                "Case Study",
            ],
            index=0,
        )
        tone = st.selectbox(
            "Tone of Voice",
            options=[
                "Professional",
                "Conversational",
                "Authoritative",
                "Friendly",
                "Technical",
                "Beginner-Friendly",
            ],
            index=1,
        )

    st.subheader("🎯 Audience & Length")
    col3, col4, col5 = st.columns(3)
    with col3:
        target_audience = st.text_input(
            "Target Audience",
            value="developers and tech enthusiasts",
            placeholder="e.g. small business owners",
        )
    with col4:
        word_count = st.slider(
            "Target Word Count",
            min_value=500,
            max_value=5000,
            value=1500,
            step=250,
        )
    with col5:
        language = st.selectbox(
            "Language",
            options=["English", "Spanish", "French", "German", "Portuguese", "Italian"],
            index=0,
        )

    st.subheader("🔧 Advanced Settings")
    col6, col7 = st.columns(2)
    with col6:
        brand_voice = st.text_area(
            "Brand Voice Notes (optional)",
            placeholder="e.g. We avoid jargon. We use 'you' instead of 'the user'. We always cite sources.",
            height=80,
        )
    with col7:
        site_url = st.text_input(
            "Site URL (for schema markup, optional)",
            placeholder="https://yourblog.com",
        )
        author_name = st.text_input(
            "Author Name",
            value="SEO Blog Agent",
        )

    submitted = st.form_submit_button(
        "🚀 Generate Blog Post",
        type="primary",
        use_container_width=True,
    )

# ── Validation & execution ────────────────────────────────────────────────────
if submitted:
    if not topic.strip():
        st.error("Please enter a blog topic before generating.")
        st.stop()

    # Parse keywords
    kw_list = [k.strip() for k in target_keywords.split(",") if k.strip()] if target_keywords else []

    # Build BlogRequest
    from models.schemas import BlogRequest  # lazy import after env vars are set
    request = BlogRequest(
        topic=topic.strip(),
        target_keywords=kw_list,
        blog_type=blog_type,
        tone=tone,
        target_audience=target_audience.strip(),
        word_count=word_count,
        language=language,
        brand_voice_notes=brand_voice.strip(),
        site_url=site_url.strip(),
        author_name=author_name.strip(),
    )

    st.session_state["current_request"] = request.model_dump()

    # ── Live pipeline execution ───────────────────────────────────────────────
    st.divider()
    st.subheader("🤖 Agent Pipeline Running…")

    progress_bar = st.progress(0, text="Initialising agents…")
    status_container = st.status("Pipeline starting…", expanded=True)

    phases = [
        (0.10, "🔍 Phase 1: SEO Research — keyword analysis & SERP mining"),
        (0.30, "📐 Phase 2: Content Strategy — outline generation"),
        (0.60, "✍️  Phase 3: Writing — section-by-section content creation"),
        (0.80, "📈 Phase 4: SEO Optimisation — meta tags, schema, keyword density"),
        (0.95, "🔍 Phase 5: Quality Assurance — fact-checking & final polish"),
    ]

    from agents.crew import SEOBlogCrew

    crew = SEOBlogCrew()
    blog_post = None
    error_msg = None

    with status_container:
        for progress, label in phases:
            st.write(label)

        try:
            progress_bar.progress(0.05, text="Starting research…")
            start_time = time.time()
            blog_post = crew.run(request)
            elapsed = time.time() - start_time
            progress_bar.progress(1.0, text=f"Done! ({elapsed:.0f}s)")
            st.write(f"✅ Pipeline complete in {elapsed:.0f} seconds")
        except Exception as exc:
            error_msg = str(exc)
            progress_bar.progress(1.0, text="Pipeline encountered an error")
            st.write(f"❌ Error: {error_msg}")

    if blog_post:
        status_container.update(label="✅ Blog post generated successfully!", state="complete")
        st.session_state["last_blog_post"] = blog_post.model_dump()
        st.success("🎉 Blog post ready! Click below to view and download.")
        if st.button("📊 View Results & Export →", type="primary", use_container_width=True):
            st.switch_page("pages/results.py")
    else:
        status_container.update(label="❌ Generation failed", state="error")
        with st.expander("Error details"):
            st.code(error_msg or "Unknown error")
        st.info(
            "💡 Common fixes:\n"
            "- Verify all API keys in your .env file are correct\n"
            "- Ensure your SerpAPI key has remaining credits\n"
            "- Reduce the word count target and try again"
        )
