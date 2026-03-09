"""
Readability Tool — scores content using textstat metrics.

Provides:
  - Flesch Reading Ease  (target: 60-70 for general SEO content)
  - Flesch-Kincaid Grade Level
  - Gunning Fog Index
  - Actionable feedback string

Target ranges for SEO blog content:
  Flesch Reading Ease : 60-70   (plain English, accessible)
  FK Grade Level      : 7-9     (middle-school level)
  Gunning Fog         : < 12
"""
from __future__ import annotations

import textstat
from langchain_core.tools import tool


def _reading_ease_label(score: float) -> str:
    if score >= 90:
        return "Very Easy"
    if score >= 80:
        return "Easy"
    if score >= 70:
        return "Fairly Easy"
    if score >= 60:
        return "Standard"
    if score >= 50:
        return "Fairly Difficult"
    if score >= 30:
        return "Difficult"
    return "Very Confusing"


def _build_feedback(ease: float, grade: float, fog: float) -> list[str]:
    feedback: list[str] = []
    if ease < 60:
        feedback.append(
            f"Reading ease is {ease:.1f} (target 60-70). Shorten sentences and replace "
            "complex words with simpler alternatives."
        )
    if ease > 80:
        feedback.append(
            f"Reading ease is {ease:.1f} — content may be too simple. Add more depth and "
            "specific terminology where appropriate."
        )
    if grade > 9:
        feedback.append(
            f"Grade level is {grade:.1f} (target 7-9). Break long paragraphs into shorter ones "
            "and avoid multi-clause sentences."
        )
    if fog > 12:
        feedback.append(
            f"Gunning Fog index is {fog:.1f} (target < 12). Reduce polysyllabic words and "
            "passive voice constructions."
        )
    if not feedback:
        feedback.append("Readability is within target range. No changes needed.")
    return feedback


@tool
def score_readability(text: str) -> dict:
    """
    Score the readability of a block of text. Returns Flesch Reading Ease,
    Flesch-Kincaid Grade Level, Gunning Fog index, a human-readable label,
    and actionable improvement suggestions.

    Args:
        text: The content to score (plain text or Markdown).

    Returns:
        dict with keys: flesch_reading_ease (float), flesch_kincaid_grade (float),
        gunning_fog (float), label (str), feedback (list[str]), passes_target (bool)
    """
    # Strip basic Markdown symbols to avoid skewing word/syllable counts
    clean = (
        text.replace("#", "")
            .replace("*", "")
            .replace("`", "")
            .replace(">", "")
            .replace("_", "")
    )

    ease: float = textstat.flesch_reading_ease(clean)
    grade: float = textstat.flesch_kincaid_grade(clean)
    fog: float = textstat.gunning_fog(clean)

    return {
        "flesch_reading_ease": round(ease, 2),
        "flesch_kincaid_grade": round(grade, 2),
        "gunning_fog": round(fog, 2),
        "label": _reading_ease_label(ease),
        "feedback": _build_feedback(ease, grade, fog),
        "passes_target": 60 <= ease <= 75 and grade <= 10,
    }


@tool
def score_section_readability(text: str, section_heading: str = "") -> dict:
    """
    Score the readability of a single blog section. Useful for checking
    individual sections during the writing loop.

    Args:
        text: The section content to score.
        section_heading: Optional heading label for context in feedback.

    Returns:
        Same structure as score_readability, with section_heading included.
    """
    result = score_readability.invoke({"text": text})
    result["section_heading"] = section_heading
    return result


READABILITY_TOOLS = [score_readability, score_section_readability]
