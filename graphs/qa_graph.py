"""
QA Sub-Graph (LangGraph)
=========================
Pipeline: fact_check → plagiarism_scan → seo_validate → final_polish
                                                              ↓
                                          revision_needed? ──► final_polish (max 2 loops)
                                                              ↓
                                                            END

Outputs: final_draft (str), qa_passed (bool)
"""
from __future__ import annotations

import re
from typing import Literal

from langchain_core.messages import HumanMessage

from langgraph.graph import END, START, StateGraph

from config.llm_config import get_qa_llm, get_writing_llm
from models.state import QAState

MAX_POLISH_ITERATIONS = 2


# ── Node 1: Fact Check ────────────────────────────────────────────────────────

def fact_check(state: QAState) -> QAState:
    """
    Scan the draft for unsupported claims and flag them.
    Uses research_summary as ground truth.
    """
    llm = get_qa_llm(temperature=0.1)
    draft = state["full_draft"]
    research = state.get("research_summary", "")

    prompt = f"""You are a rigorous fact-checker reviewing a blog post before publication.

RESEARCH CONTEXT (verified information):
{research[:2000]}

BLOG DRAFT (excerpt — first 3000 chars):
{draft[:3000]}

Review the draft against the research context and identify:
1. Any specific statistics, dates, or claims that cannot be verified from the research context
2. Any contradictions between the draft and the research
3. Any overly broad generalizations presented as facts

For each issue, write one line starting with "FLAG:" followed by the problematic text and the issue.
If there are no issues, write: ALL_CLEAR

Be concise — flag only genuine factual problems, not stylistic ones."""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content.strip()
        flags = [
            line.replace("FLAG:", "").strip()
            for line in raw.splitlines()
            if line.strip().startswith("FLAG:")
        ]
    except Exception as e:
        flags = [f"Fact-check error: {e}"]

    return {**state, "fact_check_results": flags}


# ── Node 2: Plagiarism Scan ───────────────────────────────────────────────────

def plagiarism_scan(state: QAState) -> QAState:
    """
    Check for passages that are too similar to source material or generic filler.
    Rewrite any flagged passages directly in the draft.
    """
    llm = get_writing_llm(temperature=0.7)
    draft = state["full_draft"]

    prompt = f"""You are an originality editor reviewing a blog post.

BLOG DRAFT:
{draft[:4000]}

Check for:
1. Passages that sound copied from generic sources or "SEO boilerplate" 
2. Repetitive sentences that say the same thing in different ways
3. Overly generic phrases like "In today's world...", "In conclusion, it is clear that..."

For each issue, write one line starting with "REWRITE:" followed by the exact phrase to replace.
If the content is original and varied, write: ORIGINAL_OK

List only the specific phrases to rewrite, not entire paragraphs."""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content.strip()
        flags = [
            line.replace("REWRITE:", "").strip()
            for line in raw.splitlines()
            if line.strip().startswith("REWRITE:")
        ]
    except Exception as e:
        flags = []

    # Rewrite flagged phrases directly in the draft
    updated_draft = draft
    if flags:
        rewrite_prompt = f"""Rewrite the following flagged phrases to be more original and engaging.
For each phrase, provide a replacement on a new line in the format: ORIGINAL ||| REPLACEMENT

PHRASES TO REWRITE:
{chr(10).join(f"- {f}" for f in flags[:5])}

Keep replacements concise and natural."""
        try:
            rw_response = llm.invoke([HumanMessage(content=rewrite_prompt)])
            for line in rw_response.content.splitlines():
                if "|||" in line:
                    parts = line.split("|||", 1)
                    original = parts[0].strip().lstrip("- ")
                    replacement = parts[1].strip()
                    if original and replacement and original in updated_draft:
                        updated_draft = updated_draft.replace(original, replacement, 1)
        except Exception:
            pass  # keep original draft on error

    return {
        **state,
        "full_draft": updated_draft,
        "plagiarism_flags": flags,
    }


# ── Node 3: SEO Validate ──────────────────────────────────────────────────────

