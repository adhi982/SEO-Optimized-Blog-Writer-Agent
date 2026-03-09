"""
Research Sub-Graph (LangGraph)
==============================
Pipeline: keyword_research → serp_analysis → competitor_analysis → keyword_clustering

Conditional retry edge: if keyword_data is empty after keyword_research,
loop back up to MAX_RETRIES times with an expanded query before proceeding.

State flows OUT via: primary_keyword, secondary_keywords, research_summary
"""
from __future__ import annotations

import json
from typing import Literal

from langchain_core.messages import HumanMessage

from langgraph.graph import END, START, StateGraph

from config.llm_config import get_research_llm
from models.state import ResearchState
from models.schemas import KeywordData, SERPResult
from tools.serpapi_tool import search_keywords, get_serp_analysis, get_keyword_suggestions

MAX_RETRIES = 3


# ── Node 1: Keyword Research ──────────────────────────────────────────────────

def keyword_research(state: ResearchState) -> ResearchState:
    """
    For every seed keyword in the request, call SerpAPI to gather:
    - Related keywords and suggestions
    - People Also Ask questions
    - Organic SERP results (for context)
    """
    request = state["request"]
    seed_keywords: list[str] = state.get("seed_keywords") or request.target_keywords or [request.topic]
    retry_count: int = state.get("retry_count", 0)

    all_keyword_data: list[KeywordData] = list(state.get("keyword_data") or [])
    seen_keywords: set[str] = {kd.keyword for kd in all_keyword_data}

    for seed in seed_keywords[:5]:  # max 5 seeds per pass to limit API calls
        try:
            kw_result = search_keywords.invoke({"query": seed})
            suggest_result = get_keyword_suggestions.invoke({"seed_keyword": seed})

            # Primary keyword entry
            if seed not in seen_keywords:
                all_keyword_data.append(
                    KeywordData(
                        keyword=seed,
                        intent="informational",
                        related_keywords=suggest_result.get("suggestions", [])[:8],
                        questions=suggest_result.get("questions", [])[:5],
                    )
                )
                seen_keywords.add(seed)

            # Related keywords from search
            for related in kw_result.get("related_searches", [])[:5]:
                if related and related not in seen_keywords:
                    all_keyword_data.append(
                        KeywordData(keyword=related, intent="informational")
                    )
                    seen_keywords.add(related)

        except Exception as e:
            # Don't crash — log and continue
            print(f"[keyword_research] SerpAPI error for '{seed}': {e}")

    # On retry, expand with topic-derived variations
    expanded_seeds = seed_keywords
    if retry_count > 0:
        expanded_seeds = seed_keywords + [
            f"best {request.topic}",
            f"how to {request.topic}",
            f"{request.topic} guide",
        ]

    return {
        **state,
        "seed_keywords": expanded_seeds,
        "keyword_data": all_keyword_data,
        "retry_count": retry_count,
    }


def route_after_keyword_research(state: ResearchState) -> Literal["serp_analysis", "keyword_research"]:
    """Retry if we have no keyword data and haven't hit the retry limit."""
    if not state.get("keyword_data") and state.get("retry_count", 0) < MAX_RETRIES:
        return "keyword_research"
    return "serp_analysis"


# ── Node 2: SERP Analysis ─────────────────────────────────────────────────────

def serp_analysis(state: ResearchState) -> ResearchState:
    """
    For the top 3 keywords, fetch SERP top-10 results.
    Identify average content length, common heading patterns, and featured snippets.
    """
    keyword_data: list[KeywordData] = state.get("keyword_data", [])
    top_keywords = [kd.keyword for kd in keyword_data[:3]]

    serp_results: dict[str, list[SERPResult]] = dict(state.get("serp_results") or {})

    for keyword in top_keywords:
        if keyword in serp_results:
            continue
        try:
            analysis = get_serp_analysis.invoke({"keyword": keyword})
            results = [SERPResult(**r) for r in analysis.get("top_results", [])]
            serp_results[keyword] = results
        except Exception as e:
            print(f"[serp_analysis] SerpAPI error for '{keyword}': {e}")
            serp_results[keyword] = []

    return {**state, "serp_results": serp_results}


# ── Node 3: Competitor Analysis ───────────────────────────────────────────────

def competitor_analysis(state: ResearchState) -> ResearchState:
    """
    Use the LLM to analyse SERP snippets from top 3 competitors per keyword.
    Identify: common angles, topics covered, content gaps, unique angles we can own.
    """
    llm = get_research_llm(temperature=0.2)
    serp_results: dict[str, list[SERPResult]] = state.get("serp_results", {})
    request = state["request"]

    # Build a concise summary of what competitors cover
    competitor_context_parts: list[str] = []
    for keyword, results in serp_results.items():
        snippets = "\n".join(
            f"  [{r.position}] {r.title}: {r.snippet}" for r in results[:5]
        )
        competitor_context_parts.append(f"Keyword: {keyword}\nTop results:\n{snippets}")

    competitor_context = "\n\n".join(competitor_context_parts) or "No SERP data available."

    prompt = f"""You are an expert SEO content strategist.

Topic: {request.topic}
Blog type: {request.blog_type}
Target audience: {request.target_audience}

Here are the top SERP results for the target keywords:
{competitor_context}

Analyse the competitor content and provide:
1. COMPETITOR_THEMES: What topics/angles appear repeatedly across top results (3-5 bullet points)
2. CONTENT_GAPS: What important subtopics are missing or underserved (3-5 bullet points)  
3. UNIQUE_ANGLES: Specific differentiation angles we can use to outrank them (2-3 bullet points)

Be specific and actionable. Format each section with its label on its own line."""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        analysis_text = response.content
    except Exception as e:
        analysis_text = f"Competitor analysis unavailable: {e}"

    # Extract content gaps as a list
    content_gaps: list[str] = []
    in_gaps = False
    for line in analysis_text.splitlines():
        if "CONTENT_GAPS" in line:
            in_gaps = True
            continue
        if in_gaps and line.strip().startswith(("-", "•", "*", "1", "2", "3", "4", "5")):
            content_gaps.append(line.strip().lstrip("-•*0123456789. "))
        elif in_gaps and line.strip() and not line.strip()[0].isdigit() and ":" in line:
            in_gaps = False

    return {
        **state,
        "competitor_summaries": [analysis_text],
        "content_gaps": content_gaps,
    }


