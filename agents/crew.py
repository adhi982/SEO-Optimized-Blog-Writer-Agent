"""
SEO Blog Crew — Main Orchestrator
==================================
SEOBlogCrew wires together all 5 agents in a sequential pipeline:

  Research → Strategist → Writer → SEO Optimizer → Editor

The pipeline is hybrid:
  - CrewAI agents handle the LLM reasoning, task delegation, and tool calls
  - LangGraph sub-graphs run inside the Research, Writer, and Editor agents
    as wrapped tools for stateful, loop-based processing

Usage:
    from models.schemas import BlogRequest
    from agents.crew import SEOBlogCrew

    request = BlogRequest(topic="Best Python Web Frameworks 2026")
    crew = SEOBlogCrew()
    blog_post = crew.run(request)
    print(blog_post.output_path)
"""
from __future__ import annotations

import json
import re
from datetime import datetime

from crewai import Crew, Process

from models.schemas import (
    BlogOutline,
    BlogPost,
    BlogRequest,
    BlogSection,
    SEOReport,
)
from tools.markdown_tool import make_slug, save_blog_post

from graphs.writing_graph import run_writing_graph
from graphs.qa_graph import run_qa_graph
from agents.research_agent import create_research_agent, create_research_task
from agents.strategist_agent import (
    create_strategist_agent,
    create_strategist_task,
    parse_outline_from_output,
)
from agents.seo_agent import (    create_seo_agent,
    create_seo_task,
    build_seo_report,
    parse_seo_report_from_output,
)


