"""
Strategist Agent
================
Role: Content Strategist & SEO Architect
Pure LLM agent (no external tools). Takes the research output and
produces a fully structured BlogOutline with SEO-optimised titles,
heading hierarchy, key points per section, E-E-A-T signals, and
internal linking placeholders.
"""
from __future__ import annotations

import json
import re

from crewai import Agent, Task

from config.llm_config import get_crewai_research_llm
from models.schemas import BlogOutline, BlogRequest, OutlineSection


# ── Agent factory ─────────────────────────────────────────────────────────────

def create_strategist_agent() -> Agent:
    return Agent(
        role="Content Strategist & SEO Architect",
        goal=(
            "Transform raw keyword research into a winning blog outline that satisfies "
            "search intent, follows SEO best practices, and gives writers a clear "
            "roadmap to produce content that outranks competitors."
        ),
        backstory=(
            "You are a veteran content strategist who has planned hundreds of top-ranking "
            "blog posts. You understand the importance of matching content structure to "
            "search intent, building E-E-A-T signals, and creating logical information "
            "hierarchies. You know exactly how to craft titles that get clicks and outlines "
            "that make writing easy and SEO scores high."
        ),
        llm=get_crewai_research_llm(temperature=0.4),
        tools=[],
        verbose=True,
        allow_delegation=False,
    )


def create_strategist_task(
    agent: Agent,
    request: BlogRequest,
    research_output: str,
) -> Task:
    word_min, word_max = request.word_count_range
    return Task(
        description=(
            f"Create a detailed SEO blog outline based on the following research.\n\n"
            f"BLOG REQUEST:\n"
            f"- Topic: {request.topic}\n"
            f"- Blog type: {request.blog_type}\n"
            f"- Tone: {request.tone}\n"
            f"- Target audience: {request.target_audience}\n"
            f"- Word count target: {word_min}-{word_max} words\n\n"
            f"RESEARCH OUTPUT:\n{research_output}\n\n"
            "Produce a complete outline in this EXACT JSON format:\n"
            "```json\n"
            "{\n"
            '  "title": "SEO-optimised title with primary keyword",\n'
            '  "meta_description": "150-160 char description with primary keyword",\n'
            '  "primary_keyword": "...",\n'
            '  "secondary_keywords": ["kw1", "kw2", "kw3"],\n'
            '  "estimated_word_count": 2000,\n'
            '  "internal_linking_targets": ["related topic 1", "related topic 2"],\n'
            '  "sections": [\n'
            '    {\n'
            '      "heading": "Introduction heading",\n'
            '      "heading_level": "h2",\n'
            '      "subheadings": ["subheading 1", "subheading 2"],\n'
            '      "key_points": ["key point 1", "key point 2"],\n'
            '      "target_keyword": "keyword for this section"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "```\n\n"
            "RULES:\n"
            "- Title must include the primary keyword and be ≤65 characters\n"
            "- Meta description must be 150-160 characters with primary keyword\n"
            f"- Plan {max(5, word_min // 300)}-{min(10, word_max // 250)} sections (including intro & conclusion)\n"
            "- Each section should have 2-4 key points\n"
            "- Spread secondary keywords across sections (1 per section)\n"
            "- First section = introduction with hook + primary keyword\n"
            "- Last section = conclusion with CTA\n"
            "- Add an FAQ section if 'People Also Ask' questions were found in research\n"
            "- Include at least one E-E-A-T signal per section (expert tip, stat, case study cue)"
        ),
        expected_output=(
            "A valid JSON BlogOutline object with title, meta_description, primary_keyword, "
            "secondary_keywords, estimated_word_count, internal_linking_targets, and a "
            "list of sections each with heading, heading_level, subheadings, key_points, "
            "and target_keyword."
        ),
        agent=agent,
    )


# ── Output parser ─────────────────────────────────────────────────────────────

def parse_outline_from_output(raw_output: str, request: BlogRequest) -> BlogOutline:
    """
    Parse a BlogOutline from the strategist agent's raw text output.
    Falls back to a minimal outline if JSON cannot be extracted.
    """
    # Try to extract JSON block from the output
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_output, re.DOTALL)
    if not json_match:
        # Try bare JSON object
        json_match = re.search(r"(\{[\s\S]*\"sections\"[\s\S]*\})", raw_output)

    if json_match:
        try:
            data = json.loads(json_match.group(1))
            # Normalise sections
            sections = []
            for s in data.get("sections", []):
                sections.append(OutlineSection(
                    heading=s.get("heading", "Section"),
                    heading_level=s.get("heading_level", "h2"),
                    subheadings=s.get("subheadings", []),
                    key_points=s.get("key_points", []),
                    target_keyword=s.get("target_keyword"),
                ))
            return BlogOutline(
                title=data.get("title", request.topic),
                meta_description=data.get("meta_description", f"Learn all about {request.topic}.")[:160],
                primary_keyword=data.get("primary_keyword", request.topic),
                secondary_keywords=data.get("secondary_keywords", [])[:8],
                sections=sections,
                estimated_word_count=data.get("estimated_word_count", request.word_count_range[0]),
                internal_linking_targets=data.get("internal_linking_targets", []),
            )
        except (json.JSONDecodeError, Exception):
            pass

    # Fallback minimal outline
    return BlogOutline(
        title=request.topic,
        meta_description=f"A comprehensive guide to {request.topic}."[:160],
        primary_keyword=request.topic,
        secondary_keywords=[],
        sections=[
            OutlineSection(heading="Introduction", heading_level="h2", key_points=["Overview"]),
            OutlineSection(heading="Main Content", heading_level="h2", key_points=["Core topic"]),
            OutlineSection(heading="Conclusion", heading_level="h2", key_points=["Summary and CTA"]),
        ],
        estimated_word_count=request.word_count_range[0],
    )
