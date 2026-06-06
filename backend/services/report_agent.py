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


SYSTEM_PROMPT_TEMPLATE = """You are an expert English speaking coach and assessor for OfferGPT, serving Chinese-speaking learners.

## Scene: {scene_display}
## Rubric: {rubric_str}
## Rules: {scene_rules}

For each rubric dimension, assign score (0-100) AND concrete evidence from the session.

## 语言要求（极其重要）
- 所有面向用户的文本必须使用中文，包括：evidence（评分依据）、highlights、improvements、finalRecommendation
- highlights、improvements、finalRecommendation 额外提供英文版本（加 En 后缀）
- dimensionScores 中每个维度的 evidence 字段必须用中文撰写
- 中英文内容应对应但不必逐字翻译，各自符合母语表达习惯

Return ONLY valid JSON:
{{
  "sceneScore": 78,
  "scoreName": "Offer Score",
  "dimensionScores": {{
    "english": {{"score": 75, "evidence": "使用了较丰富的词汇，但存在少量语法错误如主谓一致问题"}}
  }},
  "highlights": ["回答结构清晰，使用了具体数据支撑观点"],
  "highlightsEn": ["Clear answer structure with specific data to support points"],
  "improvements": ["建议使用 STAR 方法组织行为面试回答，补充具体行动和量化结果"],
  "improvementsEn": ["Use STAR method for behavioral questions — add specific actions and quantified results"],
  "finalRecommendation": "整体表现不错，继续加强 STAR 结构化的回答能力，多用量化指标展示成果。",
  "finalRecommendationEn": "Good overall performance. Continue strengthening STAR-structured responses with quantified outcomes.",
  "timelineEvents": [
当用户回答行为面试题时，检查是否包含完整的 STAR 四要素：
- S (Situation / 情境) — 当时是什么背景？在什么项目中？
- T (Task / 任务) — 你需要完成什么目标？
- A (Action / 行动) — 你个人采取了哪些具体行动？
- R (Result / 结果) — 带来了什么可量化的成果？

创建 star_missing 事件时，要求：
- title: 用中文概括缺失了哪个要素，如"回答缺少具体行动细节"、"缺少量化结果"，不要用 "STAR: Missing X" 这种格式
- description: 用友好的中文说明当前回答缺少了什么，为什么重要
- suggestion: 必须包含完整的 STAR 四要素模板，用中文，每要素配一句具体示例，让用户知道怎么改。格式示例：
  "💡 建议用 STAR 方法组织回答：\\nS (情境): 当时我负责 [具体项目]，遇到了 [具体问题]\\nT (任务): 我的目标是在 [时间] 内达成 [指标]\\nA (行动): 我做了 [具体动作1]、[具体动作2]，使用了 [技术/方法]\\nR (结果): 最终 [指标] 提升了 X%，获得了 [认可/奖励]"

Return ONLY valid JSON (see format above). timelineEvents examples:
[
    {{
      "turnId": "turn_002",
      "eventType": "star_missing",
      "severity": "medium",
      "title": "回答缺少具体行动细节",
      "description": "你描述了项目的背景和目标，但没有说明你个人采取了哪些行动。面试官希望了解你的具体贡献。",
      "startMs": 45000,
      "endMs": 65000,
      "transcriptSnippet": "用户的原始回答片段（英文）",
      "suggestion": "💡 建议用 STAR 方法组织回答：\\nS (情境): 当时我负责推荐系统的性能优化，响应延迟高达 500ms\\nT (任务): 需要在 2 周内将响应时间降到 100ms 以内\\nA (行动): 我引入了 Redis 缓存层，重构了冷数据查询逻辑，并做了预加载优化\\nR (结果): 最终响应时间降到 80ms，用户留存率提升了 12%"
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

        highlights_en = result.get("highlightsEn", []) if isinstance(result.get("highlightsEn"), list) else []
        improvements_en = result.get("improvementsEn", []) if isinstance(result.get("improvementsEn"), list) else []
        final_rec_en = result.get("finalRecommendationEn", "")
        if not isinstance(final_rec_en, str):
            final_rec_en = ""

        return {
            "sceneScore": int(scene_score),
            "scoreName": result.get("scoreName", "Offer Score"),
            "dimensionScores": cleaned_dims,
            "highlights": highlights[:5],
            "improvements": improvements[:5],
            "finalRecommendation": final_rec,
            "highlightsEn": highlights_en[:5],
            "improvementsEn": improvements_en[:5],
            "finalRecommendationEn": final_rec_en,
            "timelineEvents": cleaned_timeline[:5],
        }


report_agent = ReportAgent()
