"""
Writing Sub-Graph (LangGraph)
==============================
Iterates through each outline section one at a time:
  write_section → inject_citations → enforce_brand_voice → readability_check
                                                               ↓
                                             next section OR → END

State controls the loop via `current_section_index`.
Each pass writes one BlogSection and appends it to `sections_written`.
"""
from __future__ import annotations

import re
from typing import Literal

from langchain_core.messages import HumanMessage

from langgraph.graph import END, START, StateGraph

from config.llm_config import get_writing_llm, get_qa_llm
from models.state import WritingState
from models.schemas import BlogSection, OutlineSection
from tools.readability_tool import score_readability

MAX_READABILITY_RETRIES = 2


# ── Node 1: Write Section ─────────────────────────────────────────────────────

def write_section(state: WritingState) -> WritingState:
    """Write the current outline section using the writing LLM."""
    llm = get_writing_llm(temperature=0.75)
    outline = state["outline"]
    idx = state.get("current_section_index", 0)
    request = state["request"]
    research_summary = state.get("research_summary", "")
    brand_voice = state.get("brand_voice_config", {})

    section_spec: OutlineSection = outline.sections[idx]
    tone_instruction = brand_voice.get("tone_instruction", f"Write in a {request.tone} tone.")

    # Build context from already-written sections (last 1 for continuity)
    prev_sections = state.get("sections_written", [])
    continuity_context = ""
    if prev_sections:
        last = prev_sections[-1]
        continuity_context = (
            f"\nFor continuity, the previous section was: '{last.heading}'. "
            "Ensure smooth transitions."
        )

    subheadings_str = "\n".join(f"  - {s}" for s in section_spec.subheadings) if section_spec.subheadings else ""
    key_points_str = "\n".join(f"  - {p}" for p in section_spec.key_points) if section_spec.key_points else ""
    target_kw = section_spec.target_keyword or outline.primary_keyword

    prompt = f"""You are an expert SEO content writer crafting a {request.blog_type} blog post.

TOPIC: {outline.title}
PRIMARY KEYWORD: {outline.primary_keyword}
TARGET AUDIENCE: {request.target_audience}
TONE: {request.tone}
{tone_instruction}

RESEARCH CONTEXT:
{research_summary[:1000]}
{continuity_context}

YOUR TASK: Write the following section in full.

SECTION HEADING: {section_spec.heading}
HEADING LEVEL: {section_spec.heading_level.upper()}
TARGET KEYWORD FOR THIS SECTION: {target_kw}
{"SUBHEADINGS TO COVER:" + chr(10) + subheadings_str if subheadings_str else ""}
{"KEY POINTS TO ADDRESS:" + chr(10) + key_points_str if key_points_str else ""}

WRITING RULES:
- Use the target keyword naturally 1-2 times (never force it)
- Write {200 if 'short' in request.blog_type.lower() else 300}-{400 if 'short' in request.blog_type.lower() else 600} words for this section
- Use short paragraphs (2-4 sentences max)
- Use transition phrases between paragraphs
- If subheadings are listed, use them as ### subheadings within the section
- Do NOT include the main heading — start straight with the body text
- Include at least one specific fact, statistic, or example
- End with a sentence that transitions to the next point

Write ONLY the section body (no heading line):"""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
    except Exception as e:
        content = f"[Writing error: {e}]"

    # Create a partial BlogSection — citations added in next node
    new_section = BlogSection(
        heading=section_spec.heading,
        content=content,
        citations=[],
        image_suggestions=[],
    )

    # Temporarily store the in-progress section in state
    return {
        **state,
        "_current_section_draft": new_section,
    }


# ── Node 2: Inject Citations ──────────────────────────────────────────────────

def inject_citations(state: WritingState) -> WritingState:
    """
    Match claims in the current section draft against the citations pool.
    Append relevant source URLs/references as citations.
    """
    llm = get_qa_llm(temperature=0.1)
    current: BlogSection = state.get("_current_section_draft")
    citations_pool: list[str] = state.get("citations_pool", [])

    if not current or not citations_pool:
        return state  # nothing to do

    citations_text = "\n".join(f"- {c}" for c in citations_pool[:20])
    prompt = f"""You are a fact-checking editor. Given this section content and a pool of sources,
select which sources (if any) are relevant and should be cited.

SECTION CONTENT:
{current.content[:800]}

AVAILABLE SOURCES:
{citations_text}

Return ONLY a comma-separated list of relevant source URLs/references (max 3).
If none are relevant, return: NONE"""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content.strip()
        if raw.upper() != "NONE" and raw:
            citations = [c.strip() for c in raw.split(",") if c.strip()][:3]
        else:
            citations = []
    except Exception:
        citations = []

    updated_section = BlogSection(
        heading=current.heading,
        content=current.content,
        citations=citations,
        image_suggestions=current.image_suggestions,
    )

    return {**state, "_current_section_draft": updated_section}


# ── Node 3: Enforce Brand Voice ───────────────────────────────────────────────

