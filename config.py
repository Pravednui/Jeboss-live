import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    
    # Модель Gemini
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    
    # Голос TTS
    TTS_VOICE: str = "ru-RU-DmitryNeural"
    TTS_RATE: str = "+15%"
    TTS_PITCH: str = "+0Hz"
    
    # Файл памяти
    MEMORY_FILE: str = "memory.json"
    
    # Параметры детекции речи (VAD)
    VAD_RMS_THRESHOLD: int = 350
    VAD_SILENCE_CHUNKS: int = 6
    MIN_AUDIO_BYTES: int = 20000
    MAX_AUDIO_BYTES: int = 64000

config = Config()
