"""Grammar Agent — 异步语法分析，规则优先 + LLM 增强。

职责：
- 检测严重语法错误（如 "I have did" → "I have done"）
- 统计语气词（um/uh 等）
- 严重错误且开启 realtimeLightCorrection 时触发 correction.light
- 轻微错误仅写入 cache 供课后汇总
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional

import httpx

from config import settings
from services.realtime.asr_filter import FILLER_WORDS


# ---------------------------------------------------------------------------
# 严重语法错误规则表（规则优先，保证无 API Key 时演示可复现）
# 格式: (错误模式 regex, 替换函数, 描述)
# ---------------------------------------------------------------------------
_SEVERE_GRAMMAR_RULES: list[tuple[re.Pattern, callable, str]] = [
    # have/has/had + 过去式动词（双重时态）
    (re.compile(r"\b(have|has|had)\s+did\b", re.I),
     lambda m: m.group(0).replace("did", "done").replace("Did", "Done"), "have/has/had + did"),
    (re.compile(r"\b(have|has|had)\s+went\b", re.I),
     lambda m: m.group(0).replace("went", "gone").replace("Went", "Gone"), "have/has/had + went"),
    (re.compile(r"\b(have|has|had)\s+saw\b", re.I),
     lambda m: m.group(0).replace("saw", "seen").replace("Saw", "Seen"), "have/has/had + saw"),
    (re.compile(r"\b(have|has|had)\s+took\b", re.I),
     lambda m: m.group(0).replace("took", "taken").replace("Took", "Taken"), "have/has/had + took"),
    (re.compile(r"\b(have|has|had)\s+made\b", re.I),
     lambda m: m.group(0).replace("made", "made"), "have/has/had + made (ok)"),
    # I/you/we/they + has
    (re.compile(r"\b(I|you|we|they)\s+has\b", re.I),
     lambda m: re.sub(r"\bhas\b", "have", m.group(0), flags=re.I), "subject-verb agreement: has→have"),
    # he/she/it + have
    (re.compile(r"\b(he|she|it)\s+have\b", re.I),
     lambda m: re.sub(r"\bhave\b", "has", m.group(0), flags=re.I), "subject-verb agreement: have→has"),
    # 第三人称 + 原形动词（无 -s）
    (re.compile(r"\b(he|she|it)\s+(do|go|make|take|work|speak|think)\b(?!\s)", re.I),
     lambda m: m.group(0) + "s" if not m.group(2).endswith("s") else m.group(0), "third person missing -s"),
    # did + 过去式（双重过去）
    (re.compile(r"\bdid\s+(went|saw|took|made|did|had|was|were)\b", re.I),
     lambda m: m.group(0), "did + past tense (double past)"),
    # am/is/are + 过去分词误用
    (re.compile(r"\b(am|is|are)\s+(did|went|took)\b", re.I),
     lambda m: m.group(0), "be + wrong verb form"),
]

# 非英文（中文等）字符检测
_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u30ff]")


def is_english_transcript(text: str) -> bool:
    """判断文本是否为英文口语（含中文则视为非英文）。"""
    if not text or not text.strip():
        return False
    if _CJK_PATTERN.search(text):
        return False
    # 英文字母占比过低 → 可能是 Whisper 对中文的幻觉转写
    letters = sum(1 for c in text if c.isalpha())
    if letters == 0:
        return False
    latin = sum(1 for c in text if ("a" <= c.lower() <= "z"))
    return latin / max(letters, 1) >= 0.85


# 轻微错误规则（仅课后汇总，不实时提示）
_MINOR_GRAMMAR_RULES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"\ba\s+([aeiouAEIOU]\w+)"), "an", "a→an before vowel"),
    (re.compile(r"\ban\s+([bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ]\w+)"), "a", "an→a before consonant"),
]


@dataclass
class GrammarResult:
    """语法分析结果。"""
    original: str = ""
    corrected: str = ""
    severity: str = "none"  # none | minor | serious
    spoken_tip: str = ""
    filler_counts: dict = field(default_factory=dict)


class GrammarAgent:
    """异步语法分析 Agent。"""

    def __init__(self):
        self._api_key: str = settings.deepseek_api_key or settings.llm_api_key
        self._base_url: str = settings.llm_api_base_url.rstrip("/")
        self._model: str = settings.llm_analysis_model or settings.llm_report_model

    def count_fillers(self, transcript: str) -> dict:
        """仅统计语气词，不做语法纠正。"""
        return self._detect_fillers(transcript)

    def _detect_fillers(self, transcript: str) -> dict:
        """统计语气词出现次数。"""
        words = transcript.lower().split()
        counts: dict[str, int] = {}
        for word in words:
            clean = word.strip(".,!?;:'\"")
            if clean in FILLER_WORDS:
                counts[clean] = counts.get(clean, 0) + 1
        return counts

    def _apply_severe_rules(self, transcript: str) -> Optional[GrammarResult]:
        """规则检测严重语法错误。"""
        for pattern, fix_fn, desc in _SEVERE_GRAMMAR_RULES:
            match = pattern.search(transcript)
            if match:
                original_phrase = match.group(0)
                corrected_phrase = fix_fn(match)
                # 跳过无实际变化的匹配（如 made→made）
                if original_phrase.lower() == corrected_phrase.lower():
                    continue
                corrected_text = transcript[:match.start()] + corrected_phrase + transcript[match.end():]
                return GrammarResult(
                    original=original_phrase,
                    corrected=corrected_phrase,
                    severity="serious",
                    spoken_tip=f"Just a tip: we say '{corrected_phrase}' instead of '{original_phrase}'.",
                )
        return None

    def _apply_minor_rules(self, transcript: str) -> Optional[GrammarResult]:
        """规则检测轻微语法错误（仅课后汇总）。"""
        for pattern, replacement, desc in _MINOR_GRAMMAR_RULES:
            match = pattern.search(transcript)
            if match:
                original_phrase = match.group(0)
                corrected_phrase = pattern.sub(replacement + r" \1", transcript)
                # 只取差异部分
                corrected_part = corrected_phrase[match.start():match.end() + len(replacement) - 1]
                return GrammarResult(
                    original=original_phrase,
                    corrected=corrected_part.strip(),
                    severity="minor",
                    spoken_tip="",
                )
        return None

    async def _llm_enhance(self, transcript: str) -> Optional[GrammarResult]:
        """LLM 增强判定（有 API Key 时），超时回落 None。"""
        if not self._api_key:
            return None

        prompt = (
            "Analyze this English sentence for SERIOUS grammar errors only "
            "(errors that affect understanding, like wrong tense or subject-verb agreement). "
            "Ignore minor issues like articles or prepositions.\n\n"
            f'Sentence: "{transcript}"\n\n'
            "Respond in JSON only:\n"
            '{"hasError": true/false, "severity": "serious"/"minor"/"none", '
            '"original": "wrong phrase", "corrected": "correct phrase"}'
        )

        url = f"{self._base_url}/v1/messages"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "max_tokens": 128,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }

        try:
            timeout = httpx.Timeout(settings.grammar_llm_timeout_sec)
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    return None
                data = resp.json()
                # 提取 LLM 回复文本
                content = ""
                if "content" in data and isinstance(data["content"], list):
                    for block in data["content"]:
                        if block.get("type") == "text":
                            content += block.get("text", "")
                elif "choices" in data:
                    content = data["choices"][0].get("message", {}).get("content", "")

                # 解析 JSON
                json_match = re.search(r"\{[^}]+\}", content)
                if not json_match:
                    return None
                result = json.loads(json_match.group())
                if not result.get("hasError"):
                    return None

                severity = result.get("severity", "minor")
                original = result.get("original", "")
                corrected = result.get("corrected", "")
                if not original or not corrected:
                    return None

                return GrammarResult(
                    original=original,
                    corrected=corrected,
                    severity=severity,
                    spoken_tip=(
                        f"Just a tip: we say '{corrected}' instead of '{original}'."
                        if severity == "serious" else ""
                    ),
                )
        except Exception as exc:
            print(f"[GrammarAgent] LLM enhance failed: {exc}")
            return None

    async def analyze(
        self,
        transcript: str,
        *,
        realtime_enabled: bool = True,
        correction_policy: Optional[dict] = None,
    ) -> GrammarResult:
        """分析语法，返回 GrammarResult。

        Args:
            transcript: 用户最终发言文本
            realtime_enabled: 是否开启实时轻纠正
            correction_policy: 场景纠错策略配置

        Returns:
            GrammarResult，含 severity/filler_counts 等
        """
        policy = correction_policy or {}
        only_severe = policy.get("onlyInterruptSevereErrors", True)

        # 非英文内容不做语法纠正（避免中文被误识别为英文后乱改）
        if not is_english_transcript(transcript):
            return GrammarResult(
                severity="none",
                filler_counts=self._detect_fillers(transcript),
            )

        # 1. 统计语气词
        filler_counts = self._detect_fillers(transcript)

        # 2. 规则优先检测严重错误
        result = self._apply_severe_rules(transcript)

        # 3. LLM 增强（有 Key 且规则未命中时，使用 pro 模型深度分析）
        if result is None and realtime_enabled:
            llm_result = await self._llm_enhance(transcript)
            if llm_result and llm_result.severity == "serious":
                result = llm_result

        # 4. 轻微错误检测（仅课后汇总）
        if result is None:
            minor = self._apply_minor_rules(transcript)
            if minor:
                result = minor

        # 5. 组装最终结果
        if result is None:
            result = GrammarResult(severity="none")

        result.filler_counts = filler_counts

        # 6. 根据开关和策略决定是否实时提示
        if not realtime_enabled:
            result.spoken_tip = ""
        elif only_severe and result.severity != "serious":
            result.spoken_tip = ""

        return result


# 全局单例
grammar_agent = GrammarAgent()
