import asyncio
import os
import json
import io
import wave
import base64
import logging
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from google import genai
import speech_recognition as sr
from gtts import gTTS

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jeboss-live")

app = FastAPI(title="JeBoss Live API Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if os.path.exists("index.html"):
    @app.get("/")
    async def serve_index():
        return FileResponse("index.html")

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "JeBoss Live Server"}

SYSTEM_PROMPT = """
Ты — JeBoss (Жебосс), живой, энергичный, стильный и умный голосовой ИИ-друг в Telegram.
Ты общаешься с пользователем короткими фразами в диалоге (1-2 емких предложения), очень естественно, дружелюбно, уверенно и современно.
Никаких списков, маркеров и длинных лекций — это живая разговорная речь!
"""

recognizer = sr.Recognizer()

def recognize_audio(pcm_bytes: bytes) -> Optional[str]:
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
    except Exception as e:
        return None

def text_to_speech_mp3(text: str) -> Optional[bytes]:
    try:
        tts = gTTS(text=text, lang='ru')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp.read()
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return None

@app.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Клиент подключился к WebSocket")

    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if not api_key:
        await websocket.send_text(json.dumps({
            "type": "status",
            "text": "Ошибка: GEMINI_API_KEY не задан на сервере!"
        }))
        await websocket.close()
        return

    gemini_client = genai.Client(api_key=api_key)
    chat = gemini_client.chats.create(
        model="gemini-3.1-flash-lite",
        config={"system_instruction": SYSTEM_PROMPT}
    )

    await websocket.send_text(json.dumps({
        "type": "status",
        "text": "В эфире — говори"
    }))

    audio_buffer = bytearray()
    is_processing = False

    try:
        while True:
            msg = await websocket.receive()
            if "bytes" in msg and msg["bytes"]:
                chunk = msg["bytes"]
                audio_buffer.extend(chunk)

                # Каждые ~2 секунды аудио анализируем
                if len(audio_buffer) >= 64000 and not is_processing:
                    is_processing = True
                    pcm_to_process = bytes(audio_buffer)
                    audio_buffer.clear()

                    loop = asyncio.get_running_loop()
                    user_text = await loop.run_in_executor(None, recognize_audio, pcm_to_process)

                    if user_text and len(user_text.strip()) > 1:
                        logger.info(f"Распознано: {user_text}")
                        await websocket.send_text(json.dumps({
                            "type": "user_text",
                            "text": user_text
                        }))
                        await websocket.send_text(json.dumps({
                            "type": "status",
                            "text": "JeBoss думает..."
                        }))

                        # Запрос в Gemini
                        try:
                            gemini_resp = await loop.run_in_executor(
                                None,
                                lambda: chat.send_message(user_text)
                            )
                            ai_text = gemini_resp.text
                            logger.info(f"JeBoss ответил: {ai_text}")

                            await websocket.send_text(json.dumps({
                                "type": "ai_text",
                                "text": ai_text
                            }))

                            # Озвучка
                            mp3_bytes = await loop.run_in_executor(None, text_to_speech_mp3, ai_text)
                            if mp3_bytes:
                                b64_audio = base64.b64encode(mp3_bytes).decode('ascii')
                                await websocket.send_text(json.dumps({
                                    "type": "audio_mp3",
                                    "data": b64_audio
                                }))

                        except Exception as ge:
                            logger.error(f"Gemini error: {ge}")
                            await websocket.send_text(json.dumps({
                                "type": "ai_text",
                                "text": "Я тебя слышу, но давай повторим!"
                            }))

                        await websocket.send_text(json.dumps({
                            "type": "status",
                            "text": "В эфире — говори"
                        }))

                    is_processing = False

            elif "text" in msg and msg["text"]:
                try:
                    data = json.loads(msg["text"])
                    if data.get("type") == "text":
                        txt = data.get("text")
                        gemini_resp = chat.send_message(txt)
                        await websocket.send_text(json.dumps({
                            "type": "ai_text",
                            "text": gemini_resp.text
                        }))
                except:
                    pass

    except WebSocketDisconnect:
        logger.info("Клиент отключился")
    except Exception as e:
        logger.error(f"WS error: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
