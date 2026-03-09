"""
tests/conftest.py
=================
Shared pytest fixtures and configuration.
"""
from __future__ import annotations

import os
import sys

import pytest

# ── Make project root importable ─────────────────────────────────────────────
# Important when running pytest from inside the tests/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Stub out missing API keys so settings load without errors ─────────────────
def pytest_configure(config):
    """Set placeholder env vars so Pydantic Settings doesn't raise on missing keys."""
    placeholders = {
        "GEMINI_API_KEY": "test-gemini-key",
        "GROQ_API_KEY": "test-groq-key",
        "MISTRAL_API_KEY": "test-mistral-key",
        "SERPAPI_KEY": "test-serpapi-key",
    }
    for key, value in placeholders.items():
        if not os.environ.get(key):
            os.environ[key] = value


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def sample_request():
    from models.schemas import BlogRequest
    return BlogRequest(
        topic="Best Python Web Frameworks 2025",
        target_keywords=["python web frameworks", "django", "flask"],
        blog_type="How-To Guide",
        tone="Conversational",
        word_count=1500,
    )


@pytest.fixture
def sample_outline():
    from models.schemas import BlogOutline, OutlineSection
    return BlogOutline(
        title="Best Python Web Frameworks 2025",
        meta_description="Discover the top Python web frameworks for your next project in 2025.",
        primary_keyword="python web frameworks",
        secondary_keywords=["django", "flask", "fastapi"],
        sections=[
            OutlineSection(
                heading="Why Use Python for Web Development",
                heading_level="h2",
                subheadings=["Ecosystem", "Speed"],
                key_points=["Large community", "Rich libraries"],
                target_keyword="python web development",
            ),
            OutlineSection(
                heading="Top Python Web Frameworks Compared",
                heading_level="h2",
                subheadings=["Django", "Flask", "FastAPI"],
                key_points=["Django is batteries-included", "Flask is lightweight"],
                target_keyword="python frameworks comparison",
            ),
            OutlineSection(
                heading="How to Choose the Right Framework",
                heading_level="h2",
                subheadings=["Project Size", "Team Experience"],
                key_points=["Consider scalability", "Check learning curve"],
                target_keyword="choose python framework",
            ),
        ],
        estimated_word_count=1500,
    )


@pytest.fixture
def sample_draft(sample_outline):
    return (
        f"# {sample_outline.title}\n\n"
        "Python web frameworks are essential tools for building modern web applications. "
        "They provide structure, libraries, and conventions that accelerate development. "
        "In this guide, we explore the best python web frameworks for 2025.\n\n"
        "## Why Use Python for Web Development\n\n"
        "Python's ecosystem is vast and well-maintained. Whether you're building a simple "
        "REST API or a complex web application, python web frameworks have you covered. "
        "Django, Flask, and FastAPI each serve different use cases brilliantly.\n\n"
        "## Top Python Web Frameworks Compared\n\n"
        "Choosing between Django, Flask, and FastAPI depends on your project needs. "
        "Django is a batteries-included framework perfect for large projects. "
        "Flask offers minimalism and flexibility for smaller services. "
        "FastAPI is the modern choice for async APIs with automatic documentation.\n\n"
        "## How to Choose the Right Framework\n\n"
        "Consider the size of your team and the complexity of your project. "
        "For rapid development with built-in admin and ORM, Django wins. "
        "For microservices and APIs, FastAPI's performance and type safety are unmatched.\n\n"
        "## Conclusion\n\n"
        "Python web frameworks give developers powerful tools to build anything from simple "
        "scripts to enterprise-grade applications. Start with Django or Flask and grow from there.\n"
    )
