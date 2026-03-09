from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Input ─────────────────────────────────────────────────────────────────────

class BlogRequest(BaseModel):
    topic: str
    target_keywords: list[str] = Field(default_factory=list)
    blog_type: str = "long-form"
    tone: str = "professional"
    target_audience: str = "general audience"
    word_count: int = 1500
    language: str = "English"
    brand_voice_notes: Optional[str] = None
    site_url: str = ""
    author_name: str = "SEO Blog Agent"

    @property
    def word_count_range(self) -> tuple[int, int]:
        """Derived word count range for backward-compat with graphs/agents."""
        return (self.word_count, int(self.word_count * 1.4))


# ── Research ──────────────────────────────────────────────────────────────────

class KeywordData(BaseModel):
    keyword: str
    search_volume: Optional[int] = None
    difficulty: Optional[float] = None
    intent: Literal["informational", "transactional", "navigational", "commercial"] = "informational"
    related_keywords: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


class SERPResult(BaseModel):
    title: str
    url: str
    snippet: str
    position: int
    estimated_word_count: Optional[int] = None


# ── Outline / Strategy ────────────────────────────────────────────────────────

class OutlineSection(BaseModel):
    heading: str
    heading_level: Literal["h2", "h3"] = "h2"
    subheadings: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    target_keyword: Optional[str] = None


class BlogOutline(BaseModel):
    title: str
    meta_description: str = Field(max_length=160)
    primary_keyword: str
    secondary_keywords: list[str] = Field(default_factory=list)
    sections: list[OutlineSection]
    estimated_word_count: int
    internal_linking_targets: list[str] = Field(default_factory=list)


# ── Content ───────────────────────────────────────────────────────────────────

class BlogSection(BaseModel):
    heading: str
    content: str
    citations: list[str] = Field(default_factory=list)
    image_suggestions: list[str] = Field(default_factory=list)


# ── SEO Report ────────────────────────────────────────────────────────────────

class SEOReport(BaseModel):
    meta_title: str = Field(max_length=60)
    meta_description: str = Field(max_length=160)
    primary_keyword_density: float = Field(ge=0.0, le=100.0)
    readability_score: float
    readability_grade: str
    schema_markup: dict
    alt_text_suggestions: list[str] = Field(default_factory=list)
    internal_link_suggestions: list[str] = Field(default_factory=list)
    seo_score: int = Field(ge=0, le=100)
    suggestions: list[str] = Field(default_factory=list)


# ── Final Output ──────────────────────────────────────────────────────────────

class BlogPost(BaseModel):
    title: str
    slug: str
    meta_description: str
    primary_keyword: str
    secondary_keywords: list[str]
    content: str
    sections: list[BlogSection]
    seo_report: Optional[SEOReport] = None
    schema_markup: dict = Field(default_factory=dict)
    word_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    output_path: Optional[str] = None

    @property
    def full_content(self) -> str:
        """Alias used by the Streamlit UI."""
        return self.content
