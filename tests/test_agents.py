"""
tests/test_agents.py
====================
Unit tests for CrewAI agents and crew assembly.
Agent instantiation and task creation are tested without running the LLM pipeline
(no API keys needed — we only test structure, not LLM execution).
"""
from __future__ import annotations

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_request():
    from models.schemas import BlogRequest
    return BlogRequest(
        topic="Best Python Web Frameworks 2025",
        target_keywords=["python web frameworks", "django"],
        blog_type="How-To Guide",
        tone="Conversational",
        word_count=1500,
    )


def _make_outline():
    from models.schemas import BlogOutline, OutlineSection
    return BlogOutline(
        title="Best Python Web Frameworks 2025",
        meta_description="Discover the best Python web frameworks for your next project in 2025.",
        primary_keyword="python web frameworks",
        secondary_keywords=["django", "flask", "fastapi"],
        sections=[
            OutlineSection(heading="Introduction", heading_level="h2", key_points=["Overview"]),
            OutlineSection(heading="Django Deep Dive", heading_level="h2", key_points=["Features"]),
            OutlineSection(heading="Conclusion", heading_level="h2", key_points=["Summary"]),
        ],
        estimated_word_count=1500,
    )


# ── Research Agent ────────────────────────────────────────────────────────────

class TestResearchAgent:
    def test_agent_instantiation(self):
        from agents.research_agent import create_research_agent
        agent = create_research_agent()
        assert agent.role == "Senior SEO Research Analyst"
        assert len(agent.tools) == 1

    def test_task_creation(self):
        from agents.research_agent import create_research_agent, create_research_task
        agent = create_research_agent()
        task = create_research_task(agent, _make_request())
        assert task is not None
        assert "python" in task.description.lower() or "keyword" in task.description.lower()
        assert task.agent == agent


# ── Strategist Agent ──────────────────────────────────────────────────────────

class TestStrategistAgent:
    def test_agent_instantiation(self):
        from agents.strategist_agent import create_strategist_agent
        agent = create_strategist_agent()
        assert agent.role == "Content Strategist & SEO Architect"
        assert len(agent.tools) == 0

    def test_task_creation(self):
        from agents.strategist_agent import create_strategist_agent, create_strategist_task
        agent = create_strategist_agent()
        task = create_strategist_task(agent, _make_request(), "Research output: python frameworks are popular.")
        assert task is not None
        assert task.agent == agent

    def test_parse_outline_from_output_valid_json(self):
        import json
        from agents.strategist_agent import parse_outline_from_output
        outline_json = json.dumps({
            "title": "Best Python Web Frameworks 2025",
            "meta_description": "Discover the best Python web frameworks for building fast applications.",
            "primary_keyword": "python web frameworks",
            "secondary_keywords": ["django", "flask"],
            "estimated_word_count": 1500,
            "sections": [
                {
                    "heading": "Why Python for Web Dev",
                    "heading_level": "h2",
                    "subheadings": [],
                    "key_points": ["Easy to learn"],
                    "target_keyword": "python web development",
                }
            ],
            "internal_linking_targets": [],
        })
        raw = f"```json\n{outline_json}\n```"
        outline = parse_outline_from_output(raw, _make_request())
        assert outline.title == "Best Python Web Frameworks 2025"
        assert len(outline.sections) == 1

    def test_parse_outline_from_output_fallback(self):
        from agents.strategist_agent import parse_outline_from_output
        # Invalid JSON → should fall back to default outline
        outline = parse_outline_from_output("", _make_request())
        assert outline is not None
        assert len(outline.sections) >= 1


# ── Writer Agent ──────────────────────────────────────────────────────────────

class TestWriterAgent:
    def test_agent_instantiation(self):
        from agents.writer_agent import create_writer_agent
        agent = create_writer_agent()
        assert agent.role == "Expert SEO Content Writer"
        assert len(agent.tools) == 1

    def test_task_creation(self):
        from agents.writer_agent import create_writer_agent, create_writer_task
        agent = create_writer_agent()
        task = create_writer_task(
            agent=agent,
            request=_make_request(),
            outline=_make_outline(),
            research_summary="Python is popular for web development.",
        )
        assert task is not None
        assert task.agent == agent

    def test_parse_writing_output_fallback(self):
        from agents.writer_agent import parse_writing_output
        sections, draft = parse_writing_output("Some plain text output with no JSON.")
        assert draft is not None


# ── SEO Agent ─────────────────────────────────────────────────────────────────

class TestSEOAgent:
    def test_agent_instantiation(self):
        from agents.seo_agent import create_seo_agent
        agent = create_seo_agent()
        assert agent.role == "Technical SEO Specialist"
        assert len(agent.tools) == 2  # ReadabilityScoreTool + ArticleSchemaTool

    def test_task_creation(self):
        from agents.seo_agent import create_seo_agent, create_seo_task
        agent = create_seo_agent()
        task = create_seo_task(
            agent=agent,
            request=_make_request(),
            outline=_make_outline(),
            full_draft="# Best Python Web Frameworks\n\nPython is great for web development.",
            sections=[],
        )
        assert task is not None

    def test_build_seo_report_programmatic(self):
        from agents.seo_agent import build_seo_report
        report = build_seo_report(
            outline=_make_outline(),
            full_draft=(
                "# Best Python Web Frameworks 2025\n\n"
                "Python web frameworks make building web apps easy. "
                "Django is a batteries-included framework that powers Instagram. "
                "Flask is a lightweight micro-framework great for small projects. "
                "FastAPI is the modern choice for building REST APIs quickly. "
                "When choosing python web frameworks for your project, consider "
                "the size and complexity of what you're building. "
                "For large-scale applications, Django provides everything you need. "
                "For APIs and microservices, FastAPI's type hints and auto-documentation shine.\n\n"
                "## Django Deep Dive\n\nDjango includes an ORM, admin panel, and authentication. "
                "It follows the batteries-included philosophy for rapid development.\n\n"
                "## Conclusion\n\nChoose python web frameworks based on your project requirements.\n"
            ),
        )
        assert 0 <= report.seo_score <= 100
        assert report.meta_title
        assert report.meta_description


# ── Editor Agent ──────────────────────────────────────────────────────────────

class TestEditorAgent:
    def test_agent_instantiation(self):
        from agents.editor_agent import create_editor_agent
        agent = create_editor_agent()
        assert agent.role == "Senior Content Editor & Fact Checker"
        assert len(agent.tools) == 1

    def test_task_creation(self):
        from agents.editor_agent import create_editor_agent, create_editor_task
        agent = create_editor_agent()
        task = create_editor_task(
            agent=agent,
            request=_make_request(),
            outline=_make_outline(),
            full_draft="# Test\n\nDraft content here.",
            research_summary="Summary",
            sections=[],
        )
        assert task is not None

    def test_parse_editor_output_passthrough(self):
        from agents.editor_agent import parse_editor_output
        draft = "# Final\n\nPolished content."
        output, passed = parse_editor_output(draft, fallback_draft=draft)
        assert isinstance(output, str)
        assert isinstance(passed, bool)


# ── SEOBlogCrew ───────────────────────────────────────────────────────────────

class TestSEOBlogCrew:
    def test_crew_instantiation(self):
        from agents.crew import SEOBlogCrew
        crew = SEOBlogCrew()
        assert crew is not None

    def test_crew_has_run_method(self):
        from agents.crew import SEOBlogCrew
        crew = SEOBlogCrew()
        assert callable(getattr(crew, "run", None))
