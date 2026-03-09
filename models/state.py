"""
LangGraph state definitions (TypedDict).

Each sub-graph (research, writing, QA) has its own state class.
These are the single source of truth for what flows between nodes.
"""
from __future__ import annotations

from typing import Optional, TypedDict

from models.schemas import (
    BlogOutline,
    BlogRequest,
    BlogSection,
    KeywordData,
    SERPResult,
)


class ResearchState(TypedDict):
    # Input
    request: BlogRequest

    # Intermediate
    seed_keywords: list[str]
    keyword_data: list[KeywordData]
    serp_results: dict[str, list[SERPResult]]   # primary keyword → top SERP results
    competitor_summaries: list[str]
    content_gaps: list[str]
    keyword_clusters: dict[str, list[str]]       # cluster label → grouped keywords
    retry_count: int

    # Output (consumed by Strategist agent)
    primary_keyword: str
    secondary_keywords: list[str]
    research_summary: str


class WritingState(TypedDict):
    # Input
    request: BlogRequest
    outline: BlogOutline
    research_summary: str
    brand_voice_config: dict
    citations_pool: list[str]

    # Loop control
    current_section_index: int
    revision_count: int

    # Accumulates as the loop runs
    sections_written: list[BlogSection]

    # Temp: in-flight section being processed by the 4-node inner pipeline
    _current_section_draft: Optional[BlogSection]


class QAState(TypedDict):
    # Input
    request: BlogRequest
    full_draft: str
    sections: list[BlogSection]
    outline: BlogOutline
    research_summary: str

    # Intermediate
    fact_check_results: list[str]
    plagiarism_flags: list[str]
    seo_issues: list[str]
    revision_count: int

    # Output
    final_draft: str
    revision_needed: bool
    qa_passed: bool