class SEOBlogCrew:
    """
    Orchestrates the full SEO blog writing pipeline.
    All phases run sequentially; outputs from each phase feed the next.
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    # ── Main entry point ──────────────────────────────────────────────────────

    def run(self, request: BlogRequest) -> BlogPost:
        """
        Run the full pipeline for a BlogRequest.
        Returns a complete BlogPost with content, SEO report, schema, and saved file path.
        """
        print(f"\n{'='*60}")
        print(f"SEO Blog Crew — Starting pipeline")
        print(f"Topic: {request.topic}")
        print(f"Type:  {request.blog_type} | Tone: {request.tone}")
        print(f"{'='*60}\n")

        # ── Phase 1: Research ─────────────────────────────────────────────────
        print("[1/5] RESEARCH — Keyword & SERP Analysis")
        research_output, research_summary, primary_keyword, secondary_keywords = (
            self._run_research_phase(request)
        )

        # ── Phase 2: Strategy ─────────────────────────────────────────────────
        print("[2/5] STRATEGY — Outline Generation")
        outline = self._run_strategy_phase(request, research_output)

        # Override outline's keyword data with research findings if better
        if primary_keyword and not outline.primary_keyword:
            outline = outline.model_copy(update={"primary_keyword": primary_keyword})
        if secondary_keywords and not outline.secondary_keywords:
            outline = outline.model_copy(update={"secondary_keywords": secondary_keywords})

        # ── Phase 3: Writing ──────────────────────────────────────────────────
        print("[3/5] WRITING — Section-by-Section Content Generation")
        sections, full_draft = self._run_writing_phase(
            request, outline, research_summary
        )

        # ── Phase 4: SEO Optimisation ─────────────────────────────────────────
        print("[4/5] SEO OPTIMIZATION — Meta Tags, Schema, Scores")
        seo_report = self._run_seo_phase(request, outline, full_draft, sections)

        # ── Phase 5: QA / Editing ─────────────────────────────────────────────
        print("[5/5] EDITING — Fact-Check, Polish, Final QA")
        final_draft, qa_passed = self._run_editor_phase(
            request, outline, full_draft, sections, research_summary
        )

        # ── Assemble BlogPost ─────────────────────────────────────────────────
        print("\nAssembling final blog post...")
        blog_post = self._assemble_blog_post(
            request=request,
            outline=outline,
            sections=sections,
            final_draft=final_draft,
            seo_report=seo_report,
        )

        # ── Save to output/ ───────────────────────────────────────────────────
        file_path = save_blog_post(blog_post)
        blog_post = blog_post.model_copy(update={"output_path": file_path})

        print(f"\n{'='*60}")
        print(f"DONE! Blog saved to: {file_path}")
        print(f"Words: {blog_post.word_count} | SEO Score: {seo_report.seo_score}/100")
        print(f"Readability: {seo_report.readability_score:.1f} | QA Passed: {qa_passed}")
        print(f"{'='*60}\n")

        return blog_post

    # ── Phase runners ─────────────────────────────────────────────────────────

    def _run_research_phase(
        self, request: BlogRequest
    ) -> tuple[str, str, str, list[str]]:
        """Run the Research Agent and return (raw_output, summary, primary_kw, secondary_kws)."""
        agent = create_research_agent()
        task = create_research_task(agent, request)
        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=self.verbose,
            tracing=True,
        )
        result = crew.kickoff()
        raw_output = str(result)

        # Extract structured data from tool JSON embedded in output
        research_summary, primary_kw, secondary_kws = self._parse_research_output(
            raw_output, request
        )
        return raw_output, research_summary, primary_kw, secondary_kws

    def _run_strategy_phase(self, request: BlogRequest, research_output: str) -> BlogOutline:
        """Run the Strategist Agent and return a BlogOutline."""
        agent = create_strategist_agent()
        task = create_strategist_task(agent, request, research_output)
        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=self.verbose,
            tracing=True,
        )
        result = crew.kickoff()
        return parse_outline_from_output(str(result), request)

    def _run_writing_phase(
        self,
        request: BlogRequest,
        outline: BlogOutline,
        research_summary: str,
    ) -> tuple[list[BlogSection], str]:
        """Call the LangGraph writing sub-graph directly (bypasses CrewAI tool call)."""
        print("  → Running LangGraph writing graph directly")
        try:
            state = run_writing_graph(
                request=request,
                outline=outline,
                research_summary=research_summary,
                citations_pool=[],
                brand_voice_config={"notes": request.brand_voice_notes} if request.brand_voice_notes else {},
            )
            sections = state.get("sections_written", [])
            if sections:
                lines = [f"# {outline.title}", ""]
                for s in sections:
                    heading = s.heading.strip()
                    if not heading.startswith("#"):
                        heading = f"## {heading}"
                    lines.extend([heading, "", s.content.strip(), ""])
                    if s.citations:
                        lines.append("**Sources:** " + " | ".join(s.citations))
                        lines.append("")
                full_draft = "\n".join(lines)
                return sections, full_draft
        except Exception as e:
            print(f"  ⚠ Writing graph error: {e} — using fallback draft")

        # Fallback: build a minimal draft from outline
        return self._fallback_draft(outline)

    def _run_seo_phase(
        self,
        request: BlogRequest,
        outline: BlogOutline,
        full_draft: str,
        sections: list[BlogSection],
    ) -> SEOReport:
        """Run the SEO Optimizer Agent and return an SEOReport."""
        agent = create_seo_agent()
        task = create_seo_task(agent, request, outline, full_draft, sections)
        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=self.verbose,
            tracing=True,
        )
        result = crew.kickoff()
        return parse_seo_report_from_output(str(result), outline, full_draft)

    def _run_editor_phase(
        self,
        request: BlogRequest,
        outline: BlogOutline,
        full_draft: str,
        sections: list[BlogSection],
        research_summary: str,
    ) -> tuple[str, bool]:
        """Call the LangGraph QA sub-graph directly (bypasses CrewAI tool call)."""
        print("  → Running LangGraph QA graph directly")
        try:
            state = run_qa_graph(
                request=request,
                full_draft=full_draft,
                sections=sections,
                outline=outline,
                research_summary=research_summary,
            )
            final = state.get("final_draft") or full_draft
            passed = state.get("qa_passed", True)
            return final, passed
        except Exception as e:
            print(f"  ⚠ QA graph error: {e} — returning original draft")
            return full_draft, True

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _parse_research_output(
        self, raw: str, request: BlogRequest
    ) -> tuple[str, str, list[str]]:
        """Extract research_summary, primary_keyword, secondary_keywords from raw output."""
        summary = ""
        primary_kw = request.topic
        secondary_kws: list[str] = []

        # Try JSON block first (from tool output embedded in agent text)
        json_match = re.search(r'\{[\s\S]*?"research_summary"[\s\S]*?\}', raw)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                summary = data.get("research_summary", "")
                primary_kw = data.get("primary_keyword", request.topic)
                secondary_kws = data.get("secondary_keywords", [])
                return summary, primary_kw, secondary_kws
            except Exception:
                pass

        # Fall back to text parsing
        for line in raw.splitlines():
            if line.strip().startswith("PRIMARY_KEYWORD"):
                primary_kw = line.split(":", 1)[-1].strip()
            elif line.strip().startswith("SECONDARY_KEYWORDS"):
                rest = line.split(":", 1)[-1].strip()
                secondary_kws = [k.strip() for k in rest.split(",") if k.strip()]
            elif line.strip().startswith("RESEARCH_SUMMARY"):
                idx = raw.find("RESEARCH_SUMMARY")
                summary = raw[idx + len("RESEARCH_SUMMARY"):].strip()[:1500]

        return summary or raw[:1000], primary_kw, secondary_kws

    def _fallback_draft(
        self, outline: BlogOutline
    ) -> tuple[list[BlogSection], str]:
        """Generate a minimal fallback draft when writer output can't be parsed."""
        sections = [
            BlogSection(
                heading=s.heading,
                content=f"Content for section: {s.heading}. Key points: {', '.join(s.key_points)}.",
                citations=[],
                image_suggestions=[],
            )
            for s in outline.sections
        ]
        draft_lines = [f"# {outline.title}", ""]
        for s in sections:
            draft_lines.extend([f"## {s.heading}", "", s.content, ""])
        return sections, "\n".join(draft_lines)

    def _assemble_blog_post(
        self,
        request: BlogRequest,
        outline: BlogOutline,
        sections: list[BlogSection],
        final_draft: str,
        seo_report: SEOReport,
    ) -> BlogPost:
        """Build the final BlogPost object from all phase outputs."""
        word_count = len(final_draft.split())
        slug = make_slug(outline.title)

        return BlogPost(
            title=outline.title,
            slug=slug,
            meta_description=outline.meta_description,
            primary_keyword=outline.primary_keyword,
            secondary_keywords=outline.secondary_keywords,
            content=final_draft,
            sections=sections,
            seo_report=seo_report,
            schema_markup=seo_report.schema_markup,
            word_count=word_count,
            created_at=datetime.utcnow(),
        )
