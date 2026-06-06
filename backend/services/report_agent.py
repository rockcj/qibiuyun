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


SYSTEM_PROMPT_TEMPLATE = """You are an expert English speaking coach and assessor for OfferGPT.

## Scene: {scene_display}
## Rubric: {rubric_str}
## Rules: {scene_rules}

For each rubric dimension, assign score (0-100) AND concrete evidence from the session.

Return ONLY valid JSON:
{{
  "sceneScore": 78,
  "scoreName": "Offer Score",
  "dimensionScores": {{
    "english": {{"score": 75, "evidence": "specific quote or observation"}}
  }},
  "highlights": ["..."],
  "improvements": ["..."],
  "finalRecommendation": "...",
  "timelineEvents": [
    {{
      "turnId": "turn_002",
      "eventType": "star_missing",
      "severity": "medium",
      "title": "STAR: Missing Situation",
      "description": "...",
      "startMs": 45000,
      "endMs": 65000,
      "transcriptSnippet": "...",
      "suggestion": "..."
    }}
  ]
}}"""


def _scene_rules(scene: str) -> str:
    if scene == "interview":
        return "Job interview. Focus on STAR methodology, quantified impact, technical depth. Score name: 'Offer Score'."
    elif scene == "restaurant":
        return "Restaurant dining. Focus on politeness, functional phrases, task completion. Score name: 'Dining Score'."
    elif scene == "meeting":
        return "Business meeting. Focus on professional communication, meeting control, clarity. Score name: 'Meeting Score'."
    return "General English conversation."


def _scene_display(scene: str) -> str:
    mapping = {"interview": "Job Interview", "restaurant": "Restaurant Dining", "meeting": "Business Meeting"}
    return mapping.get(scene, scene.title())


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
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
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
                    print(f"[ReportAgent] LLM error {resp.status_code}")
                    return None
                data = resp.json()
                content = ""
                for block in data.get("content", []):
                    if block.get("type") == "text":
                        content += block.get("text", "")
                if not content:
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                json_match = re.search(r"\{[\s\S]*\}", content)
                if not json_match:
                    return None
                result = json.loads(json_match.group())
                return self._validate_and_clean(result, rubric, analysis_summary)

        except Exception as exc:
            print(f"[ReportAgent] Exception: {exc}")
            return None

    def _build_system_prompt(self, scene: str, rubric: list[str]) -> str:
        return SYSTEM_PROMPT_TEMPLATE.format(
            scene_display=_scene_display(scene),
            rubric_str=", ".join(rubric),
            scene_rules=_scene_rules(scene),
        )

    def _build_user_prompt(
        self, session_id: str, scene: str, rubric: list[str],
        analysis_summary: dict, conversation_history: list[dict],
        existing_timeline_events: list[dict],
    ) -> str:
        parts = []
        corrections = analysis_summary.get("corrections", [])
        filler_counts = analysis_summary.get("fillerCounts", {})
        pronunciation = analysis_summary.get("pronunciation", [])
        serious_count = sum(1 for c in corrections if c.get("severity") == "serious")
        total_fillers = sum(filler_counts.values())

        parts.append(f"Session: {session_id[:8]}, Scene: {_scene_display(scene)}")
        parts.append(f"Dimensions: {', '.join(rubric)}")
        parts.append(f"Turns: {len(pronunciation)}, Corrections: {len(corrections)} ({serious_count} serious)")
        parts.append(f"Fillers: {total_fillers}")

        if pronunciation:
            avg_wpm = sum(p.get("wordsPerMinute", 0) for p in pronunciation) / len(pronunciation)
            total_pauses = sum(p.get("pauseCount", 0) for p in pronunciation)
            parts.append(f"Avg WPM: {avg_wpm:.0f}, Pauses: {total_pauses}")

        if filler_counts:
            parts.append(f"Filler breakdown: {dict(sorted(filler_counts.items(), key=lambda x: -x[1]))}")

        if corrections:
            parts.append("Grammar corrections:")
            for c in corrections[:20]:
                parts.append(f"  [{c.get('turnId','?')}] {c.get('severity','?')}: '{c.get('original','')}' → '{c.get('corrected','')}'")

        if conversation_history:
            parts.append("Conversation:")
            for turn in conversation_history[-10:]:
                role = turn.get("role", "?")
                content = turn.get("content", "")[:300]
                tid = f"[{turn.get('turnId','')}] " if turn.get("turnId") else ""
                parts.append(f"  {role.upper()} {tid}: {content}")

        if existing_timeline_events:
            parts.append(f"Existing events: {len(existing_timeline_events)}")

        parts.append(f"Score all {len(rubric)} dimensions with evidence. Return ONLY JSON.")
        return "\n".join(parts)

    def _validate_and_clean(self, result: dict, rubric: list[str], summary: dict) -> dict:
        scene_score = result.get("sceneScore", 70)
        if not isinstance(scene_score, (int, float)) or not 0 <= scene_score <= 100:
            scene_score = 70

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
                cleaned_dims[dim] = {
                    "score": int(max(0, min(100, score if isinstance(score, (int, float)) else 60))),
                    "evidence": str(info.get("evidence", "")),
                }
            else:
                cleaned_dims[dim] = {"score": 60, "evidence": ""}

        highlights = result.get("highlights", []) if isinstance(result.get("highlights"), list) else []
        improvements = result.get("improvements", []) if isinstance(result.get("improvements"), list) else []
        if len(improvements) < 2:
            improvements.append("Review grammar correction records and practice corrected sentences")
            improvements.append("Continue practicing with more challenging scenarios")

        final_rec = result.get("finalRecommendation", "")
        if not isinstance(final_rec, str) or not final_rec:
            final_rec = "Keep practicing to improve your English communication skills."

        timeline_events = result.get("timelineEvents", []) if isinstance(result.get("timelineEvents"), list) else []
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
            "scoreName": result.get("scoreName", "Offer Score"),
            "dimensionScores": cleaned_dims,
            "highlights": highlights[:5],
            "improvements": improvements[:5],
            "finalRecommendation": final_rec,
            "timelineEvents": cleaned_timeline[:5],
        }


report_agent = ReportAgent()
