"""
SEO Optimizer Agent
===================
Role: Technical SEO Specialist
Pure tool-based agent. Analyses the full blog draft and produces a
complete SEOReport: meta tags, JSON-LD schema, keyword density,
readability scores, alt-text suggestions, and actionable improvements.
"""
from __future__ import annotations

import json
import re
from datetime import datetime

import textstat
from crewai import Agent, Task
from crewai.tools import BaseTool as CrewBaseTool
from pydantic import BaseModel, Field

from config.llm_config import get_crewai_qa_llm, get_qa_llm
from models.schemas import BlogOutline, BlogRequest, BlogSection, SEOReport
from tools.readability_tool import score_readability
from tools.schema_markup_tool import build_full_schema


# ── CrewAI-compatible tool wrappers ───────────────────────────────────────────

class _ReadabilityInput(BaseModel):
    text: str = Field(description="Plain text or Markdown content to score")


class ReadabilityScoreTool(CrewBaseTool):
    name: str = "score_readability"
    description: str = (
        "Score the readability of a text block. Returns Flesch Reading Ease (target 60-70), "
        "Flesch-Kincaid Grade Level (target 7-9), Gunning Fog index (<12), and feedback."
    )
    args_schema: type[BaseModel] = _ReadabilityInput

    def _run(self, text: str) -> str:
        clean = text.replace("#", "").replace("*", "").replace("`", "").replace(">", "").replace("_", "")
        ease = round(textstat.flesch_reading_ease(clean), 2)
        grade = round(textstat.flesch_kincaid_grade(clean), 2)
        fog = round(textstat.gunning_fog(clean), 2)
        return json.dumps({
            "flesch_reading_ease": ease,
            "flesch_kincaid_grade": grade,
            "gunning_fog": fog,
            "passes_target": 60 <= ease <= 75 and grade <= 10,
        })


class _SchemaInput(BaseModel):
    title: str = Field(description="Blog post title")
    description: str = Field(description="Meta description ≤160 chars")
    url: str = Field(default="", description="Canonical URL (optional)")
    author_name: str = Field(default="SEO Blog Agent", description="Author name")


class ArticleSchemaTool(CrewBaseTool):
    name: str = "generate_article_schema"
    description: str = (
        "Generate a JSON-LD Article schema for a blog post. "
        "Returns a structured data dict ready to embed in the page."
    )
    args_schema: type[BaseModel] = _SchemaInput

    def _run(self, title: str, description: str, url: str = "", author_name: str = "SEO Blog Agent") -> str:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        schema: dict = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": title[:110],
            "description": description[:160],
            "author": {"@type": "Person", "name": author_name},
            "datePublished": today,
            "dateModified": today,
        }
        if url:
            schema["url"] = url
        return json.dumps(schema, ensure_ascii=False)


_SEO_CREW_TOOLS = [ReadabilityScoreTool(), ArticleSchemaTool()]


# ── Agent factory ─────────────────────────────────────────────────────────────

def create_seo_agent() -> Agent:
    return Agent(
        role="Technical SEO Specialist",
        goal=(
            "Analyse the blog draft and produce a comprehensive SEO report with optimised "
            "meta title, meta description, JSON-LD schema markup, keyword density analysis, "
            "readability scores, and actionable improvement suggestions."
        ),
        backstory=(
            "You are a seasoned technical SEO expert who has optimised thousands of web pages. "
            "You have deep knowledge of Google's quality guidelines, Core Web Vitals, structured "
            "data, and on-page optimisation techniques. You are meticulous — you check every "
            "meta tag, every heading, and every keyword placement. Your reports are precise, "
            "data-driven, and give writers clear, prioritised actions."
        ),
        llm=get_crewai_qa_llm(temperature=0.2),
        tools=_SEO_CREW_TOOLS,
        verbose=True,
        allow_delegation=False,
    )


