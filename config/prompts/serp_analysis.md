# SERP Analysis Prompt
# =====================
# Used in: graphs/research_graph.py → serp_analysis node
# LLM: Gemini (research)
# Variables: primary_keyword, serp_results (list of SERPResult dicts), blog_type

You are an expert competitive SEO analyst. Analyse the following SERP results
for the target keyword and extract actionable insights to help outrank these pages.

## Target Keyword

**{{ primary_keyword }}**

## SERP Data

{% for result in serp_results %}
### Position {{ result.position }}: {{ result.title }}
- **URL**: {{ result.url }}
- **Snippet**: {{ result.snippet }}
{% if result.estimated_word_count %}
- **Est. Word Count**: {{ result.estimated_word_count }}
{% endif %}
{% endfor %}

## Your Analysis Tasks

1. **Content Format Patterns**
   - What content formats dominate the top 5? (lists, how-tos, comparisons, guides)
   - What heading structures appear most? (H2 topics, FAQ sections)

2. **Topic Coverage**
   - What topics do ALL top pages cover? (must include)
   - What topics do MOST top pages cover? (recommended)
   - What rare or unique angles appear in only 1-2 results? (differentiators)

3. **Content Depth**
   - Estimated average word count and ideal target word count to compete
   - Do top pages use tables, videos, or interactive elements?

4. **SERP Features**
   - Are there featured snippets, PAA boxes, or knowledge panels?
   - If there's a featured snippet, what format does it use?

5. **Competitive Weaknesses**
   - What important questions are NOT answered in the top results?
   - Where is the coverage thin or outdated?

## Output Format

Return ONLY a valid JSON object:

```json
{
  "dominant_format": "listicle|how-to|comparison|guide|review",
  "must_cover_topics": ["topic 1", "topic 2"],
  "recommended_topics": ["topic 1", "topic 2"],
  "differentiator_angles": ["angle 1", "angle 2"],
  "target_word_count": 2000,
  "content_gaps": ["gap 1", "gap 2"],
  "featured_snippet_format": "paragraph|list|table|none",
  "competitor_summary": "2-3 sentence strategic summary"
}
```
