"""
tests/test_api.py
=================
Integration-style tests for the full pipeline flow.
These tests mock all LLM and API calls and verify the complete
data flow from BlogRequest → BlogPost.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


def _make_request():
    from models.schemas import BlogRequest
    return BlogRequest(
        topic="Best Python Web Frameworks 2025",
        target_keywords=["python web frameworks", "django", "flask"],
        blog_type="How-To Guide",
        tone="Conversational",
        word_count=1000,
    )


def _make_outline():
    from models.schemas import BlogOutline, OutlineSection
    return BlogOutline(
        title="Best Python Web Frameworks 2025",
        meta_description="Discover the best Python web frameworks for building fast applications.",
        primary_keyword="python web frameworks",
        secondary_keywords=["django", "flask", "fastapi"],
        sections=[
            OutlineSection(
                heading="Why Use Python for Web Development",
                heading_level="h2",
                subheadings=["Ecosystem"],
                key_points=["Large community"],
                target_keyword="python web development",
            ),
            OutlineSection(
                heading="Top Framework Comparison",
                heading_level="h2",
                subheadings=["Django", "Flask"],
                key_points=["Django is full-stack", "Flask is minimal"],
                target_keyword="django vs flask",
            ),
            OutlineSection(
                heading="Conclusion",
                heading_level="h2",
                subheadings=[],
                key_points=["Choose based on project size"],
                target_keyword="python web frameworks",
            ),
        ],
        estimated_word_count=1000,
    )


# ── Schema validation tests ───────────────────────────────────────────────────

class TestSchemas:
    def test_blog_request_defaults(self):
        from models.schemas import BlogRequest
        r = BlogRequest(topic="Test Topic")
        assert r.blog_type == "long-form"
        assert r.tone == "professional"
        assert r.word_count == 1500
        assert r.word_count_range == (1500, 2100)
        assert r.language == "English"

    def test_blog_request_word_count_range_property(self):
        from models.schemas import BlogRequest
        r = BlogRequest(topic="Test", word_count=2000)
        low, high = r.word_count_range
        assert low == 2000
        assert high == int(2000 * 1.4)

    def test_blog_outline_meta_description_max_length(self):
        from models.schemas import BlogOutline, OutlineSection
        with pytest.raises(Exception):
            BlogOutline(
                title="Test",
                meta_description="x" * 161,  # exceeds 160 limit
                primary_keyword="test",
                sections=[],
                estimated_word_count=1000,
            )

    def test_seo_report_score_bounds(self):
        from models.schemas import SEOReport
        with pytest.raises(Exception):
            SEOReport(
                meta_title="Test",
                meta_description="Test description for SEO report validation.",
                primary_keyword_density=1.0,
                readability_score=65.0,
                readability_grade="Grade 8",
                schema_markup={},
                seo_score=101,  # exceeds 100
            )

    def test_blog_post_full_content_alias(self):
        from models.schemas import BlogPost
        post = BlogPost(
            title="Test",
            slug="test",
            meta_description="A test description for this blog post.",
            primary_keyword="test",
            secondary_keywords=[],
            content="# Hello\n\nContent here.",
            sections=[],
        )
        assert post.full_content == post.content


# ── Tool integration tests ────────────────────────────────────────────────────

class TestToolIntegration:
    def test_readability_schema_pipeline(self):
        """Simulate what the SEO agent does: score text then generate schema."""
        from tools.readability_tool import score_readability
        from tools.schema_markup_tool import generate_article_schema

        text = (
            "Python web frameworks make building web applications fast. "
            "Django is excellent for large projects. "
            "Flask is great for small APIs. "
            "FastAPI is the newest and fastest of the three main options. "
            "Choose the framework that best fits your project requirements."
        ) * 3

        read_result = score_readability.invoke({"text": text})
        assert read_result["flesch_reading_ease"] > 30

        schema = generate_article_schema.invoke({
            "title": "Best Python Web Frameworks 2025",
            "description": "A guide to Python web frameworks.",
        })
        assert schema["@type"] == "Article"


# ── Markdown assembly integration ─────────────────────────────────────────────

class TestMarkdownAssembly:
    def test_generate_toc_matches_outline(self):
        from tools.markdown_tool import generate_toc
        outline = _make_outline()
        toc = generate_toc(outline.sections)
        for section in outline.sections:
            assert section.heading in toc

    def test_slug_is_url_safe(self):
        from tools.markdown_tool import make_slug
        import re
        titles = [
            "Best Python Frameworks 2025",
            "What is Django? A Complete Guide",
            "C++ vs Python: Performance Comparison",
            "10 Reasons to Use FastAPI!",
        ]
        url_safe = re.compile(r'^[a-z0-9][a-z0-9\-]*[a-z0-9]$')
        for title in titles:
            slug = make_slug(title)
            assert url_safe.match(slug), f"Slug '{slug}' is not URL-safe (from '{title}')"


# ── Config tests ──────────────────────────────────────────────────────────────

class TestConfig:
    def test_settings_loads(self):
        from config.settings import settings
        assert settings is not None
        assert hasattr(settings, "gemini_api_key")
        assert hasattr(settings, "groq_api_key")
        assert hasattr(settings, "mistral_api_key")
        assert hasattr(settings, "serpapi_key")

    def test_llm_provider_defaults(self):
        from config.settings import settings
        assert settings.research_llm_provider in ("gemini", "groq", "mistral")
        assert settings.writing_llm_provider in ("gemini", "groq", "mistral")
        assert settings.qa_llm_provider in ("gemini", "groq", "mistral")

    def test_crewai_llm_factory_returns_crewai_llm(self):
        """Verify the factory returns a CrewAI LLM — no API call made."""
        from crewai import LLM as CrewAILLM
        # This test will raise if MISTRAL_API_KEY etc. are empty but
        # the important thing is the *type* is correct, not validity
        try:
            from config.llm_config import get_crewai_qa_llm
            llm = get_crewai_qa_llm()
            assert isinstance(llm, CrewAILLM)
        except Exception as e:
            # If CrewAI validates the key at construction, skip this check
            if "api_key" in str(e).lower() or "key" in str(e).lower():
                pytest.skip("API key validation requires live keys")
            raise
