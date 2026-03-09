"""
Writer Agent
============
Role: Expert SEO Content Writer
Wraps the LangGraph writing_graph. Iterates section-by-section through
the outline, writing content with natural keyword placement, citations,
brand voice compliance, and per-section readability checks.
"""
from __future__ import annotations

import json

from crewai import Agent, Task
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from config.llm_config import get_crewai_writing_llm
from graphs.writing_graph import run_writing_graph
from models.schemas import BlogOutline, BlogRequest, BlogSection
from models.state import WritingState


# ── LangGraph wrapper tool ────────────────────────────────────────────────────

class WritingGraphInput(BaseModel):
    blog_request_json: str = Field(description="JSON-serialised BlogRequest")
    outline_json: str = Field(description="JSON-serialised BlogOutline")
    research_summary: str = Field(default="", description="Research summary from research agent")
    citations_pool: list[str] = Field(default_factory=list, description="List of source URLs/references")
    brand_voice_notes: str = Field(default="", description="Brand voice instructions")


class RunWritingGraphTool(BaseTool):
    name: str = "run_section_writer"
    description: str = (
        "Write all blog sections following a structured outline. "
        "Iterates section-by-section, injecting citations, enforcing brand voice, "
        "and checking readability for each section. Returns the complete written "
        "blog content as a list of sections."
    )
    args_schema: type[BaseModel] = WritingGraphInput

    def _run(
        self,
        blog_request_json: str,
        outline_json: str,
        research_summary: str = "",
        citations_pool: list[str] | None = None,
        brand_voice_notes: str = "",
    ) -> str:
        request = BlogRequest(**json.loads(blog_request_json))
        outline = BlogOutline(**json.loads(outline_json))
        brand_voice_config = {"notes": brand_voice_notes} if brand_voice_notes else {}

        state: WritingState = run_writing_graph(
            request=request,
            outline=outline,
            research_summary=research_summary,
            citations_pool=citations_pool or [],
            brand_voice_config=brand_voice_config,
        )

        sections = state.get("sections_written", [])
        sections_data = [s.model_dump() for s in sections]
        full_draft = _sections_to_full_draft(outline, sections)

        return json.dumps({
            "sections": sections_data,
            "full_draft": full_draft,
            "sections_written_count": len(sections),
        }, ensure_ascii=False)


def _sections_to_full_draft(outline: BlogOutline, sections: list[BlogSection]) -> str:
    """Assemble all written sections into a single Markdown draft."""
    lines = [f"# {outline.title}", ""]
    for section in sections:
        heading = section.heading.strip()
        if not heading.startswith("#"):
            heading = f"## {heading}"
        lines.append(heading)
        lines.append("")
        lines.append(section.content.strip())
        lines.append("")
        if section.citations:
            lines.append("**Sources:** " + " | ".join(section.citations))
            lines.append("")
    return "\n".join(lines)


# ── Agent factory ─────────────────────────────────────────────────────────────

def create_writer_agent() -> Agent:
    return Agent(
        role="Expert SEO Content Writer",
        goal=(
            "Write engaging, comprehensive blog content section-by-section that naturally "
            "incorporates target keywords, provides genuine value to readers, and is "
            "optimised for both search engines and human readability."
        ),
        backstory=(
            "You are a professional content writer with a gift for making complex topics "
            "accessible and engaging. You understand that great SEO content isn't about "
            "stuffing keywords — it's about thoroughly answering what the reader needs "
            "while signalling authority and expertise. You write with a clear structure, "
            "strong topic sentences, smooth transitions, and memorable examples."
        ),
        llm=get_crewai_writing_llm(temperature=0.7),
        tools=[RunWritingGraphTool()],
        verbose=True,
        allow_delegation=False,
    )


def create_writer_task(
    agent: Agent,
    request: BlogRequest,
    outline: BlogOutline,
    research_summary: str,
    citations_pool: list[str] | None = None,
) -> Task:
    citations_pool = citations_pool or []
    return Task(
        description=(
            "Write the complete blog post section-by-section using the run_section_writer tool.\n\n"
            f"BLOG REQUEST JSON:\n{request.model_dump_json()}\n\n"
            f"OUTLINE JSON:\n{outline.model_dump_json()}\n\n"
            f"RESEARCH SUMMARY:\n{research_summary[:500]}\n\n"
            f"CITATIONS POOL:\n{json.dumps(citations_pool)}\n\n"
            f"BRAND VOICE NOTES: {request.brand_voice_notes or 'None — use the specified tone.'}\n\n"
            "Call the run_section_writer tool with:\n"
            "- blog_request_json: the BlogRequest JSON above\n"
            "- outline_json: the Outline JSON above\n"
            "- research_summary: the research summary\n"
            "- citations_pool: the citations list\n"
            "- brand_voice_notes: the brand voice notes\n\n"
            "After the tool completes, report how many sections were written and provide "
            "a summary of the content coverage."
        ),
        expected_output=(
            "Confirmation that all outline sections were written, with a count of sections "
            "completed and a brief summary. Also include the full_draft and sections JSON "
            "from the tool output for the SEO agent to use."
        ),
        agent=agent,
    )


# ── Output parser ─────────────────────────────────────────────────────────────

def parse_writing_output(raw_output: str) -> tuple[list[BlogSection], str]:
    """Extract sections and full_draft from the writer agent's output."""
    import re
    json_match = re.search(r'\{["\s]*"sections"[\s\S]*\}', raw_output)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            sections = [BlogSection(**s) for s in data.get("sections", [])]
            full_draft = data.get("full_draft", "")
            return sections, full_draft
        except Exception:
            pass
    return [], raw_output
