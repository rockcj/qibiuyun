"""ASR 过滤器单元测试 – 短句放行与语气词过滤。"""

from services.realtime.asr_filter import asr_filter


class TestAsrFilter:
    """ASR 输出过滤规则测试。"""

    def test_hello_short_utterance_allowed(self):
        """实时对话中 hello 应被放行。"""
        valid, reason = asr_filter.check("hello", confidence=0.85)
        assert valid is True
        assert reason == ""

    def test_hi_short_utterance_allowed(self):
        """hi 打招呼应被放行。"""
        valid, reason = asr_filter.check("hi", confidence=0.9)
        assert valid is True
        assert reason == ""

    def test_pure_filler_um_still_filtered(self):
        """纯语气词 um 仍应被过滤。"""
        valid, reason = asr_filter.check("um", confidence=0.9)
        assert valid is False
        assert reason == "filler_words"

    def test_chinese_rejected(self):
        """中文语音转写应被拦截。"""
        valid, reason = asr_filter.check("你好我想练习", confidence=0.95)
        assert valid is False
        assert reason == "non_english"
