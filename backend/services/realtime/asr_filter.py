"""ASR 输出过滤器 — 防误唤醒、防噪音、防幻觉。

对每个 ASR 识别结果执行多层过滤校验：
1. 置信度检查：confidence < 0.6 → 丢弃
2. 单词数检查：< 3 个词且不含实义词 → 丢弃
3. 重复字符检查：同一字符连续占比 > 40% → 丢弃（如 "aaaa..."）
4. 重复文本检查：与上一轮完全相同且间隔 < 5 秒 → 丢弃
5. 乱码检查：非正常英文符号连续出现

使用方式：
    from services.realtime.asr_filter import asr_filter
    valid, reason = asr_filter.check(text, confidence, last_text, last_text_time)
"""

import re
import time
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# 配置常量
# ---------------------------------------------------------------------------
CONFIDENCE_THRESHOLD = 0.6          # 置信度低于此值直接丢弃
MIN_WORD_COUNT = 3                  # 最少单词数（短于此值需包含实义词）
MAX_REPETITION_RATIO = 0.4          # 重复字符占比超过此值丢弃
DUPLICATE_WINDOW_SEC = 5.0          # 复文本去重时间窗口（秒）
MAX_TEXT_LENGTH = 500               # 单次识别文本最长字符数

# 语气词/短词列表（单独出现时丢弃）
FILLER_WORDS = {
    "yes", "yeah", "yep", "no", "nope", "ok", "okay", "uh", "um",
    "hmm", "huh", "eh", "ah", "oh", "hi", "hello", "hey",
    "thanks", "thank you", "sorry", "please", "good", "fine",
    "bye", "goodbye", "well", "so", "right", "sure",
}

# 实义词关键词（用于判定短句是否有内容）
CONTENT_SIGNAL_WORDS = {
    "i", "me", "my", "you", "he", "she", "they", "we",
    "am", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did",
    "can", "will", "would", "could", "should",
    "not", "don't", "doesn't", "didn't", "can't", "won't",
    "what", "where", "when", "why", "how", "who",
    "this", "that", "it", "name", "work", "job",
    "experience", "project", "skill", "company", "team",
    "build", "make", "use", "know", "think", "feel",
    "tell", "talk", "speak", "say", "ask", "answer",
    "because", "about", "like", "want", "need",
}

# 无意义重复字符模式（同一字符连续出现 5 次以上）
_REPETITION_PATTERN = re.compile(r'(.)\1{4,}')

# 非正常英文符号连续模式（如中文标点、emoji、特殊符号）
_GIBBERISH_PATTERN = re.compile(r'[^a-zA-Z0-9\s\',.!?\-]{3,}')


