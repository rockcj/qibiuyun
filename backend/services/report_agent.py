"""LLM 报告生成 Agent — 使用 DeepSeek V4 Pro 生成带证据的场景报告和时间轴事件。

LLM 失败时返回 None，由调用方降级到 report_service 规则引擎。
"""

import json
import re
from typing import Any, Optional

import httpx

from config import settings


def _get_api_key() -> str:
    return settings.deepseek_api_key or settings.llm_api_key


# ---------------------------------------------------------------------------
# System prompt — 指导 LLM 如何评分和输出
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_TEMPLATE = """You are an expert English speaking coach and interview assessor for OfferGPT, an AI-powered English oral practice platform.

Your task: analyze a completed training session and produce a structured assessment report.

## Scene Context
- Scene: {scene_display}
- Rubric dimensions: {rubric_str}
- Scene type rules: {scene_rules}

## Scoring Guidelines
1. Assign a scene total score (0-100) based on the overall conversation quality.
2. For EACH rubric dimension, assign a score (0-100) AND provide concrete evidence from the session.
3. Evidence must reference specific turns, quotes, or statistics — never generic.
4. Interview scene: Offer Score is the primary score name.
5. Restaurant/Meeting scenes: use scene-specific score names (e.g., "Dining Score", "Meeting Score").
6. For interview STAR dimension: identify if answers follow Situation→Task→Action→Result structure.
7. For interview Logic dimension: evaluate reasoning clarity and structure.

## Timeline Events
Identify up to 5 key moments in the conversation:
- "star_missing": Where an answer lacked STAR elements (Situation, Task, Action, Result)
- "highlight_answer": A particularly strong or well-structured answer
- Estimate startMs/endMs based on turn order (roughly 30-45 seconds per turn)

## Output Format
Return ONLY valid JSON — no markdown fences, no extra text:
{{
  "sceneScore": 78,
  "scoreName": "Offer Score",
  "dimensionScores": {{
    "english": {{"score": 75, "evidence": "Grammar errors in rounds 2 and 4 affected clarity; e.g., subject-verb agreement issue in turn_002"}},
    "logic": {{"score": 80, "evidence": "Logical flow was good in most answers but round 3 lacked clear structure"}}
  }},
  "highlights": ["Strong technical vocabulary in round 3", "Good recovery after correction in round 4"],
  "improvements": ["Reduce filler words — try brief pauses instead", "Include quantified results in STAR answers"],
  "finalRecommendation": "Solid performance. Focus on STAR completeness and reducing fillers for higher scores.",
  "timelineEvents": [
    {{
      "turnId": "turn_002",
      "eventType": "star_missing",
      "severity": "medium",
      "title": "STAR: Missing Situation context",
      "description": "The answer jumps directly to actions without establishing the background context",
      "startMs": 45000,
      "endMs": 65000,
      "transcriptSnippet": "I led the migration and we moved everything...",
      "suggestion": "Start with: 'At my previous company, we were facing scalability issues with...'"
    }}
  ]
}}"""


def _scene_rules(scene: str) -> str:
    """返回场景专属评分规则。"""
    if scene == "interview":
        return (
            "This is a JOB INTERVIEW simulation. "
            "Focus heavily on STAR methodology (Situation, Task, Action, Result). "
            "Evaluate if answers demonstrate quantified impact, technical depth, and structured communication. "
            "The primary score name is 'Offer Score'."
        )
    elif scene == "restaurant":
        return (
            "This is a RESTAURANT DINING simulation. "
            "Focus on politeness, functional phrases (ordering, requests, complaints), and task completion. "
            "Evaluate if the user communicates their needs clearly and handles the interaction smoothly. "
            "The primary score name is 'Dining Score'."
        )
    elif scene == "meeting":
        return (
            "This is a BUSINESS MEETING simulation. "
            "Focus on professional communication, meeting control, clarity of proposals, and functional business phrases. "
            "Evaluate if the user contributes effectively, handles questions, and maintains professional tone. "
            "The primary score name is 'Meeting Score'."
        )
    return "General English conversation assessment."


def _scene_display(scene: str) -> str:
    mapping = {"interview": "Job Interview", "restaurant": "Restaurant Dining", "meeting": "Business Meeting"}
    return mapping.get(scene, scene.title())


def _score_name(scene: str) -> str:
    mapping = {"interview": "Offer Score", "restaurant": "Dining Score", "meeting": "Meeting Score"}
    return mapping.get(scene, "Scene Score")


