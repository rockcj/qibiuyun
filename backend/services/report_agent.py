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


SYSTEM_PROMPT_TEMPLATE = """你是 OfferGPT 的英语口语评估专家。

## 场景：{scene_display}
## 评分维度：{rubric_str}
## 规则：{scene_rules}

请用**简体中文**撰写所有分析文本（highlights、improvements、finalRecommendation、evidence、timeline 的 title/description/suggestion 均须中文）。英文原句可保留在 transcriptSnippet 中。

为每个 rubric 维度给出 0-100 分，并提供来自会话的具体证据。

仅返回合法 JSON：
{{
  "sceneScore": 78,
  "scoreName": "Offer 评分",
  "dimensionScores": {{
    "english": {{"score": 75, "evidence": "具体引用或观察（中文）"}}
  }},
  "highlights": ["中文亮点"],
  "improvements": ["中文改进建议"],
  "finalRecommendation": "中文总结与录用建议",
  "timelineEvents": [
    {{
      "turnId": "turn_002",
      "eventType": "star_missing",
      "severity": "medium",
      "title": "STAR：缺少 Situation",
      "description": "中文描述",
      "startMs": 45000,
      "endMs": 65000,
      "transcriptSnippet": "英文原句",
      "suggestion": "中文改进建议"
    }}
  ]
}}"""


def _scene_rules(scene: str) -> str:
    if scene == "interview":
        return "求职面试。关注 STAR 法则、量化成果、技术深度。评分名称：Offer 评分。"
    elif scene == "restaurant":
        return "餐厅点餐。关注礼貌用语、功能句型、任务完成度。评分名称：点餐评分。"
    elif scene == "meeting":
        return "商务会议。关注专业沟通、会议掌控、表达清晰度。评分名称：会议评分。"
    return "通用英语对话练习。"


def _scene_display(scene: str) -> str:
    mapping = {"interview": "求职面试", "restaurant": "餐厅点餐", "meeting": "商务会议"}
    return mapping.get(scene, scene)


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
        parts.append("重要：highlights、improvements、finalRecommendation、各维度 evidence、timeline 的 title/description/suggestion 必须使用简体中文。")
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
            improvements.extend([
                "对照语法纠正记录，练习修正后的句子。",
                "继续挑战更高难度场景，巩固表达能力。",
            ])

        final_rec = result.get("finalRecommendation", "")
        if not isinstance(final_rec, str) or not final_rec:
            final_rec = "请继续练习，重点改进语法准确性与表达流畅度。"
        elif final_rec.startswith("Keep practicing") or "Not recommended" in final_rec:
            final_rec = "本次表现仍有较大提升空间，建议对照纠正记录专项练习后再进行模拟面试。"

        score_name = result.get("scoreName", "Offer 评分")
        if score_name in ("Offer Score", "Scene Score"):
            score_name = "Offer 评分"

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
            "scoreName": score_name,
            "dimensionScores": cleaned_dims,
            "highlights": highlights[:5],
            "improvements": improvements[:5],
            "finalRecommendation": final_rec,
            "timelineEvents": cleaned_timeline[:5],
        }


report_agent = ReportAgent()