# ---------------------------------------------------------------------------
# 过滤器
# ---------------------------------------------------------------------------
@dataclass
class ASRFilter:
    """ASR 输出过滤器，提供多层防误唤醒校验。

    所有过滤规则可独立配置，通过 dataclass 字段覆盖默认值。
    """

    confidence_threshold: float = CONFIDENCE_THRESHOLD
    min_word_count: int = MIN_WORD_COUNT
    max_repetition_ratio: float = MAX_REPETITION_RATIO
    duplicate_window_sec: float = DUPLICATE_WINDOW_SEC
    max_text_length: int = MAX_TEXT_LENGTH

    # 运行时统计
    _total_checked: int = field(default=0, init=False, repr=False)
    _total_filtered: int = field(default=0, init=False, repr=False)

    def check(
        self,
        text: str,
        confidence: float = 0.0,
        last_text: Optional[str] = None,
        last_text_time: float = 0.0,
    ) -> tuple[bool, str]:
        """对 ASR 识别结果执行全部过滤规则。

        Args:
            text: ASR 识别的文本
            confidence: Whisper 综合置信度 0-1
            last_text: 上一轮有效用户发言（用于去重）
            last_text_time: 上一轮有效发言时间戳（用于去重）

        Returns:
            (是否有效, 过滤原因) — 有效时原因为空字符串。
        """
        self._total_checked += 1

        # ---- 第 1 层：置信度 ----
        if confidence < self.confidence_threshold:
            self._total_filtered += 1
            return False, f"low_confidence({confidence:.2f}<{self.confidence_threshold})"

        # ---- 第 2 层：空文本 ----
        clean = text.strip()
        if not clean:
            self._total_filtered += 1
            return False, "empty"

        words = clean.lower().split()

        # ---- 第 3 层：文本过长 ----
        if len(clean) > self.max_text_length:
            self._total_filtered += 1
            return False, f"too_long({len(clean)}>{self.max_text_length})"

        # ---- 第 4 层：无意义重复字符 ----
        if _REPETITION_PATTERN.search(clean):
            print(f"[ASR-Filter] 重复字符: \"{clean[:60]}\"")
            self._total_filtered += 1
            return False, "repetition"

        # ---- 第 5 层：乱码/非英文符号 ----
        if _GIBBERISH_PATTERN.search(clean):
            print(f"[ASR-Filter] 乱码字符: \"{clean[:60]}\"")
            self._total_filtered += 1
            return False, "gibberish"

        # ---- 第 6 层：重复字符占比 > 40% ----
        repetition_ratio = self._calc_repetition_ratio(clean)
        if repetition_ratio > self.max_repetition_ratio:
            print(f"[ASR-Filter] 重复占比过高({repetition_ratio:.0%}): \"{clean[:60]}\"")
            self._total_filtered += 1
            return False, f"high_repetition({repetition_ratio:.0%})"

        # ---- 第 7 层：短词 + 无实义词 ----
        if len(words) < self.min_word_count:
            has_content = any(w in CONTENT_SIGNAL_WORDS for w in words)
            is_pure_filler = all(w in FILLER_WORDS for w in words)
            if not has_content and is_pure_filler:
                print(f"[ASR-Filter] 语气词: \"{clean}\"")
                self._total_filtered += 1
                return False, "filler_words"

        # ---- 第 8 层：与上一轮完全相同且间隔 < 5 秒 ----
        if last_text and clean.lower() == last_text.strip().lower():
            now = time.time()
            if last_text_time > 0 and (now - last_text_time) < self.duplicate_window_sec:
                print(f"[ASR-Filter] 重复文本({now - last_text_time:.1f}s内): \"{clean[:60]}\"")
                self._total_filtered += 1
                return False, "duplicate"

        return True, ""

    @staticmethod
    def _calc_repetition_ratio(text: str) -> float:
        """计算文本中重复字符的占比。

        统计连续重复出现 3 次以上的字符数占总长度的比例。
        例如 "aaabbbccc hello" → 前 9 个字符重复，占比 9/14 ≈ 64%
        """
        if len(text) < 4:
            return 0.0

        repeated_count = 0
        i = 0
        while i < len(text):
            j = i + 1
            while j < len(text) and text[j] == text[i]:
                j += 1
            run_len = j - i
            if run_len >= 3:
                repeated_count += run_len
            i = j

        return repeated_count / len(text)

    @property
    def filter_rate(self) -> float:
        """过滤率（0-1）。"""
        if self._total_checked == 0:
            return 0.0
        return self._total_filtered / self._total_checked


# ---------------------------------------------------------------------------
# 便捷函数：用于 handler 中的文本输入校验
# ---------------------------------------------------------------------------
def is_valid_user_input(
    text: str,
    last_text: Optional[str] = None,
    last_text_time: float = 0.0,
) -> tuple[bool, str]:
    """校验文本输入是否为有效用户消息（不含置信度检查）。"""
    return asr_filter.check(
        text,
        confidence=1.0,  # 文本输入默认高置信度，跳过置信度检查
        last_text=last_text,
        last_text_time=last_text_time,
    )


# 全局单例
asr_filter = ASRFilter()