class ReportAgent:
    """使用 LLM 生成场景报告。"""

    async def generate(
        self,
        session_id: str,
        scene: str,
        scene_config: dict,
        analysis_summary: dict,
        conversation_history: list[dict],
        existing_timeline_events: list[dict],
    ) -> Optional[dict]:
        """调用 LLM 生成报告 JSON，失败返回 None。"""
        api_key = _get_api_key()
        if not api_key:
            print("[ReportAgent] No API key configured")
            return None

        rubric = scene_config.get("rubric", [])
        system_prompt = self._build_system_prompt(scene, rubric)
        user_prompt = self._build_user_prompt(
            session_id, scene, rubric, analysis_summary,
            conversation_history, existing_timeline_events,
        )

        try:
            url = f"{settings.llm_api_base_url.rstrip('/')}/v1/messages"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": settings.llm_report_model,
                "max_tokens": 4096,
                "temperature": 0.3,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    print(f"[ReportAgent] LLM error {resp.status_code}: {resp.text[:200]}")
                    return None

                data = resp.json()
                content = ""
                for block in data.get("content", []):
                    if block.get("type") == "text":
                        content += block.get("text", "")
                if not content:
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                if not content:
                    print("[ReportAgent] Empty LLM response")
                    return None

                json_match = re.search(r"\{[\s\S]*\}", content)
                if not json_match:
                    print(f"[ReportAgent] No JSON found in: {content[:200]}")
                    return None

                result = json.loads(json_match.group())
                validated = self._validate_and_clean(result, rubric, analysis_summary)
                return validated

        except json.JSONDecodeError as exc:
            print(f"[ReportAgent] JSON parse error: {exc}")
            return None
        except Exception as exc:
            print(f"[ReportAgent] Exception: {exc}")
            return None

    def _build_system_prompt(self, scene: str, rubric: list[str]) -> str:
        rubric_str = ", ".join(rubric)
        rules = _scene_rules(scene)
        display = _scene_display(scene)
        return SYSTEM_PROMPT_TEMPLATE.format(
            scene_display=display,
            rubric_str=rubric_str,
            scene_rules=rules,
        )

    def _build_user_prompt(
        self,
        session_id: str,
        scene: str,
        rubric: list[str],
        analysis_summary: dict,
        conversation_history: list[dict],
        existing_timeline_events: list[dict],
    ) -> str:
        """组装 User Prompt，包含所有会话数据。"""
        parts = []

        parts.append(f"## Session: {session_id[:8]}...")
        parts.append(f"## Scene: {_scene_display(scene)}")
        parts.append(f"## Dimensions to score: {', '.join(rubric)}")
        parts.append("")

        # --- 分析统计数据 ---
        corrections = analysis_summary.get("corrections", [])
        filler_counts = analysis_summary.get("fillerCounts", {})
        pronunciation = analysis_summary.get("pronunciation", [])

        serious_count = sum(1 for c in corrections if c.get("severity") == "serious")
        minor_count = sum(1 for c in corrections if c.get("severity") in ("minor", "medium"))
        total_fillers = sum(filler_counts.values())

        parts.append("## Analysis Statistics")
        parts.append(f"- Total turns with audio: {len(pronunciation)}")
        if pronunciation:
            avg_wpm = sum(p.get("wordsPerMinute", 0) for p in pronunciation) / len(pronunciation)
            total_pauses = sum(p.get("pauseCount", 0) for p in pronunciation)
            parts.append(f"- Average WPM: {avg_wpm:.0f}")
            parts.append(f"- Total pauses: {total_pauses}")
        parts.append(f"- Grammar corrections: {len(corrections)} ({serious_count} serious, {minor_count} minor)")
        parts.append(f"- Total filler words: {total_fillers}")
        if filler_counts:
            filler_detail = ", ".join(f"{k}:{v}" for k, v in sorted(filler_counts.items(), key=lambda x: -x[1]))
            parts.append(f"- Filler breakdown: {filler_detail}")
        parts.append("")

        # --- 语法纠正详情 ---
        if corrections:
            parts.append("## Grammar Corrections (all turns)")
            for c in corrections[:20]:  # limit to avoid token overflow
                parts.append(
                    f"- [{c.get('turnId', '?')}] {c.get('severity', '?')}: "
                    f"'{c.get('original', '')}' → '{c.get('corrected', '')}'"
                )
            parts.append("")

        # --- 对话历史 ---
        if conversation_history:
            parts.append("## Conversation History")
            for turn in conversation_history[-10:]:  # last 10 turns
                role = turn.get("role", "?")
                content = turn.get("content", "")
                turn_id = turn.get("turnId", "")
                label = f"[{turn_id}]" if turn_id else ""
                parts.append(f"- {role.upper()} {label}: {content[:300]}")
            parts.append("")

        # --- 已有时间轴事件 ---
        if existing_timeline_events:
            parts.append("## Existing Timeline Events (from real-time analysis)")
            for e in existing_timeline_events[:10]:
                parts.append(
                    f"- [{e.get('eventType', '?')}] {e.get('title', '')} "
                    f"(@{e.get('startMs', 0)}-{e.get('endMs', 0)}ms)"
                )
            parts.append("")

        parts.append("## Instructions")
        parts.append(f"Generate the report JSON with all {len(rubric)} rubric dimensions scored.")
        parts.append("Each dimension MUST have 'score' (0-100) and 'evidence' (specific quote/reference).")
        parts.append("Identify at least 2 timeline events (star_missing or highlight_answer for interview; scene-appropriate for others).")
        parts.append("Return ONLY the JSON object — no markdown, no extra text.")

        return "\n".join(parts)

    def _validate_and_clean(
        self, result: dict, rubric: list[str], summary: dict
    ) -> dict:
        """校验 LLM 输出，补全缺失字段。"""
        # sceneScore
        scene_score = result.get("sceneScore", 70)
        if not isinstance(scene_score, (int, float)) or scene_score < 0 or scene_score > 100:
            scene_score = 70

        # scoreName
        score_name = result.get("scoreName", "Offer Score")
        if not isinstance(score_name, str) or not score_name.strip():
            score_name = "Offer Score"

        # dimensionScores — ensure all rubric dimensions exist
        dim_scores = result.get("dimensionScores", {})
        if not isinstance(dim_scores, dict):
            dim_scores = {}

        cleaned_dims = {}
        for dim in rubric:
            info = dim_scores.get(dim, {})
            if isinstance(info, (int, float)):
                cleaned_dims[dim] = {"score": int(max(0, min(100, info))), "evidence": ""}
            elif isinstance(info, dict):
                score = info.get("score", 60)
                if not isinstance(score, (int, float)):
                    score = 60
                cleaned_dims[dim] = {
                    "score": int(max(0, min(100, score))),
                    "evidence": str(info.get("evidence", "")),
                }
            else:
                cleaned_dims[dim] = {"score": 60, "evidence": ""}

        # highlights / improvements
        highlights = result.get("highlights", [])
        if not isinstance(highlights, list):
            highlights = []
        improvements = result.get("improvements", [])
        if not isinstance(improvements, list):
            improvements = []

        # Ensure at least 2 improvements
        corrections = summary.get("corrections", [])
        if len(improvements) < 2:
            if corrections:
                improvements.append("Review grammar correction records and practice the corrected sentences")
            improvements.append("Continue practicing with more challenging scenarios to build confidence")

        # finalRecommendation
        final_rec = result.get("finalRecommendation", "")
        if not final_rec or not isinstance(final_rec, str):
            total_fillers = sum(summary.get("fillerCounts", {}).values())
            if scene_score >= 85:
                final_rec = "Excellent performance! Your English communication is strong."
            elif scene_score >= 70:
                final_rec = "Good effort. With targeted practice on weaker areas, you can reach the next level."
            else:
                final_rec = "Keep practicing. Focus on grammar accuracy and reducing filler words."

        # timelineEvents
        timeline_events = result.get("timelineEvents", [])
        if not isinstance(timeline_events, list):
            timeline_events = []
        cleaned_timeline = []
        for event in timeline_events:
            if not isinstance(event, dict):
                continue
            cleaned_timeline.append({
                "turnId": str(event.get("turnId", "")),
                "eventType": str(event.get("eventType", "llm_detected")),
                "severity": str(event.get("severity", "medium")),
                "title": str(event.get("title", "Event")),
                "description": str(event.get("description", "")),
                "startMs": int(event.get("startMs", 0)),
                "endMs": int(event.get("endMs", 0)),
                "transcriptSnippet": str(event.get("transcriptSnippet", "")),
                "suggestion": str(event.get("suggestion", "")),
                "evidence": event.get("evidence"),
                "displayPriority": int(event.get("displayPriority", 0)),
            })

        return {
            "sceneScore": int(scene_score),
            "scoreName": score_name,
            "dimensionScores": cleaned_dims,
            "highlights": highlights[:5],
            "improvements": improvements[:5],
            "finalRecommendation": final_rec,
            "timelineEvents": cleaned_timeline[:5],
        }


# 单例
report_agent = ReportAgent()
