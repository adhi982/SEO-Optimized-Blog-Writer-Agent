"""
Markdown Tool — assembles the final blog post as a Markdown file.

Responsibilities:
  1. Generate a URL-safe slug from the blog title
  2. Build YAML frontmatter (title, description, keywords, date, schema)
  3. Generate a Table of Contents from headings
  4. Assemble all sections into a single Markdown document
  5. Write the file to the output/ directory
  6. Return the file path
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

import frontmatter  # python-frontmatter
from langchain_core.tools import tool

from config.settings import settings
from models.schemas import BlogPost, BlogSection


# ── Slug ─────────────────────────────────────────────────────────────────────

def make_slug(title: str) -> str:
    """Convert a title into a URL-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)       # remove special chars
    slug = re.sub(r"[\s_]+", "-", slug)         # spaces → hyphens
    slug = re.sub(r"-{2,}", "-", slug)          # collapse multiple hyphens
    slug = slug.strip("-")
    return slug[:80]  # max 80 chars


# ── Table of Contents ─────────────────────────────────────────────────────────

def generate_toc(sections: list[BlogSection]) -> str:
    """Generate a Markdown Table of Contents from section headings."""
    lines = ["## Table of Contents\n"]
    for idx, section in enumerate(sections, start=1):
        heading = section.heading.strip("# ").strip()
        anchor = make_slug(heading)
        lines.append(f"{idx}. [{heading}](#{anchor})")
    return "\n".join(lines)


# ── Frontmatter ───────────────────────────────────────────────────────────────

def build_frontmatter_metadata(post: BlogPost) -> dict:
    return {
        "title": post.title,
        "description": post.meta_description,
        "slug": post.slug,
        "keywords": [post.primary_keyword] + post.secondary_keywords,
        "date": post.created_at.strftime("%Y-%m-%d"),
        "author": "SEO Blog Agent",
        "word_count": post.word_count,
        "readability_score": post.seo_report.readability_score if post.seo_report else None,
        "seo_score": post.seo_report.seo_score if post.seo_report else None,
        "schema": post.schema_markup,
    }


# ── Section → Markdown ────────────────────────────────────────────────────────

def section_to_markdown(section: BlogSection) -> str:
    """Convert a BlogSection into Markdown text."""
    parts: list[str] = []

    # Heading — normalise to ## if not already prefixed
    heading = section.heading.strip()
    if not heading.startswith("#"):
        heading = f"## {heading}"
    parts.append(heading)
    parts.append("")

    # Body content
    parts.append(section.content.strip())
    parts.append("")

    # Citations
    if section.citations:
        parts.append("**Sources:**")
        for citation in section.citations:
            parts.append(f"- {citation}")
        parts.append("")

    # Image suggestions (as HTML comments for editors to act on)
    if section.image_suggestions:
        for suggestion in section.image_suggestions:
            parts.append(f"<!-- IMAGE: {suggestion} -->")
        parts.append("")

    return "\n".join(parts)


# ── Main assembler ────────────────────────────────────────────────────────────

@tool
def assemble_and_save_blog(blog_post_json: str) -> dict:
    """
    Assemble a complete BlogPost into a Markdown file with YAML frontmatter
    and Table of Contents, then save it to the output directory.

    Args:
        blog_post_json: JSON string of a serialised BlogPost object.

    Returns:
        dict with keys: file_path (str), slug (str), word_count (int)
    """
    data = json.loads(blog_post_json)
    post = BlogPost(**data)

    # ── Build Markdown body ───────────────────────────────────────────────────
    lines: list[str] = []

    # H1
    lines.append(f"# {post.title}")
    lines.append("")

    # Meta description as intro callout
    lines.append(f"> {post.meta_description}")
    lines.append("")

    # Table of Contents
    lines.append(generate_toc(post.sections))
    lines.append("")
    lines.append("---")
    lines.append("")

    # Sections
    for section in post.sections:
        lines.append(section_to_markdown(section))

    # JSON-LD schema block at the bottom (HTML comment — visible to devs)
    if post.schema_markup:
        schema_json = json.dumps(post.schema_markup, indent=2)
        lines.append("<!-- JSON-LD SCHEMA")
        lines.append(schema_json)
        lines.append("-->")

    body = "\n".join(lines)

    # ── Front-matter ─────────────────────────────────────────────────────────
    metadata = build_frontmatter_metadata(post)
    fm_post = frontmatter.Post(body, **metadata)
    md_content = frontmatter.dumps(fm_post)

    # ── Write to output/ ─────────────────────────────────────────────────────
    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    date_prefix = post.created_at.strftime("%Y-%m-%d")
    filename = f"{date_prefix}-{post.slug}.md"
    file_path = output_dir / filename

    file_path.write_text(md_content, encoding="utf-8")

    return {
        "file_path": str(file_path),
        "slug": post.slug,
        "word_count": post.word_count,
    }


# ── Convenience (used outside LangChain tool context) ────────────────────────

def save_blog_post(post: BlogPost) -> str:
    """Save a BlogPost object directly (not via LangChain tool invocation)."""
    result = assemble_and_save_blog.invoke({"blog_post_json": post.model_dump_json()})
    return result["file_path"]


MARKDOWN_TOOLS = [assemble_and_save_blog]