def seo_validate(state: QAState) -> QAState:
    """
    Check: keyword presence in H1/intro, heading structure, keyword density,
    meta description length, and internal linking placeholders.
    Collect issues list for final_polish to address.
    """
    draft = state["full_draft"]
    outline = state["outline"]
    primary_kw = outline.primary_keyword.lower()

    issues: list[str] = []

    # Check H1 contains primary keyword
    h1_match = re.search(r"^#\s+(.+)$", draft, re.MULTILINE)
    if h1_match:
        h1_text = h1_match.group(1).lower()
        if primary_kw not in h1_text:
            issues.append(f"H1 does not contain primary keyword '{outline.primary_keyword}'")
    else:
        issues.append("No H1 heading found in the draft")

    # Check first paragraph contains primary keyword
    paragraphs = [p.strip() for p in draft.split("\n\n") if p.strip() and not p.strip().startswith("#")]
    if paragraphs:
        if primary_kw not in paragraphs[0].lower():
            issues.append(f"Primary keyword '{outline.primary_keyword}' not in first paragraph")

    # Check keyword density (target 1-2%)
    word_count = len(draft.split())
    kw_count = draft.lower().count(primary_kw)
    density = (kw_count / word_count * 100) if word_count > 0 else 0
    if density < 0.5:
        issues.append(f"Keyword density too low ({density:.1f}%) — increase natural usage")
    elif density > 3.0:
        issues.append(f"Keyword density too high ({density:.1f}%) — reduce keyword stuffing")

    # Check minimum word count
    target_min = state["request"].word_count_range[0]
    if word_count < target_min * 0.85:
        issues.append(f"Draft is {word_count} words — target minimum is {target_min}")

    # Check H2 structure
    h2_count = len(re.findall(r"^##\s", draft, re.MULTILINE))
    if h2_count < 2:
        issues.append(f"Only {h2_count} H2 headings found — add more structural sections")

    return {**state, "seo_issues": issues}


# ── Node 4: Final Polish ──────────────────────────────────────────────────────

def final_polish(state: QAState) -> QAState:
    """
    Apply all fixes identified by fact_check, plagiarism_scan, and seo_validate.
    Ensure the intro hooks the reader and the conclusion has a CTA.
    Smooth transitions between sections.
    """
    llm = get_writing_llm(temperature=0.65)
    draft = state["full_draft"]
    fact_flags = state.get("fact_check_results", [])
    seo_issues = state.get("seo_issues", [])
    outline = state["outline"]
    revision_count = state.get("revision_count", 0)

    issues_str = ""
    if fact_flags:
        issues_str += "\nFACT ISSUES TO FIX:\n" + "\n".join(f"- {f}" for f in fact_flags[:5])
    if seo_issues:
        issues_str += "\nSEO ISSUES TO FIX:\n" + "\n".join(f"- {s}" for s in seo_issues[:5])

    prompt = f"""You are a senior content editor doing a final polish pass on a blog post.

BLOG TITLE: {outline.title}
PRIMARY KEYWORD: {outline.primary_keyword}
META DESCRIPTION (for context): {outline.meta_description}

CURRENT DRAFT:
{draft[:5000]}

YOUR TASKS:
1. Fix any issues listed below (if any)
2. Ensure the opening paragraph is engaging and hooks the reader within the first 2 sentences
3. Ensure the conclusion has a clear call-to-action (CTA) or next step for the reader
4. Smooth any abrupt transitions between sections
5. Ensure the primary keyword appears naturally in the first paragraph if it doesn't already
{issues_str}

Return the COMPLETE improved draft. Preserve all headings, structure, and Markdown formatting.
Do not add any commentary — return only the blog content:"""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        polished = response.content.strip()
        # Basic sanity check — must be longer than 200 chars
        if len(polished) < 200:
            polished = draft
    except Exception:
        polished = draft

    # Determine if another revision pass is needed
    still_has_issues = bool(seo_issues) and revision_count < MAX_POLISH_ITERATIONS
    qa_passed = not seo_issues and not fact_flags

    return {
        **state,
        "full_draft": polished,
        "final_draft": polished,
        "revision_count": revision_count + 1,
        "revision_needed": still_has_issues,
        "qa_passed": qa_passed,
        # Clear issues after addressing them
        "seo_issues": [],
        "fact_check_results": [],
    }


def route_after_polish(state: QAState) -> Literal["final_polish", "__end__"]:
    if state.get("revision_needed") and state.get("revision_count", 0) < MAX_POLISH_ITERATIONS:
        return "final_polish"
    return "__end__"


# ── Graph Assembly ────────────────────────────────────────────────────────────

def build_qa_graph():
    graph = StateGraph(QAState)

    graph.add_node("fact_check", fact_check)
    graph.add_node("plagiarism_scan", plagiarism_scan)
    graph.add_node("seo_validate", seo_validate)
    graph.add_node("final_polish", final_polish)

    graph.add_edge(START, "fact_check")
    graph.add_edge("fact_check", "plagiarism_scan")
    graph.add_edge("plagiarism_scan", "seo_validate")
    graph.add_edge("seo_validate", "final_polish")
    graph.add_conditional_edges(
        "final_polish",
        route_after_polish,
        {
            "final_polish": "final_polish",
            "__end__": END,
        },
    )

    return graph.compile()


qa_graph = build_qa_graph()


def run_qa_graph(
    request,
    full_draft: str,
    sections,
    outline,
    research_summary: str = "",
) -> QAState:
    """Entry point for the Editor Agent."""
    initial_state: QAState = {
        "request": request,
        "full_draft": full_draft,
        "sections": sections,
        "outline": outline,
        "research_summary": research_summary,
        "fact_check_results": [],
        "plagiarism_flags": [],
        "seo_issues": [],
        "revision_count": 0,
        "final_draft": "",
        "revision_needed": False,
        "qa_passed": False,
    }
    return qa_graph.invoke(initial_state)
