#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
agents_demo.py
Tiny multi-agent demo using a local LLM via Ollama.
Flow: Planner -> Reviewer -> Finalizer
Output: strict JSON with exactly 3 topical tags and a <=25-word summary.

Requirements:
- Ollama running locally (default: http://localhost:11434)
- Model: smollm:1.7b   (pull it with: `ollama pull smollm:1.7b`)
- Python 3.11/3.12, packages: ollama, pydantic

Usage examples:
  python agents_demo.py --title "Lamport Clocks" --content-file blog.txt
  python agents_demo.py --title "Intro to Vector Databases" --content "We explain..."
  python agents_demo.py --model smollm:1.7b --title "..." --content "..."
"""

from __future__ import annotations
import argparse
import json
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import ollama
from pydantic import BaseModel, ValidationError, field_validator

# ----------------------------- Utilities -----------------------------

def extract_json(text: str) -> Dict[str, Any]:
    # 1) Drop entire fenced code blocks
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

    # 2) Fast path: try the whole thing as JSON
    try:
        return json.loads(text.strip())
    except Exception:
        pass

    # 3) Scan for balanced {...} candidates and try each
    candidates = []
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            if depth:
                depth -= 1
                if depth == 0 and start is not None:
                    candidates.append(text[start:i+1])

    for c in candidates:
        try:
            return json.loads(c)
        except Exception:
            continue

    raise ValueError("No JSON object found in model output.")

def word_count(s: str) -> int:
    return len([w for w in re.findall(r"\b[\w'-]+\b", s)])

def call_ollama(
    model: str,
    system_prompt: Optional[str],
    user_prompt: str,
    temperature: float = 0.1,
) -> str:
    """
    Call Ollama chat endpoint with (optional) system + user messages.
    Returns model's text string.
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    
    
    resp = ollama.chat(
    model=model,
    messages=messages,
    options={"temperature": temperature, "format": "json"} 
)
    return resp["message"]["content"]

# ----------------------------- Schemas -------------------------------

class PlannerOut(BaseModel):
    proposed_tags: List[str]
    draft_summary: str

    @field_validator("proposed_tags")
    @classmethod
    def nonempty_tags(cls, v):
        if not v or not all(isinstance(x, str) and x.strip() for x in v):
            raise ValueError("proposed_tags must be a non-empty list of non-empty strings.")
        return v

class ReviewerOut(BaseModel):
    approved_tags: List[str]
    edited_summary: str

    @field_validator("approved_tags")
    @classmethod
    def exactly_three(cls, v):
        if len(v) != 3:
            raise ValueError("approved_tags must contain exactly 3 items.")
        if not all(isinstance(x, str) and x.strip() for x in v):
            raise ValueError("approved_tags must be non-empty strings.")
        return v

# Final JSON that must be printed
class PublishOut(BaseModel):
    tags: List[str]
    summary: str

    @field_validator("tags")
    @classmethod
    def exactly_three_final(cls, v):
        if len(v) != 3:
            raise ValueError("tags must contain exactly 3 items.")
        if not all(isinstance(x, str) and x.strip() for x in v):
            raise ValueError("tags must be non-empty strings.")
        return v

    @field_validator("summary")
    @classmethod
    def limit_words(cls, v):
        if word_count(v) > 25:
            raise ValueError("summary must be <= 25 words.")
        return v

# ------------------------------ Prompts ------------------------------

PLANNER_SYS = """You are a precise Planner agent.
Given a blog title and content, produce JSON with:
- "proposed_tags": 3-6 short topical tags (1-3 words each, no hashtags, distinct),
- "draft_summary": 1 sentence ideally <= 25 words summarizing the post.
Return ONLY a single JSON object.
The first character MUST be '{' and the last character MUST be '}'.
Do not include markdown, comments, or code.
If unsure, return {}.
If you do not know, return an empty JSON object {}.
"""

PLANNER_USER_TMPL = """Title: {title}

Content:
{content}

Return JSON with keys: "proposed_tags", "draft_summary".
"""

REVIEWER_SYS = """You are a careful Reviewer.
Check the Planner JSON and produce STRICT JSON with:
- "approved_tags": exactly 3 distinct topical tags (1-3 words),
- "edited_summary": single sentence <= 25 words.
If the Planner exceeded limits or missed topics, FIX them.
Return ONLY JSON.
"""

REVIEWER_USER_TMPL = """Title: {title}

Original content (for context):
{content}

Planner JSON:
{planner_json}

Now return JSON with keys: "approved_tags", "edited_summary".
"""

FINALIZER_SYS = """You are the Finalizer.
Merge prior steps and output STRICT JSON:
{
  "tags": ["t1","t2","t3"],
  "summary": "<=25 words"
}
Rules:
- Exactly 3 tags (strings).
- Summary MUST be <= 25 words.
- NO extra keys, NO comments, NO code fences.
- If needed, shorten the summary while preserving meaning.
"""

FINALIZER_USER_TMPL = """Title: {title}

Content (for grounding):
{content}

Planner JSON:
{planner_json}

Reviewer JSON:
{reviewer_json}

Return ONLY the final JSON with keys: "tags", "summary".
"""

# ------------------------------ Pipeline -----------------------------

def run_pipeline(model: str, title: str, content: str) -> Tuple[PlannerOut, ReviewerOut, PublishOut]:
    # --- Planner ---
    planner_raw = call_ollama(
        model=model,
        system_prompt=PLANNER_SYS,
        user_prompt=PLANNER_USER_TMPL.format(title=title, content=content),
        temperature=0.2,
    )
    print("=== Planner output (raw) ===")
    print(planner_raw.strip(), flush=True)

    try:
        planner_json = extract_json(planner_raw)
        planner = PlannerOut(**planner_json)
    except Exception as e:
        print("\n[Planner JSON parse/validation failed]", e, file=sys.stderr)
        raise

    # --- Reviewer ---
    reviewer_raw = call_ollama(
        model=model,
        system_prompt=REVIEWER_SYS,
        user_prompt=REVIEWER_USER_TMPL.format(
            title=title, content=content, planner_json=json.dumps(planner.model_dump(), ensure_ascii=False)
        ),
        temperature=0.2,
    )
    print("\n=== Reviewer output (raw) ===")
    print(reviewer_raw.strip(), flush=True)

    try:
        reviewer_json = extract_json(reviewer_raw)
        reviewer = ReviewerOut(**reviewer_json)
    except Exception as e:
        print("\n[Reviewer JSON parse/validation failed]", e, file=sys.stderr)
        raise

    # --- Finalizer ---
    final_raw = call_ollama(
        model=model,
        system_prompt=FINALIZER_SYS,
        user_prompt=FINALIZER_USER_TMPL.format(
            title=title,
            content=content,
            planner_json=json.dumps(planner.model_dump(), ensure_ascii=False),
            reviewer_json=json.dumps(reviewer.model_dump(), ensure_ascii=False),
        ),
        temperature=0.1,
    )
    print("\n=== Finalized Output (raw) ===")
    print(final_raw.strip(), flush=True)

    # Validate final JSON strictly; if the model violated rules, fix here deterministically
    try:
        final_json = extract_json(final_raw)
    except Exception:
        # Deterministic fallback: build from reviewer
        final_json = {"tags": reviewer.approved_tags, "summary": reviewer.edited_summary}

    # Enforce exactly-3 tags and <=25 words (deterministic guardrails)
    tags = final_json.get("tags") or reviewer.approved_tags
    if not isinstance(tags, list):
        tags = [str(tags)]
    # de-dup & keep first 3
    seen = set()
    uniq = []
    for t in tags:
        t = str(t).strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            uniq.append(t)
    if len(uniq) < 3:
        # top up from reviewer-approved as needed
        for t in reviewer.approved_tags:
            if t.lower() not in seen:
                uniq.append(t)
                seen.add(t.lower())
            if len(uniq) == 3:
                break
    tags = uniq[:3]

    summary = str(final_json.get("summary") or reviewer.edited_summary).strip()
    # hard-limit summary to <=25 words (deterministic)
    tokens = re.findall(r"\b[\w'-]+\b", summary)
    if len(tokens) > 25:
        # naive compression: keep first 25 words and strip trailing punctuation
        summary = " ".join(tokens[:25]).rstrip(" ,;:—-")

    try:
        publish = PublishOut(tags=tags, summary=summary)
    except ValidationError as ve:
        # As a last resort, force minimal valid structure (should rarely happen)
        fallback = PublishOut(
            tags=reviewer.approved_tags[:3] if reviewer and reviewer.approved_tags else tags[:3],
            summary=reviewer.edited_summary if reviewer and word_count(reviewer.edited_summary) <= 25 else " ".join(re.findall(r"\b[\w'-]+\b", summary)[:25])
        )
        publish = fallback

    print("\n=== Publish output (strict JSON) ===")
    print(json.dumps(publish.model_dump(), ensure_ascii=False))
    return planner, reviewer, publish

# ------------------------------ CLI ---------------------------------

def main():
    ap = argparse.ArgumentParser(description="Tiny agentic pipeline using Ollama.")
    ap.add_argument("--model", default="smollm:1.7b", help="Ollama model name, e.g., smollm:1.7b")
    ap.add_argument("--title", required=True, help="Blog post title")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--content", help="Raw blog content text")
    g.add_argument("--content-file", help="Path to a text file with blog content (UTF-8)")
    args = ap.parse_args()

    if args.content:
        content = args.content
    else:
        with open(args.content_file, "r", encoding="utf-8") as f:
            content = f.read()

    run_pipeline(model=args.model, title=args.title, content=content)


if __name__ == "__main__":
    main()
