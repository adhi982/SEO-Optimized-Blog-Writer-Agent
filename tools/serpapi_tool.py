"""
SerpAPI Tool — LangChain-compatible tool for keyword research and SERP analysis.

Provides three actions:
  1. search_keywords     — organic results + related searches + People Also Ask
  2. get_serp_analysis   — top-10 SERP results for a keyword
  3. get_keyword_suggestions — related keyword ideas with context

Results are cached in-memory (per process) to avoid duplicate API calls.
"""
from __future__ import annotations

import time
from functools import lru_cache
from typing import Any

from langchain_core.tools import tool
from serpapi import GoogleSearch  # google-search-results package

from config.settings import settings
from models.schemas import KeywordData, SERPResult


# ── In-memory cache (key → (timestamp, result)) ──────────────────────────────

_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL_SECONDS = 3600  # 1 hour


def _cached_search(cache_key: str, params: dict) -> dict:
    """Run a SerpAPI search with simple TTL caching."""
    now = time.time()
    if cache_key in _CACHE:
        ts, result = _CACHE[cache_key]
        if now - ts < _CACHE_TTL_SECONDS:
            return result

    params["api_key"] = settings.serpapi_key
    search = GoogleSearch(params)
    result = search.get_dict()
    _CACHE[cache_key] = (now, result)
    return result


# ── Helper parsers ────────────────────────────────────────────────────────────

def _parse_organic(results: dict) -> list[SERPResult]:
    organic = results.get("organic_results", [])
    parsed: list[SERPResult] = []
    for item in organic[:10]:
        parsed.append(
            SERPResult(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
                position=item.get("position", 0),
                estimated_word_count=None,
            )
        )
    return parsed


def _parse_related_searches(results: dict) -> list[str]:
    return [r.get("query", "") for r in results.get("related_searches", [])]


def _parse_people_also_ask(results: dict) -> list[str]:
    return [q.get("question", "") for q in results.get("related_questions", [])]


# ── LangChain Tools ───────────────────────────────────────────────────────────

@tool
def search_keywords(query: str) -> dict:
    """
    Search Google for a query and return organic results, related searches,
    and 'People Also Ask' questions. Use this for initial keyword research.

    Args:
        query: The seed keyword or topic to research.

    Returns:
        dict with keys: organic_results (list[SERPResult dicts]),
        related_searches (list[str]), people_also_ask (list[str])
    """
    params = {
        "engine": "google",
        "q": query,
        "num": 10,
        "gl": "us",
        "hl": "en",
    }
    raw = _cached_search(f"kw::{query}", params)
    return {
        "organic_results": [r.model_dump() for r in _parse_organic(raw)],
        "related_searches": _parse_related_searches(raw),
        "people_also_ask": _parse_people_also_ask(raw),
    }


@tool
def get_serp_analysis(keyword: str) -> dict:
    """
    Fetch detailed SERP data for a keyword — top 10 organic results with
    titles, URLs, snippets, and positions. Also returns featured snippet if present.
    Use this to analyse what top-ranking content looks like.

    Args:
        keyword: The target keyword to analyse.

    Returns:
        dict with keys: top_results (list[SERPResult dicts]),
        featured_snippet (str | None), answer_box (str | None)
    """
    params = {
        "engine": "google",
        "q": keyword,
        "num": 10,
        "gl": "us",
        "hl": "en",
    }
    raw = _cached_search(f"serp::{keyword}", params)

    featured_snippet: str | None = None
    if "answer_box" in raw:
        featured_snippet = raw["answer_box"].get("answer") or raw["answer_box"].get("snippet")

    answer_box: str | None = None
    if "knowledge_graph" in raw:
        answer_box = raw["knowledge_graph"].get("description")

    return {
        "top_results": [r.model_dump() for r in _parse_organic(raw)],
        "featured_snippet": featured_snippet,
        "answer_box": answer_box,
    }


@tool
def get_keyword_suggestions(seed_keyword: str) -> dict:
    """
    Generate related keyword ideas using Google Autocomplete and related
    searches. Use this to expand keyword clusters.

    Args:
        seed_keyword: The base keyword to expand from.

    Returns:
        dict with keys: suggestions (list[str]), questions (list[str])
    """
    params = {
        "engine": "google_autocomplete",
        "q": seed_keyword,
        "gl": "us",
        "hl": "en",
    }
    raw = _cached_search(f"suggest::{seed_keyword}", params)
    suggestions = [s.get("value", "") for s in raw.get("suggestions", [])]

    # Also pull PAA from a regular search for questions
    serp_params = {
        "engine": "google",
        "q": seed_keyword,
        "num": 5,
        "gl": "us",
        "hl": "en",
    }
    serp_raw = _cached_search(f"kw_suggest_serp::{seed_keyword}", serp_params)
    questions = _parse_people_also_ask(serp_raw)

    return {
        "suggestions": suggestions[:15],
        "questions": questions[:10],
    }


# ── Convenience list for easy import by agents ───────────────────────────────
SERP_TOOLS = [search_keywords, get_serp_analysis, get_keyword_suggestions]