def enforce_brand_voice(state: WritingState) -> WritingState:
    """
    Check the section against brand voice rules.
    Rewrite if it significantly deviates from tone/style requirements.
    """
    llm = get_writing_llm(temperature=0.5)
    current: BlogSection = state.get("_current_section_draft")
    brand_voice: dict = state.get("brand_voice_config", {})
    request = state["request"]

    if not current:
        return state

    # Only rewrite if brand voice notes are explicitly provided
    brand_notes = brand_voice.get("notes") or request.brand_voice_notes
    if not brand_notes:
        return state

    prompt = f"""You are a brand voice editor. Review this content and adjust it to match the brand voice guidelines.

BRAND VOICE GUIDELINES:
{brand_notes}
Tone: {request.tone}
Target audience: {request.target_audience}

CONTENT TO REVIEW:
{current.content}

If the content already matches the guidelines well, return it unchanged.
If it needs adjustment, rewrite it maintaining all the same information and structure
but with the correct tone and style.

Return ONLY the rewritten content (no explanations):"""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        adjusted_content = response.content.strip()
    except Exception:
        adjusted_content = current.content  # keep original on error

    updated_section = BlogSection(
        heading=current.heading,
        content=adjusted_content,
        citations=current.citations,
        image_suggestions=current.image_suggestions,
    )

    return {**state, "_current_section_draft": updated_section}


# ── Node 4: Readability Check ─────────────────────────────────────────────────

def readability_check(state: WritingState) -> WritingState:
    """
    Score the section. If readability is below target AND we haven't
    exceeded the retry limit, rewrite for clarity.
    Finalise the section into sections_written.
    """
    llm = get_writing_llm(temperature=0.6)
    current: BlogSection = state.get("_current_section_draft")
    revision_count: int = state.get("revision_count", 0)

    if not current:
        return state

    score_result = score_readability.invoke({"text": current.content})
    passes = score_result.get("passes_target", True)
    feedback = score_result.get("feedback", [])

    if not passes and revision_count < MAX_READABILITY_RETRIES:
        feedback_str = " ".join(feedback)
        prompt = f"""Rewrite the following content to improve readability.

READABILITY ISSUES TO FIX:
{feedback_str}

RULES:
- Use shorter sentences (aim for 15-20 words average)
- Break long paragraphs into 2-3 sentences max
- Replace jargon with plain English where possible
- Keep all information and examples — just simplify the language

ORIGINAL CONTENT:
{current.content}

Return ONLY the rewritten content:"""

        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            improved_content = response.content.strip()
        except Exception:
            improved_content = current.content

        current = BlogSection(
            heading=current.heading,
            content=improved_content,
            citations=current.citations,
            image_suggestions=current.image_suggestions,
        )
        revision_count += 1

    # Finalise — add image suggestion placeholder
    image_suggestions = current.image_suggestions or [
        f"Relevant image illustrating: {current.heading}"
    ]
    final_section = BlogSection(
        heading=current.heading,
        content=current.content,
        citations=current.citations,
        image_suggestions=image_suggestions,
    )

    # Advance the section index and append to written sections
    sections_written = list(state.get("sections_written", []))
    sections_written.append(final_section)

    return {
        **state,
        "sections_written": sections_written,
        "current_section_index": state.get("current_section_index", 0) + 1,
        "revision_count": 0,  # reset per section
        "_current_section_draft": None,
    }


def route_after_readability(state: WritingState) -> Literal["write_section", "__end__"]:
    """Continue loop if more sections remain, otherwise END."""
    idx = state.get("current_section_index", 0)
    total = len(state["outline"].sections)
    if idx < total:
        return "write_section"
    return "__end__"


# ── Graph Assembly ────────────────────────────────────────────────────────────

def build_writing_graph():
    graph = StateGraph(WritingState)

    graph.add_node("write_section", write_section)
    graph.add_node("inject_citations", inject_citations)
    graph.add_node("enforce_brand_voice", enforce_brand_voice)
    graph.add_node("readability_check", readability_check)

    graph.add_edge(START, "write_section")
    graph.add_edge("write_section", "inject_citations")
    graph.add_edge("inject_citations", "enforce_brand_voice")
    graph.add_edge("enforce_brand_voice", "readability_check")
    graph.add_conditional_edges(
        "readability_check",
        route_after_readability,
        {
            "write_section": "write_section",
            "__end__": END,
        },
    )

    return graph.compile()


writing_graph = build_writing_graph()


def run_writing_graph(
    request,
    outline,
    research_summary: str = "",
    citations_pool: list[str] | None = None,
    brand_voice_config: dict | None = None,
) -> WritingState:
    """Entry point for the Writer Agent."""
    initial_state: WritingState = {
        "request": request,
        "outline": outline,
        "research_summary": research_summary,
        "brand_voice_config": brand_voice_config or {},
        "citations_pool": citations_pool or [],
        "current_section_index": 0,
        "revision_count": 0,
        "sections_written": [],
        "_current_section_draft": None,
    }
    return writing_graph.invoke(initial_state)
