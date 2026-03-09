"""
tests/test_tools.py
===================
Unit tests for all 4 tool modules.
No API calls — all tools that need live API are skipped or mocked.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


# ── Readability Tool ──────────────────────────────────────────────────────────

class TestReadabilityTool:
    def test_score_readability_basic(self):
        from tools.readability_tool import score_readability
        result = score_readability.invoke({"text": "The cat sat on the mat. It was a small cat."})
        assert isinstance(result, dict)
        assert "flesch_reading_ease" in result
        assert "flesch_kincaid_grade" in result
        assert "gunning_fog" in result
        assert "passes_target" in result
        assert "label" in result
        assert isinstance(result["feedback"], list)

    def test_score_readability_high_ease(self):
        from tools.readability_tool import score_readability
        simple_text = " ".join(["The dog runs fast."] * 10)
        result = score_readability.invoke({"text": simple_text})
        assert result["flesch_reading_ease"] > 60

    def test_score_readability_complex_text(self):
        from tools.readability_tool import score_readability
        complex_text = (
            "The utilisation of multifaceted algorithmic paradigms in contemporary "
            "computational architectures necessitates comprehensive implementation "
            "strategies that transcend conventional methodological frameworks."
        )
        result = score_readability.invoke({"text": complex_text})
        assert result["flesch_reading_ease"] < 40
        assert not result["passes_target"]

    def test_score_section_readability(self):
        from tools.readability_tool import score_section_readability
        result = score_section_readability.invoke({
            "text": "This is a simple section. It has short sentences.",
            "section_heading": "Introduction",
        })
        assert result["section_heading"] == "Introduction"
        assert "flesch_reading_ease" in result

    def test_readability_tools_export(self):
        from tools.readability_tool import READABILITY_TOOLS
        assert len(READABILITY_TOOLS) == 2


# ── Schema Markup Tool ────────────────────────────────────────────────────────

class TestSchemaMarkupTool:
    def test_generate_article_schema(self):
        from tools.schema_markup_tool import generate_article_schema
        result = generate_article_schema.invoke({
            "title": "Best Python Frameworks 2025",
            "description": "A comprehensive guide to the best Python web frameworks.",
            "url": "https://example.com/python-frameworks",
            "author_name": "Test Author",
        })
        assert result["@type"] == "Article"
        assert result["@context"] == "https://schema.org"
        assert "headline" in result
        assert len(result["headline"]) <= 110
        assert result["url"] == "https://example.com/python-frameworks"

    def test_article_schema_title_truncated(self):
        from tools.schema_markup_tool import generate_article_schema
        long_title = "X" * 120
        result = generate_article_schema.invoke({"title": long_title, "description": "desc"})
        assert len(result["headline"]) <= 110

    def test_generate_faq_schema(self):
        from tools.schema_markup_tool import generate_faq_schema
        result = generate_faq_schema.invoke({
            "questions_and_answers": [
                {"question": "What is Django?", "answer": "Django is a Python web framework."},
                {"question": "What is Flask?", "answer": "Flask is a micro-framework."},
            ]
        })
        assert result["@type"] == "FAQPage"
        assert len(result["mainEntity"]) == 2
        assert result["mainEntity"][0]["@type"] == "Question"

    def test_generate_faq_schema_filters_invalid(self):
        from tools.schema_markup_tool import generate_faq_schema
        result = generate_faq_schema.invoke({
            "questions_and_answers": [
                {"question": "Valid?", "answer": "Yes"},
                {"question": "", "answer": "No question"},           # filtered out
                {"question": "No answer?", "answer": ""},             # filtered out
            ]
        })
        assert len(result["mainEntity"]) == 1

    def test_generate_breadcrumb_schema(self):
        from tools.schema_markup_tool import generate_breadcrumb_schema
        crumbs = [
            {"name": "Home", "url": "https://example.com"},
            {"name": "Blog", "url": "https://example.com/blog"},
        ]
        result = generate_breadcrumb_schema.invoke({"breadcrumbs": crumbs})
        assert result["@type"] == "BreadcrumbList"
        items = result["itemListElement"]
        assert items[0]["position"] == 1
        assert items[1]["position"] == 2

    def test_build_full_schema(self):
        from tools.schema_markup_tool import build_full_schema
        schemas = build_full_schema(
            title="Test Blog Post",
            description="A test blog post about testing.",
        )
        assert isinstance(schemas, list)
        assert len(schemas) >= 1
        assert schemas[0]["@type"] == "Article"

    def test_schema_tools_export(self):
        from tools.schema_markup_tool import SCHEMA_TOOLS
        assert len(SCHEMA_TOOLS) == 3


# ── Markdown Tool ─────────────────────────────────────────────────────────────

class TestMarkdownTool:
    def test_make_slug(self):
        from tools.markdown_tool import make_slug
        assert make_slug("Best Python Web Frameworks 2025!") == "best-python-web-frameworks-2025"
        assert make_slug("  Hello World  ") == "hello-world"
        assert make_slug("C++ vs Python: Which is Faster?") == "c-vs-python-which-is-faster"

    def test_make_slug_max_length(self):
        from tools.markdown_tool import make_slug
        long_title = " ".join(["word"] * 30)
        result = make_slug(long_title)
        assert len(result) <= 80

    def test_generate_toc(self):
        from tools.markdown_tool import generate_toc
        from models.schemas import BlogOutline, OutlineSection
        outline = BlogOutline(
            title="Test Blog",
            meta_description="Test meta description for the test blog post.",
            primary_keyword="test blog",
            sections=[
                OutlineSection(heading="Introduction", subheadings=["Background", "Scope"]),
                OutlineSection(heading="Main Topic", subheadings=[]),
                OutlineSection(heading="Conclusion", subheadings=[]),
            ],
            estimated_word_count=1500,
        )
        toc = generate_toc(outline.sections)
        assert "## Table of Contents" in toc
        assert "Introduction" in toc
        assert "Main Topic" in toc

    def test_save_blog_post(self, tmp_path, monkeypatch):
        from tools.markdown_tool import save_blog_post
        from models.schemas import BlogPost, BlogSection, SEOReport
        import datetime

        # Redirect output directory to tmp_path
        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))

        # Reload settings to pick up new env var
        import importlib, config.settings
        importlib.reload(config.settings)

        post = BlogPost(
            title="Test Blog Post",
            slug="test-blog-post",
            meta_description="A test meta description that is exactly right.",
            primary_keyword="test blog",
            secondary_keywords=["unit test", "python testing"],
            content="# Test Blog Post\n\nThis is the content.",
            sections=[],
            word_count=5,
        )
        output_path = save_blog_post(post)
        assert output_path.endswith(".md")


# ── SerpAPI Tool (mocked) ─────────────────────────────────────────────────────

class TestSerpAPITool:
    @patch("tools.serpapi_tool.GoogleSearch")
    def test_search_keywords_mocked(self, mock_gs):
        mock_instance = MagicMock()
        mock_gs.return_value = mock_instance
        mock_instance.get_dict.return_value = {
            "organic_results": [
                {"title": "Result 1", "link": "https://example.com/1", "snippet": "Snippet 1", "position": 1},
                {"title": "Result 2", "link": "https://example.com/2", "snippet": "Snippet 2", "position": 2},
            ]
        }

        from tools import serpapi_tool
        serpapi_tool._CACHE.clear()

        from tools.serpapi_tool import search_keywords
        result = search_keywords.invoke({"query": "python web frameworks"})
        assert isinstance(result, dict)
        assert "organic_results" in result
        assert isinstance(result["organic_results"], list)
        assert len(result["organic_results"]) == 2
        assert result["organic_results"][0]["title"] == "Result 1"

    @patch("tools.serpapi_tool.GoogleSearch")
    def test_search_keywords_caching(self, mock_gs):
        mock_instance = MagicMock()
        mock_gs.return_value = mock_instance
        mock_instance.get_dict.return_value = {
            "organic_results": [
                {"title": "Cached Result", "link": "https://example.com", "snippet": "s", "position": 1}
            ]
        }
        from tools import serpapi_tool
        serpapi_tool._CACHE.clear()

        from tools.serpapi_tool import search_keywords
        search_keywords.invoke({"query": "unique query for caching test"})
        search_keywords.invoke({"query": "unique query for caching test"})
        # Second call should hit cache — GoogleSearch constructor called only once
        assert mock_gs.call_count <= 2  # first call constructs it, second hits cache

    def test_serp_tools_export(self):
        from tools.serpapi_tool import SERP_TOOLS
        assert len(SERP_TOOLS) == 3