def create_seo_task(
    agent: Agent,
    request: BlogRequest,
    outline: BlogOutline,
    full_draft: str,
    sections: list[BlogSection],
) -> Task:
    return Task(
        description=(
            "Perform a full SEO analysis of the blog draft and produce an SEOReport.\n\n"
            f"PRIMARY KEYWORD: {outline.primary_keyword}\n"
            f"SECONDARY KEYWORDS: {', '.join(outline.secondary_keywords)}\n"
            f"META DESCRIPTION TARGET: ≤160 characters\n"
            f"META TITLE TARGET: ≤60 characters, include primary keyword\n\n"
            f"BLOG DRAFT (first 3000 chars):\n{full_draft[:3000]}\n\n"
            "YOUR TASKS:\n"
            "1. Use score_readability tool on the draft to get Flesch scores\n"
            "2. Use generate_article_schema tool with title and description\n"
            "3. Manually calculate keyword density: count primary keyword occurrences / total words * 100\n"
            "4. Evaluate heading structure (H1, H2, H3 hierarchy)\n"
            "5. Suggest alt-text for any image placeholders found\n"
            "6. Suggest 2-3 internal linking opportunities based on secondary keywords\n\n"
            "Return results in this EXACT JSON format:\n"
            "```json\n"
            "{\n"
            '  "meta_title": "≤60 char title with primary keyword",\n'
            '  "meta_description": "150-160 char description",\n'
            '  "primary_keyword_density": 1.5,\n'
            '  "readability_score": 65.2,\n'
            '  "readability_grade": "Grade 8",\n'
            '  "schema_markup": {},\n'
            '  "alt_text_suggestions": ["suggestion 1"],\n'
            '  "internal_link_suggestions": ["anchor text → target page"],\n'
            '  "seo_score": 78,\n'
            '  "suggestions": ["actionable suggestion 1", "actionable suggestion 2"]\n'
            "}\n"
            "```\n\n"
            "SEO score rubric (0-100):\n"
            "- Primary keyword in title: +15\n"
            "- Primary keyword in meta description: +10\n"
            "- Primary keyword in H1: +10\n"
            "- Primary keyword in first paragraph: +10\n"
            "- Keyword density 1-2%: +15\n"
            "- Readability ease 60-70: +15\n"
            "- Schema markup present: +10\n"
            "- ≥3 H2 headings: +10\n"
            "- Meta description ≤160 chars: +5"
        ),
        expected_output=(
            "A valid JSON SEOReport with meta_title, meta_description, "
            "primary_keyword_density, readability_score, readability_grade, "
            "schema_markup, alt_text_suggestions, internal_link_suggestions, "
            "seo_score, and suggestions list."
        ),
        agent=agent,
    )


# ── SEO report builder (direct, no agent needed for programmatic use) ─────────

def build_seo_report(
    outline: BlogOutline,
    full_draft: str,
    url: str = "",
) -> SEOReport:
    """
    Build SEOReport programmatically (used inside crew.py when agent output
    parsing fails or for direct pipeline use).
    """
    llm = get_qa_llm(temperature=0.1)

    # Readability
    read_result = score_readability.invoke({"text": full_draft})
    ease: float = read_result["flesch_reading_ease"]
    grade: float = read_result["flesch_kincaid_grade"]

    # Keyword density
    words = full_draft.lower().split()
    kw = outline.primary_keyword.lower()
    kw_count = full_draft.lower().count(kw)
    density = round((kw_count / len(words) * 100) if words else 0.0, 2)

    # Schema
    schema_list = build_full_schema(
        title=outline.title,
        description=outline.meta_description,
        url=url,
    )
    schema = schema_list[0] if schema_list else {}

    # Meta title (ensure ≤60 chars with keyword)
    meta_title = outline.title
    if len(meta_title) > 60:
        meta_title = meta_title[:57] + "..."

    # SEO score
    score = 0
    if kw.lower() in meta_title.lower():
        score += 15
    if kw.lower() in outline.meta_description.lower():
        score += 10
    h1_match = re.search(r"^#\s+(.+)$", full_draft, re.MULTILINE)
    if h1_match and kw.lower() in h1_match.group(1).lower():
        score += 10
    paragraphs = [p.strip() for p in full_draft.split("\n\n") if p.strip() and not p.startswith("#")]
    if paragraphs and kw.lower() in paragraphs[0].lower():
        score += 10
    if 0.8 <= density <= 2.5:
        score += 15
    if 55 <= ease <= 75:
        score += 15
    if schema:
        score += 10
    h2_count = len(re.findall(r"^##\s", full_draft, re.MULTILINE))
    if h2_count >= 3:
        score += 10
    if len(outline.meta_description) <= 160:
        score += 5

    # Suggestions
    suggestions = read_result.get("feedback", [])
    if density < 0.8:
        suggestions.append(f"Increase primary keyword '{outline.primary_keyword}' usage (currently {density:.1f}%)")
    if density > 2.5:
        suggestions.append(f"Reduce keyword density from {density:.1f}% to 1-2%")

    return SEOReport(
        meta_title=meta_title,
        meta_description=outline.meta_description,
        primary_keyword_density=density,
        readability_score=ease,
        readability_grade=f"Grade {grade:.0f}",
        schema_markup=schema,
        alt_text_suggestions=[f"Image illustrating {s.heading}" for s in outline.sections[:3]],
        internal_link_suggestions=[f"Link '{kw}' → /{kw.replace(' ', '-')}" for kw in outline.secondary_keywords[:3]],
        seo_score=min(score, 100),
        suggestions=suggestions[:5],
    )


# ── Output parser ─────────────────────────────────────────────────────────────

def parse_seo_report_from_output(
    raw_output: str,
    outline: BlogOutline,
    full_draft: str,
) -> SEOReport:
    """Parse SEOReport from agent output JSON, fall back to build_seo_report."""
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_output, re.DOTALL)
    if not json_match:
        json_match = re.search(r"(\{[\s\S]*\"seo_score\"[\s\S]*?\})", raw_output)

    if json_match:
        try:
            data = json.loads(json_match.group(1))
            return SEOReport(**data)
        except Exception:
            pass

    return build_seo_report(outline, full_draft)
