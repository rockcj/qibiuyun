"""对象存储服务 — 优先火山引擎 TOS，不可用时回落本地 storage/。"""

import asyncio
import io
import uuid
import wave
from pathlib import Path
from typing import Optional

from config import settings

# 本地会话音频目录
LOCAL_SESSION_AUDIO_DIR = Path(settings.local_storage_dir) / "sessions"


def pcm16_to_wav(pcm_bytes: bytes, sample_rate: int = 16000) -> bytes:
    """将 PCM16 单声道数据封装为 WAV。"""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buffer.getvalue()


def _tos_configured() -> bool:
    """是否已配置 TOS 凭证。"""
    return bool(
        settings.object_storage_provider == "tos"
        and settings.tos_bucket
        and settings.tos_access_key_id
        and settings.tos_secret_access_key
        and settings.tos_endpoint
    )


def _upload_tos_sync(object_key: str, data: bytes, content_type: str) -> str:
    """同步上传至 TOS（在线程池中调用）。"""
    import tos

    client = tos.TosClientV2(
        settings.tos_access_key_id,
        settings.tos_secret_access_key,
        settings.tos_endpoint,
        settings.tos_region,
    )
    client.put_object(
        settings.tos_bucket,
        object_key,
        content=data,
        content_type=content_type,
    )
    return object_key


def _download_tos_sync(object_key: str) -> bytes:
    """从 TOS 下载对象。"""
    import tos

    client = tos.TosClientV2(
        settings.tos_access_key_id,
        settings.tos_secret_access_key,
        settings.tos_endpoint,
        settings.tos_region,
    )
    resp = client.get_object(settings.tos_bucket, object_key)
    return resp.read()


class StorageService:
    """会话音频上传与读取。"""

    def turn_object_key(self, session_id: str, turn_id: str) -> str:
        """单轮用户发言 WAV 对象键。"""
        return f"sessions/{session_id}/turns/{turn_id}.wav"

    def full_session_object_key(self, session_id: str) -> str:
        """整场会话合并 WAV 对象键。"""
        return f"sessions/{session_id}/full.wav"

    def replay_api_path(self, session_id: str, turn_id: str) -> str:
        """前端统一使用的回放 API 路径。"""
        return f"/api/interviews/{session_id}/replay/{turn_id}"

    def full_replay_api_path(self, session_id: str) -> str:
        """整场会话回放 API 路径。"""
        return f"/api/interviews/{session_id}/replay/full"

    async def upload_turn_audio(
        self, session_id: str, turn_id: str, pcm_bytes: bytes
    ) -> dict:
        """上传单轮用户 PCM 音频，返回 storageKey 与 replayUrl。"""
        wav_bytes = pcm16_to_wav(pcm_bytes)
        object_key = self.turn_object_key(session_id, turn_id)

        if _tos_configured():
            try:
                await asyncio.to_thread(
                    _upload_tos_sync, object_key, wav_bytes, "audio/wav"
                )
                print(f"[Storage] TOS uploaded turn: {object_key}")
                return {
                    "storageKey": object_key,
                    "storageProvider": "tos",
                    "replayUrl": self.replay_api_path(session_id, turn_id),
                }
            except Exception as exc:
                print(f"[Storage] TOS upload failed, fallback local: {exc}")

        # 本地兜底
        local_dir = LOCAL_SESSION_AUDIO_DIR / session_id / "turns"
        local_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / f"{turn_id}.wav"
        local_path.write_bytes(wav_bytes)
        print(f"[Storage] Local saved turn: {local_path}")
        return {
            "storageKey": str(local_path),
            "storageProvider": "local",
            "replayUrl": self.replay_api_path(session_id, turn_id),
        }

    async def upload_full_session_audio(
        self, session_id: str, pcm_bytes: bytes
    ) -> Optional[dict]:
        """上传整场会话合并音频，返回 storageKey 与 replayUrl。"""
        if not pcm_bytes:
            return None
        wav_bytes = pcm16_to_wav(pcm_bytes)
        object_key = self.full_session_object_key(session_id)

        if _tos_configured():
            try:
                await asyncio.to_thread(
                    _upload_tos_sync, object_key, wav_bytes, "audio/wav"
                )
                print(f"[Storage] TOS uploaded full session: {object_key}")
                return {
                    "storageKey": object_key,
                    "storageProvider": "tos",
                    "replayUrl": self.full_replay_api_path(session_id),
                }
            except Exception as exc:
                print(f"[Storage] TOS full upload failed: {exc}")

        local_dir = LOCAL_SESSION_AUDIO_DIR / session_id
        local_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / "full.wav"
        local_path.write_bytes(wav_bytes)
        return {
            "storageKey": str(local_path),
            "storageProvider": "local",
            "replayUrl": self.full_replay_api_path(session_id),
        }

    async def read_turn_audio(
        self, session_id: str, turn_id: str, storage_key: str, provider: str
    ) -> Optional[bytes]:
        """读取单轮音频 WAV 字节。"""
        if provider == "tos" and _tos_configured():
            try:
                key = storage_key or self.turn_object_key(session_id, turn_id)
                return await asyncio.to_thread(_download_tos_sync, key)
            except Exception as exc:
                print(f"[Storage] TOS read failed: {exc}")
                return None

        path = Path(storage_key) if storage_key else (
            LOCAL_SESSION_AUDIO_DIR / session_id / "turns" / f"{turn_id}.wav"
        )
        if path.is_file():
            return path.read_bytes()
        return None

    async def read_full_session_audio(
        self, session_id: str, storage_key: Optional[str], provider: str
    ) -> Optional[bytes]:
        """读取整场会话音频。"""
        if provider == "tos" and storage_key and _tos_configured():
            try:
                return await asyncio.to_thread(_download_tos_sync, storage_key)
            except Exception as exc:
                print(f"[Storage] TOS read full failed: {exc}")

        path = LOCAL_SESSION_AUDIO_DIR / session_id / "full.wav"
        if path.is_file():
            return path.read_bytes()
        return None


storage_service = StorageService()