# ── Node 4: Keyword Clustering ────────────────────────────────────────────────

def keyword_clustering(state: ResearchState) -> ResearchState:
    """
    Group all gathered keywords by search intent using the LLM.
    Select the best primary keyword and top secondary keywords.
    Produce a structured research_summary for the Strategist agent.
    """
    llm = get_research_llm(temperature=0.1)
    keyword_data: list[KeywordData] = state.get("keyword_data", [])
    request = state["request"]

    keyword_list = "\n".join(f"- {kd.keyword}" for kd in keyword_data[:30])
    content_gaps = "\n".join(f"- {g}" for g in state.get("content_gaps", []))
    competitor_notes = (state.get("competitor_summaries") or [""])[0][:1500]

    prompt = f"""You are an SEO keyword strategist.

Topic: {request.topic}
Blog type: {request.blog_type}
Target audience: {request.target_audience}

Available keywords:
{keyword_list}

Content gaps identified from competitor analysis:
{content_gaps}

Tasks:
1. PRIMARY_KEYWORD: Select the single best keyword to target (high relevance, likely moderate difficulty)
2. SECONDARY_KEYWORDS: List 5-8 supporting keywords (comma-separated on one line)
3. CLUSTERS:
   - Informational: [keywords]
   - Transactional: [keywords]
   - Navigational: [keywords]
4. RESEARCH_SUMMARY: Write 2-3 paragraphs summarising: what searchers want, what competitors cover, what gaps exist, and what unique angle this blog should take.

Format each section with its label on its own line."""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        text = response.content
    except Exception as e:
        text = ""
        print(f"[keyword_clustering] LLM error: {e}")

    # ── Parse output ──────────────────────────────────────────────────────────
    primary_keyword = request.topic  # fallback
    secondary_keywords: list[str] = [kd.keyword for kd in keyword_data[1:6]]
    clusters: dict[str, list[str]] = {}
    research_summary = text

    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("PRIMARY_KEYWORD"):
            rest = line.split(":", 1)[-1].strip()
            if rest:
                primary_keyword = rest
        elif line.strip().startswith("SECONDARY_KEYWORDS"):
            rest = line.split(":", 1)[-1].strip()
            if rest:
                secondary_keywords = [k.strip() for k in rest.split(",") if k.strip()]
        elif "Informational:" in line:
            items = line.split(":", 1)[-1].strip()
            clusters["informational"] = [k.strip() for k in items.split(",") if k.strip()]
        elif "Transactional:" in line:
            items = line.split(":", 1)[-1].strip()
            clusters["transactional"] = [k.strip() for k in items.split(",") if k.strip()]
        elif line.strip().startswith("RESEARCH_SUMMARY"):
            research_summary = "\n".join(lines[i + 1:]).strip()
            break

    return {
        **state,
        "primary_keyword": primary_keyword,
        "secondary_keywords": secondary_keywords[:8],
        "keyword_clusters": clusters,
        "research_summary": research_summary,
    }


# ── Graph Assembly ────────────────────────────────────────────────────────────

def build_research_graph():
    graph = StateGraph(ResearchState)

    graph.add_node("keyword_research", keyword_research)
    graph.add_node("serp_analysis", serp_analysis)
    graph.add_node("competitor_analysis", competitor_analysis)
    graph.add_node("keyword_clustering", keyword_clustering)

    graph.add_edge(START, "keyword_research")
    graph.add_conditional_edges(
        "keyword_research",
        route_after_keyword_research,
        {
            "keyword_research": "keyword_research",
            "serp_analysis": "serp_analysis",
        },
    )
    graph.add_edge("serp_analysis", "competitor_analysis")
    graph.add_edge("competitor_analysis", "keyword_clustering")
    graph.add_edge("keyword_clustering", END)

    return graph.compile()


# Singleton — import and call run_research_graph() from agents
research_graph = build_research_graph()


def run_research_graph(request) -> ResearchState:
    """Entry point for the Research Agent."""
    initial_state: ResearchState = {
        "request": request,
        "seed_keywords": request.target_keywords or [request.topic],
        "keyword_data": [],
        "serp_results": {},
        "competitor_summaries": [],
        "content_gaps": [],
        "keyword_clusters": {},
        "retry_count": 0,
        "primary_keyword": "",
        "secondary_keywords": [],
        "research_summary": "",
    }
    return research_graph.invoke(initial_state)
