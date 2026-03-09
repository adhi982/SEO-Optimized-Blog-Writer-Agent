"""
Results & Export Page
=====================
Displays the generated blog post with:
  - Rendered Markdown preview
  - Raw Markdown code block
  - SEO Report panel
  - JSON-LD structured data viewer
  - Download button (.md file)
"""
from __future__ import annotations

import json

import streamlit as st

st.set_page_config(
    page_title="Results & Export | SEO Blog Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar navigation ────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Configuration")
    st.page_link("main.py", label="🏠 Home", icon="🏠")
    st.page_link("pages/generate.py", label="✍️ Generate Blog", icon="✍️")
    st.page_link("pages/results.py", label="📊 Results & Export", icon="📊")

# ── Guard: require a blog post in session ─────────────────────────────────────
post_data: dict | None = st.session_state.get("last_blog_post")

if not post_data:
    st.title("📊 Results & Export")
    st.info("No blog post generated yet. Go to **✍️ Generate Blog** to create one.")
    if st.button("✍️ Generate Blog →", type="primary"):
        st.switch_page("app/pages/generate.py")
    st.stop()

# ── Reconstruct BlogPost ──────────────────────────────────────────────────────
from models.schemas import BlogPost  # noqa: E402  (import after guard)

post = BlogPost(**post_data)
seo = post.seo_report  # may be None if pipeline skipped SEO phase

# ── Page header ───────────────────────────────────────────────────────────────
st.title(f"📊 {post.title}")
col_meta1, col_meta2, col_meta3, col_meta4 = st.columns(4)
col_meta1.metric("SEO Score", f"{seo.seo_score}/100" if seo else "N/A")
col_meta2.metric("Readability", f"{seo.readability_score:.0f}" if seo else "N/A", help="Flesch Reading Ease (60-70 ideal)")
col_meta3.metric("Word Count", f"{len(post.full_content.split()):,}")
col_meta4.metric("Sections", str(len(post.sections)))

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_preview, tab_raw, tab_seo, tab_schema = st.tabs(
    ["👁️ Preview", "📝 Markdown", "📈 SEO Report", "🔗 JSON-LD Schema"]
)

# ── Tab 1: Rendered Markdown preview ──────────────────────────────────────────
with tab_preview:
    st.markdown(post.full_content, unsafe_allow_html=False)

# ── Tab 2: Raw Markdown + download ────────────────────────────────────────────
with tab_raw:
    st.code(post.full_content, language="markdown", line_numbers=True)
    _slug = post.title.lower().replace(" ", "-")[:60]
    _filename = f"{_slug}.md"
    st.download_button(
        label="⬇️ Download Markdown File",
        data=post.full_content.encode("utf-8"),
        file_name=_filename,
        mime="text/markdown",
        type="primary",
        use_container_width=True,
    )

# ── Tab 3: SEO Report ─────────────────────────────────────────────────────────
with tab_seo:
    if not seo:
        st.info("SEO report not available for this post.")
    else:
        # Score gauge using progress bar
        score_color = "normal" if seo.seo_score >= 70 else "off"
        st.subheader(f"Overall SEO Score: {seo.seo_score}/100")
        st.progress(seo.seo_score / 100)

        col_l, col_r = st.columns(2)
        with col_l:
            st.subheader("📌 Meta Tags")
            st.markdown(f"**Meta Title** ({len(seo.meta_title)} chars):")
            st.code(seo.meta_title, language="text")
            st.markdown(f"**Meta Description** ({len(seo.meta_description)} chars):")
            st.code(seo.meta_description, language="text")
            if len(seo.meta_title) > 60:
                st.warning("⚠️ Meta title exceeds 60 characters")
            if len(seo.meta_description) > 160:
                st.warning("⚠️ Meta description exceeds 160 characters")

            st.subheader("🔑 Keyword Metrics")
            st.metric("Primary Keyword Density", f"{seo.primary_keyword_density:.2f}%",
                      help="Target: 1-2%")
            density_ok = 0.8 <= seo.primary_keyword_density <= 2.5
            st.caption("✅ In target range" if density_ok else "⚠️ Outside target (1-2%)")

        with col_r:
            st.subheader("📖 Readability")
            st.metric("Flesch Reading Ease", f"{seo.readability_score:.1f}", help="Target: 60-70")
            st.metric("Reading Grade", seo.readability_grade, help="Target: Grade 7-9")
            ease_ok = 55 <= seo.readability_score <= 75
            st.caption("✅ Good readability" if ease_ok else "⚠️ Adjust sentence length")

            if seo.internal_link_suggestions:
                st.subheader("🔗 Internal Link Opportunities")
                for suggestion in seo.internal_link_suggestions:
                    st.markdown(f"• {suggestion}")

        st.subheader("💡 SEO Suggestions")
        for i, suggestion in enumerate(seo.suggestions, 1):
            st.markdown(f"{i}. {suggestion}")

        if seo.alt_text_suggestions:
            with st.expander("🖼️ Alt Text Suggestions"):
                for suggestion in seo.alt_text_suggestions:
                    st.markdown(f"• {suggestion}")

# ── Tab 4: JSON-LD Schema ─────────────────────────────────────────────────────
with tab_schema:
    if not seo or not seo.schema_markup:
        st.info("No schema markup generated for this post.")
    else:
        st.subheader("Structured Data (JSON-LD)")
        st.caption("Copy this into a `<script type='application/ld+json'>` tag in your page `<head>`.")
        schema_str = json.dumps(seo.schema_markup, indent=2, ensure_ascii=False)
        st.code(schema_str, language="json")
        st.download_button(
            label="⬇️ Download schema.json",
            data=schema_str.encode("utf-8"),
            file_name="schema.json",
            mime="application/json",
        )

# ── Bottom actions ────────────────────────────────────────────────────────────
st.divider()
col_a, col_b = st.columns(2)
with col_a:
    if st.button("✍️ Generate Another Post", use_container_width=True):
        st.switch_page("app/pages/generate.py")
with col_b:
    if st.button("🗑️ Clear Results", use_container_width=True):
        st.session_state.pop("last_blog_post", None)
        st.session_state.pop("current_request", None)
        st.rerun()
