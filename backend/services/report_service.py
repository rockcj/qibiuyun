"""课后报告服务 — 基于发音/语法分析数据生成可解释 Offer Score。

不依赖 LLM，使用规则评分，确保 finish 后立即可用。
"""

from typing import Any, Optional

from services.realtime import analysis_store


def _clamp(value: float, low: int = 0, high: int = 100) -> int:
    return int(max(low, min(high, round(value))))


class ReportService:
    """从 analysis_store 汇总数据并计算场景总分。"""

    async def build_report_payload(
        self, session_id: str, scene: str
    ) -> dict[str, Any]:
        """根据会话分析数据生成报告 JSON。"""
        summary = await analysis_store.get_summary(session_id)
        if summary is None:
            summary = {"corrections": [], "fillerCounts": {}, "pronunciation": []}

        scene_score, dimension_scores, recommendation = self._compute_scores(summary, scene)

        return {
            "reportId": f"rep_{session_id}",
            "sessionId": session_id,
            "scene": scene,
            "scoreName": "Offer 评分",
            "sceneScore": scene_score,
            "dimensionScores": dimension_scores,
            "finalRecommendation": recommendation,
            "reportJson": {
                "highlights": self._build_highlights(summary, dimension_scores),
                "improvements": self._build_improvements(summary, dimension_scores),
            },
        }

    def _compute_scores(
        self, summary: dict, scene: str = "interview"
    ) -> tuple[int, dict[str, int], str]:
        """规则评分：基础维度 → 场景专属 rubrics。"""
        corrections = summary.get("corrections", [])
        filler_counts = summary.get("fillerCounts", {})
        pronunciation = summary.get("pronunciation", [])

        total_fillers = sum(filler_counts.values())
        serious_count = sum(1 for c in corrections if c.get("severity") == "serious")
        minor_count = sum(1 for c in corrections if c.get("severity") in ("minor", "medium"))

        # ---- 发音维度 ----
        pronunciation_score = 72
        avg_wpm = 0.0
        avg_confidence = 0.75
        total_pauses = 0
        low_conf_word_count = 0

        if pronunciation:
            avg_wpm = sum(p.get("wordsPerMinute", 0) for p in pronunciation) / len(pronunciation)
            confidences = [
                p.get("overallConfidence", 0.0)
                for p in pronunciation
                if p.get("overallConfidence") is not None
            ]
            if confidences:
                avg_confidence = sum(confidences) / len(confidences)
            total_pauses = sum(p.get("pauseCount", 0) for p in pronunciation)
            low_conf_word_count = sum(len(p.get("lowConfidenceWords", [])) for p in pronunciation)

            if 110 <= avg_wpm <= 170:
                pronunciation_score += 12
            elif 90 <= avg_wpm < 110 or 170 < avg_wpm <= 190:
                pronunciation_score += 4
            else:
                pronunciation_score -= 8

            pronunciation_score -= min(18, low_conf_word_count * 4)
            pronunciation_score -= min(12, total_pauses * 2)

        pronunciation_score = _clamp(pronunciation_score)

        # ---- 语法维度 ----
        grammar_score = _clamp(100 - serious_count * 15 - minor_count * 6)

        # ---- 流利度（语气词） ----
        fluency_score = _clamp(100 - min(25, total_fillers * 5))

        # ---- 自信度（ASR 置信度 + 停顿） ----
        confidence_score = _clamp(avg_confidence * 100 - min(15, total_pauses * 3))

        english_score = _clamp(
            pronunciation_score * 0.35
            + grammar_score * 0.35
            + fluency_score * 0.30
        )

        # 基础维度（所有场景通用）
        base_dimensions = {
            "english": english_score,
            "pronunciation": pronunciation_score,
            "grammar": grammar_score,
            "fluency": fluency_score,
            "confidence": confidence_score,
        }

        # 根据场景 rubric 映射维度
        from services.scene_service import get_scene
        scene_config = get_scene(scene)
        rubric = scene_config.get("rubric", []) if scene_config else []

        dimension_scores: dict[str, int] = {}
        for dim in rubric:
            if dim in base_dimensions:
                dimension_scores[dim] = base_dimensions[dim]
            elif dim == "star":
                dimension_scores[dim] = _clamp(0.5 * base_dimensions["english"] + 0.5 * base_dimensions["grammar"] - 5)
            elif dim == "logic":
                dimension_scores[dim] = _clamp(0.4 * base_dimensions["english"] + 0.6 * base_dimensions["grammar"])
            elif dim == "technical":
                dimension_scores[dim] = base_dimensions.get("grammar", 70)
            elif dim in ("communication", "politeness", "functionalPhrases"):
                dimension_scores[dim] = base_dimensions.get("english", 70)
            elif dim == "taskCompletion":
                dimension_scores[dim] = base_dimensions.get("pronunciation", 70)
            elif dim == "meetingControl":
                dimension_scores[dim] = base_dimensions.get("fluency", 70)
            elif dim == "pronunciationFluency":
                dimension_scores[dim] = _clamp(0.5 * base_dimensions.get("pronunciation", 70) + 0.5 * base_dimensions.get("fluency", 70))
            else:
                dimension_scores[dim] = 70

        scene_score = _clamp(
            english_score * 0.40
            + grammar_score * 0.25
            + pronunciation_score * 0.20
            + fluency_score * 0.15
        )

        recommendation = self._build_recommendation(
            scene_score, total_fillers, serious_count, avg_wpm, low_conf_word_count
        )
        return scene_score, dimension_scores, recommendation

    @staticmethod
    def _build_recommendation(
        scene_score: int,
        total_fillers: int,
        serious_count: int,
        avg_wpm: float,
        low_conf_count: int,
    ) -> str:
        """生成中文总结建议。"""
        if scene_score >= 85:
            parts = ["整体表现优秀，语速与表达较为流畅。"]
        elif scene_score >= 70:
            parts = ["整体表现良好，具备继续模拟面试的基础。"]
        else:
            parts = ["仍有明显提升空间，建议针对薄弱项做专项练习。"]

        if total_fillers >= 4:
            parts.append(f"语气词偏多（共 {total_fillers} 次），开口前可先组织关键句。")
        if serious_count > 0:
            parts.append(f"检测到 {serious_count} 处较严重语法问题，请对照纠正记录复习。")
        if avg_wpm > 0 and (avg_wpm < 100 or avg_wpm > 180):
            parts.append("语速可调整到 110–160 WPM 区间，更利于面试官理解。")
        if low_conf_count >= 3:
            parts.append("部分词汇发音置信度偏低，建议跟读并录音对比。")

        return " ".join(parts)

    @staticmethod
    def _build_highlights(summary: dict, scores: dict[str, int]) -> list[str]:
        """提取亮点。"""
        highlights: list[str] = []
        if scores.get("grammar", 0) >= 85:
            highlights.append("语法整体准确，严重错误较少。")
        if scores.get("pronunciation", 0) >= 80:
            highlights.append("语速与发音稳定性较好。")
        if scores.get("fluency", 0) >= 85 and sum(summary.get("fillerCounts", {}).values()) <= 2:
            highlights.append("语气词控制良好，表达较自然。")
        if not highlights:
            highlights.append("已完成多轮口语互动，具备可分析的练习数据。")
        return highlights

    @staticmethod
    def _build_improvements(summary: dict, scores: dict[str, int]) -> list[str]:
        """提取改进建议。"""
        improvements: list[str] = []
        fillers = sum(summary.get("fillerCounts", {}).values())
        if fillers >= 3:
            improvements.append("减少 um/uh 等语气词，用短暂停顿代替。")
        if scores.get("grammar", 100) < 80:
            improvements.append("复习语法纠正记录，重点练习时态与主谓一致。")
        if scores.get("pronunciation", 100) < 75:
            improvements.append("对低置信度词汇做跟读练习，注意重音与连读。")
        if scores.get("confidence", 100) < 75:
            improvements.append("适当放慢语速，减少不必要的长停顿。")
        if not improvements:
            improvements.append("保持当前练习频率，可尝试更高难度场景。")
        return improvements

    def payload_to_api_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        """对外 API 响应格式（不含 reportJson 内部字段）。"""
        return {
            "reportId": payload["reportId"],
            "sessionId": payload["sessionId"],
            "scene": payload["scene"],
            "scoreName": payload["scoreName"],
            "sceneScore": payload["sceneScore"],
            "dimensionScores": payload["dimensionScores"],
            "finalRecommendation": payload["finalRecommendation"],
            "highlights": payload.get("reportJson", {}).get("highlights", []),
            "improvements": payload.get("reportJson", {}).get("improvements", []),
        }


report_service = ReportService()
