"""
Editor Agent
============
Role: Senior Content Editor & Fact Checker
Wraps the LangGraph qa_graph. Runs fact-checking, plagiarism avoidance,
SEO validation, and final polish passes on the complete draft.
This is the last quality gate before the blog is saved.
"""
from __future__ import annotations

import json

from crewai import Agent, Task
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from config.llm_config import get_crewai_qa_llm
from graphs.qa_graph import run_qa_graph
from models.schemas import BlogOutline, BlogRequest, BlogSection
from models.state import QAState


# ── LangGraph wrapper tool ────────────────────────────────────────────────────

class QAGraphInput(BaseModel):
    blog_request_json: str = Field(description="JSON-serialised BlogRequest")
    full_draft: str = Field(description="Complete Markdown blog draft")
    outline_json: str = Field(description="JSON-serialised BlogOutline")
    research_summary: str = Field(default="", description="Research summary for fact-checking")
    sections_json: str = Field(default="[]", description="JSON-serialised list of BlogSection objects")


class RunQAGraphTool(BaseTool):
    name: str = "run_qa_pipeline"
    description: str = (
        "Run a full quality assurance pipeline on the blog draft. "
        "Performs fact-checking against research sources, plagiarism scanning, "
        "SEO structure validation, and a final polish pass (up to 2 revision loops). "
        "Returns the improved final draft and a QA pass/fail status."
    )
    args_schema: type[BaseModel] = QAGraphInput

    def _run(
        self,
        blog_request_json: str,
        full_draft: str,
        outline_json: str,
        research_summary: str = "",
        sections_json: str = "[]",
    ) -> str:
        request = BlogRequest(**json.loads(blog_request_json))
        outline = BlogOutline(**json.loads(outline_json))
        sections_raw = json.loads(sections_json)
        sections = [BlogSection(**s) for s in sections_raw]

        state: QAState = run_qa_graph(
            request=request,
            full_draft=full_draft,
            sections=sections,
            outline=outline,
            research_summary=research_summary,
        )

        return json.dumps({
            "final_draft": state.get("final_draft", full_draft),
            "qa_passed": state.get("qa_passed", False),
            "fact_check_results": state.get("fact_check_results", []),
            "plagiarism_flags": state.get("plagiarism_flags", []),
            "seo_issues": state.get("seo_issues", []),
            "revision_count": state.get("revision_count", 0),
        }, ensure_ascii=False)


# ── Agent factory ─────────────────────────────────────────────────────────────

def create_editor_agent() -> Agent:
    return Agent(
        role="Senior Content Editor & Fact Checker",
        goal=(
            "Ensure the blog post is factually accurate, original, SEO-validated, "
            "and polished to publication standard. Every claim must be supported, "
            "every heading structurally sound, and the writing must flow naturally "
            "from start to finish."
        ),
        backstory=(
            "You are a meticulous senior editor who spent years at leading digital "
            "publications. You have an eye for unsupported claims, repetitive phrasing, "
            "weak introductions, and missing CTAs. You believe that great content is "
            "earned through rigorous editing — not just the first draft. You use "
            "systematic checklists and never publish anything that hasn't passed your "
            "strict quality bar."
        ),
        llm=get_crewai_qa_llm(temperature=0.2),
        tools=[RunQAGraphTool()],
        verbose=True,
        allow_delegation=False,
    )


def create_editor_task(
    agent: Agent,
    request: BlogRequest,
    outline: BlogOutline,
    full_draft: str,
    sections: list[BlogSection],
    research_summary: str,
) -> Task:
    sections_json = json.dumps([s.model_dump() for s in sections])
    return Task(
        description=(
            "Run a full QA pipeline on the blog draft using the run_qa_pipeline tool.\n\n"
            "Call the tool with:\n"
            f"- blog_request_json: {request.model_dump_json()}\n"
            f"- outline_json: {outline.model_dump_json()}\n"
            f"- research_summary: {research_summary[:300]}\n"
            "- full_draft: (the complete blog draft below)\n"
            f"- sections_json: {sections_json[:500]}...\n\n"
            f"FULL DRAFT (first 2000 chars for context):\n{full_draft[:2000]}\n\n"
            "After the QA pipeline completes, report:\n"
            "1. QA PASS/FAIL status\n"
            "2. Number of fact-check flags found and addressed\n"
            "3. Number of plagiarism flags rewritten\n"
            "4. SEO issues found and fixed\n"
            "5. Number of revision passes performed\n"
            "6. Confirm the final draft is ready for publication"
        ),
        expected_output=(
            "QA report confirming: pass/fail status, issues found per category "
            "(fact-check, plagiarism, SEO), revision count, and confirmation that "
            "the final polished draft is ready. Include the final_draft JSON field "
            "from the tool output."
        ),
        agent=agent,
    )


# ── Output parser ─────────────────────────────────────────────────────────────

def parse_editor_output(raw_output: str, fallback_draft: str) -> tuple[str, bool]:
    """Extract final_draft and qa_passed from editor agent output."""
    import re
    json_match = re.search(r'\{["\s]*"final_draft"[\s\S]*?\}(?=\s*$|\s*```)', raw_output)
    if not json_match:
        json_match = re.search(r'\{[\s\S]*"final_draft"[\s\S]*\}', raw_output)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            return data.get("final_draft", fallback_draft), data.get("qa_passed", True)
        except Exception:
            pass
    return fallback_draft, True
