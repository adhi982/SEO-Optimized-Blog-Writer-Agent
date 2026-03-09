"""
Research Agent
==============
Role: Senior SEO Research Analyst
Executes the LangGraph research_graph to produce keyword data,
SERP analysis, competitor insights, and a structured research summary.
"""
from __future__ import annotations

import json

from crewai import Agent, Task
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from config.llm_config import get_crewai_research_llm
from graphs.research_graph import run_research_graph
from models.schemas import BlogRequest
from models.state import ResearchState


# ── LangGraph wrapper tool ────────────────────────────────────────────────────

class ResearchGraphInput(BaseModel):
    topic: str = Field(description="The main topic of the blog post.")
    blog_type: str = Field(default="long-form", description="The type of the blog post, e.g., 'Case Study'.")
    tone: str = Field(default="professional", description="The desired tone of the blog post.")
    target_audience: str = Field(default="general audience", description="The target audience.")
    target_keywords: list[str] = Field(default_factory=list, description="Target keywords if any.")
    word_count: int = Field(default=1500, description="Word count target.")
    language: str = Field(default="English", description="Language of the blog.")
    brand_voice_notes: str = Field(default="", description="Brand voice notes.")


class RunResearchGraphTool(BaseTool):
    name: str = "run_seo_research"
    description: str = (
        "Execute a full SEO research pipeline for a given blog topic. "
        "Performs keyword research, SERP analysis, competitor content analysis, "
        "and keyword clustering. Returns a structured research summary with "
        "primary keyword, secondary keywords, content gaps, and competitor insights."
    )
    args_schema: type[BaseModel] = ResearchGraphInput

    def _run(self, topic: str, blog_type: str = "long-form", tone: str = "professional", target_audience: str = "general", target_keywords: list[str] = None, word_count: int = 1500, language: str = "English", brand_voice_notes: str = "") -> str:
        request = BlogRequest(
            topic=topic,
            blog_type=blog_type,
            tone=tone,
            target_audience=target_audience,
            target_keywords=target_keywords or [],
            word_count=word_count,
            language=language,
            brand_voice_notes=brand_voice_notes,
        )
        state: ResearchState = run_research_graph(request)
        return json.dumps({
            "primary_keyword": state.get("primary_keyword", ""),
            "secondary_keywords": state.get("secondary_keywords", []),
            "keyword_clusters": state.get("keyword_clusters", {}),
            "content_gaps": state.get("content_gaps", []),
            "research_summary": state.get("research_summary", ""),
            "competitor_notes": (state.get("competitor_summaries") or [""])[0][:1000],
            "serp_keywords": list((state.get("serp_results") or {}).keys()),
        }, ensure_ascii=False)


# ── Agent factory ─────────────────────────────────────────────────────────────

def create_research_agent() -> Agent:
    return Agent(
        role="Senior SEO Research Analyst",
        goal=(
            "Conduct comprehensive keyword research and competitor analysis to identify "
            "the best primary keyword, secondary keywords, content gaps, and unique "
            "angles that will help this blog post outrank existing content."
        ),
        backstory=(
            "You are an expert SEO analyst with 10+ years of experience in search intent "
            "analysis, keyword difficulty assessment, and competitive content strategy. "
            "You have deep expertise in Google's ranking algorithms and can quickly identify "
            "what searchers truly want when they type a query. You never guess — you base "
            "every recommendation on real SERP data."
        ),
        llm=get_crewai_research_llm(temperature=0.2),
        tools=[RunResearchGraphTool()],
        verbose=True,
        allow_delegation=False,
    )


def create_research_task(agent: Agent, request: BlogRequest) -> Task:
    return Task(
        description=(
            f"Conduct full SEO research for the blog topic: '{request.topic}'.\n\n"
            f"Target keywords (if provided): {request.target_keywords or 'None — discover them.'}\n"
            f"Blog type: {request.blog_type}\n"
            f"Target audience: {request.target_audience}\n\n"
            "Use the run_seo_research tool by passing the individual fields directly (topic, blog_type, tone, etc.). Do NOT pass a JSON-serialised string.\n\n"
            "After running the tool, provide a structured summary including:\n"
            "1. PRIMARY_KEYWORD: the best keyword to target\n"
            "2. SECONDARY_KEYWORDS: supporting keywords (comma-separated)\n"
            "3. CONTENT_GAPS: what competitors miss (bullet points)\n"
            "4. UNIQUE_ANGLE: our differentiation strategy\n"
            "5. RESEARCH_SUMMARY: 2-3 paragraph overview for the writing team"
        ),
        expected_output=(
            "A structured research report containing: primary keyword, secondary keywords, "
            "content gaps, unique angle, and a 2-3 paragraph research summary. "
            "Also include the raw JSON output from the research tool."
        ),
        agent=agent,
    )
