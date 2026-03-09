"""
Schema Markup Tool — generates JSON-LD structured data for SEO.

Supports three schema types:
  1. Article           — standard blog post / news article
  2. FAQPage           — FAQ section (if blog contains Q&A content)
  3. BreadcrumbList    — navigation breadcrumb trail

Output is a valid JSON-LD dict ready to embed in a <script> tag or
include in Markdown frontmatter.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from langchain_core.tools import tool


# ── Article Schema ────────────────────────────────────────────────────────────

@tool
def generate_article_schema(
    title: str,
    description: str,
    url: str = "",
    author_name: str = "SEO Blog Agent",
    date_published: str = "",
    date_modified: str = "",
    image_url: str = "",
) -> dict:
    """
    Generate a JSON-LD Article schema for a blog post.

    Args:
        title: The blog post title.
        description: The meta description (≤160 chars).
        url: The canonical URL of the post (optional).
        author_name: Author display name.
        date_published: ISO 8601 date string. Defaults to today.
        date_modified: ISO 8601 date string. Defaults to today.
        image_url: URL of the featured image (optional).

    Returns:
        dict: Valid JSON-LD Article schema.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    schema: dict = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title[:110],  # Google truncates at 110 chars
        "description": description[:160],
        "author": {
            "@type": "Person",
            "name": author_name,
        },
        "datePublished": date_published or today,
        "dateModified": date_modified or today,
    }
    if url:
        schema["url"] = url
    if image_url:
        schema["image"] = {
            "@type": "ImageObject",
            "url": image_url,
        }
    return schema


# ── FAQ Schema ────────────────────────────────────────────────────────────────

@tool
def generate_faq_schema(questions_and_answers: list[dict]) -> dict:
    """
    Generate a JSON-LD FAQPage schema from a list of Q&A pairs.
    Each item must have 'question' and 'answer' keys.

    Args:
        questions_and_answers: List of dicts, each with 'question' (str) and 'answer' (str).

    Returns:
        dict: Valid JSON-LD FAQPage schema.
    """
    entities = [
        {
            "@type": "Question",
            "name": item["question"],
            "acceptedAnswer": {
                "@type": "Answer",
                "text": item["answer"],
            },
        }
        for item in questions_and_answers
        if item.get("question") and item.get("answer")
    ]
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": entities,
    }


# ── Breadcrumb Schema ─────────────────────────────────────────────────────────

@tool
def generate_breadcrumb_schema(breadcrumbs: list[dict]) -> dict:
    """
    Generate a JSON-LD BreadcrumbList schema.
    Each item must have 'name' and 'url' keys.

    Args:
        breadcrumbs: Ordered list of dicts with 'name' (str) and 'url' (str).
                     Example: [{"name": "Home", "url": "https://example.com"},
                               {"name": "Blog", "url": "https://example.com/blog"},
                               {"name": "Article Title", "url": "https://example.com/blog/article"}]

    Returns:
        dict: Valid JSON-LD BreadcrumbList schema.
    """
    items = [
        {
            "@type": "ListItem",
            "position": idx + 1,
            "name": crumb["name"],
            "item": crumb["url"],
        }
        for idx, crumb in enumerate(breadcrumbs)
        if crumb.get("name") and crumb.get("url")
    ]
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": items,
    }


# ── Combined helper (used by SEO Optimizer agent) ─────────────────────────────

def build_full_schema(
    title: str,
    description: str,
    faq_items: Optional[list[dict]] = None,
    breadcrumbs: Optional[list[dict]] = None,
    url: str = "",
    author_name: str = "SEO Blog Agent",
    image_url: str = "",
) -> list[dict]:
    """
    Build a complete list of JSON-LD schemas for a blog post:
    always includes Article; optionally includes FAQPage and BreadcrumbList.

    Returns:
        list[dict]: List of JSON-LD schema dicts to embed in the page.
    """
    schemas: list[dict] = [
        generate_article_schema.invoke({
            "title": title,
            "description": description,
            "url": url,
            "author_name": author_name,
            "image_url": image_url,
        })
    ]
    if faq_items:
        schemas.append(generate_faq_schema.invoke({"questions_and_answers": faq_items}))
    if breadcrumbs:
        schemas.append(generate_breadcrumb_schema.invoke({"breadcrumbs": breadcrumbs}))
    return schemas


SCHEMA_TOOLS = [generate_article_schema, generate_faq_schema, generate_breadcrumb_schema]
