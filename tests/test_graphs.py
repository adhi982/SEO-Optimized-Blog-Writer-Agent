"""
tests/test_graphs.py
====================
Unit tests for the 3 LangGraph sub-graphs.
All LLM calls are mocked — no API keys required.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_request(**kwargs):
    from models.schemas import BlogRequest
    defaults = {
        "topic": "Best Python Web Frameworks 2025",
        "target_keywords": ["python web frameworks", "django vs flask"],
        "blog_type": "How-To Guide",
        "tone": "Conversational",
        "word_count": 1500,
    }
    defaults.update(kwargs)
    return BlogRequest(**defaults)


def _make_outline():
    from models.schemas import BlogOutline, OutlineSection
    return BlogOutline(
        title="Best Python Web Frameworks 2025",
        meta_description="Discover the best Python web frameworks for your next project.",
        primary_keyword="python web frameworks",
        secondary_keywords=["django", "flask", "fastapi"],
        sections=[
            OutlineSection(
                heading="Why Choose Python for Web Development",
                heading_level="h2",
                subheadings=["Speed", "Community"],
                key_points=["Python is versatile", "Large ecosystem"],
                target_keyword="python web development",
            ),
            OutlineSection(
                heading="Top Python Web Frameworks Compared",
                heading_level="h2",
                subheadings=["Django", "Flask", "FastAPI"],
                key_points=["Django is batteries-included", "Flask is lightweight"],
                target_keyword="python frameworks comparison",
            ),
        ],
        estimated_word_count=1500,
    )


def _mock_llm_response(content: str) -> MagicMock:
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = content
    mock_llm.invoke.return_value = mock_response
    return mock_llm


# ── Research Graph ─────────────────────────────────────────────────────────────

class TestResearchGraph:
    def test_graph_compiles(self):
        from graphs.research_graph import research_graph
        assert research_graph is not None

    def test_graph_has_expected_nodes(self):
        from graphs.research_graph import research_graph
        graph_repr = str(research_graph.get_graph())
        for node in ["keyword_research", "serp_analysis", "competitor_analysis", "keyword_clustering"]:
            assert node in graph_repr

    @patch("graphs.research_graph.get_research_llm")
    @patch("graphs.research_graph.search_keywords")
    def test_run_research_graph_mocked(self, mock_search, mock_get_llm):
        import json
        from graphs.research_graph import run_research_graph

        mock_search.invoke.return_value = [
            {"title": "Result 1", "url": "https://example.com/1", "snippet": "s", "position": 1}
        ]
        mock_get_llm.return_value = _mock_llm_response(json.dumps({
            "primary_keyword": "python web frameworks",
            "secondary_keywords": ["django", "flask"],
            "lsi_keywords": ["web development"],
            "content_gaps": ["performance comparison"],
            "keyword_notes": "Strong informational intent.",
        }))

        request = _make_request()
        state = run_research_graph(request)

        assert state is not None
        assert isinstance(state, dict)
        assert "primary_keyword" in state or "keyword_data" in state or "research_summary" in state


# ── Writing Graph ─────────────────────────────────────────────────────────────

class TestWritingGraph:
    def test_graph_compiles(self):
        from graphs.writing_graph import writing_graph
        assert writing_graph is not None

    def test_graph_has_expected_nodes(self):
        from graphs.writing_graph import writing_graph
        graph_repr = str(writing_graph.get_graph())
        for node in ["write_section", "inject_citations", "enforce_brand_voice", "readability_check"]:
            assert node in graph_repr

    @patch("graphs.writing_graph.get_writing_llm")
    @patch("graphs.writing_graph.get_qa_llm")
    def test_run_writing_graph_mocked(self, mock_qa_llm, mock_writing_llm):
        from graphs.writing_graph import run_writing_graph

        section_content = "Python web frameworks provide tools for building web applications efficiently. Django is the most popular choice for large-scale projects. Flask offers flexibility for smaller applications."

        mock_writing_llm.return_value = _mock_llm_response(section_content)
        mock_qa_llm.return_value = _mock_llm_response(section_content)

        request = _make_request()
        outline = _make_outline()
        state = run_writing_graph(
            request=request,
            outline=outline,
            research_summary="Python has many excellent web frameworks.",
            citations_pool=["https://docs.djangoproject.com"],
        )

        assert state is not None
        assert "sections_written" in state


# ── QA Graph ──────────────────────────────────────────────────────────────────

class TestQAGraph:
    def test_graph_compiles(self):
        from graphs.qa_graph import qa_graph
        assert qa_graph is not None

    def test_graph_has_expected_nodes(self):
        from graphs.qa_graph import qa_graph
        graph_repr = str(qa_graph.get_graph())
        for node in ["fact_check", "plagiarism_scan", "seo_validate", "final_polish"]:
            assert node in graph_repr

    @patch("graphs.qa_graph.get_qa_llm")
    @patch("graphs.qa_graph.get_writing_llm")
    def test_run_qa_graph_mocked(self, mock_writing_llm, mock_qa_llm):
        from graphs.qa_graph import run_qa_graph

        polished_draft = "# Best Python Web Frameworks\n\nPython is great for web development.\n"
        mock_qa_llm.return_value = _mock_llm_response(polished_draft)
        mock_writing_llm.return_value = _mock_llm_response(polished_draft)

        request = _make_request()
        outline = _make_outline()
        state = run_qa_graph(
            request=request,
            full_draft="# Best Python Web Frameworks\n\nThis is a draft.",
            sections=[],
            outline=outline,
            research_summary="Python frameworks research.",
        )

        assert state is not None
        assert "final_draft" in state
