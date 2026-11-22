import io
import wave
import logging
from typing import Optional
import speech_recognition as sr
import edge_tts
from app.core.config import config

logger = logging.getLogger("jeboss.audio")

recognizer = sr.Recognizer()
recognizer.dynamic_energy_threshold = False
recognizer.energy_threshold = 100

def recognize_speech(pcm_bytes: bytes) -> Optional[str]:
    """Преобразует 16kHz 16-bit PCM аудио в текст через Google Speech API"""
    try:
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(pcm_bytes)
        buf.seek(0)
        with sr.AudioFile(buf) as source:
            audio_data = recognizer.record(source)
        text = recognizer.recognize_google(audio_data, language="ru-RU")
        return text
    except Exception:
        return None

async def synthesize_speech(text: str) -> Optional[bytes]:
    """Генерирует живой нейронный голос DmitryNeural через Edge TTS"""
    try:
        comm = edge_tts.Communicate(
            text=text,
            voice=config.TTS_VOICE,
            rate=config.TTS_RATE,
            pitch=config.TTS_PITCH
        )
        audio_data = bytearray()
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                audio_data.extend(chunk["data"])
        return bytes(audio_data) if audio_data else None
    except Exception as e:
        logger.error(f"TTS synthesis error: {e}")
        return None

def detect_voice_activity(chunk: bytes) -> tuple[bool, int]:
    """
    Анализ громкости аудио чанка (VAD)
    Возвращает (is_speaking, avg_volume)
    """
    if len(chunk) < 320:
        return False, 0
    import struct
    count = len(chunk) // 2
    shorts = struct.unpack(f"<{count}h", chunk[:count*2])
    avg_vol = sum(abs(s) for s in shorts) // count
    return (avg_vol > config.VAD_RMS_THRESHOLD), avg_vol
