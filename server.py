import asyncio
import os
import json
import base64
import logging
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import config
from app.services.audio import recognize_speech, synthesize_speech, detect_voice_activity
from app.services.ai import gemini_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("jeboss.server")

app = FastAPI(title="JeBoss Live & Self-Learning AI", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

@app.get("/")
async def serve_index():
    index_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "JeBoss Live AI Backend is running."}

@app.get("/manifest.json")
async def serve_manifest():
    path = os.path.join(BASE_DIR, "manifest.json")
    if not os.path.exists(path):
        path = os.path.join(STATIC_DIR, "manifest.json")
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "manifest not found"}

@app.get("/sw.js")
async def serve_sw():
    path = os.path.join(BASE_DIR, "sw.js")
    if not os.path.exists(path):
        path = os.path.join(STATIC_DIR, "sw.js")
    if os.path.exists(path):
        return FileResponse(path, media_type="application/javascript")
    return {"error": "sw not found"}

@app.get("/{icon_name}.png")
async def serve_any_png(icon_name: str):
    fname = f"{icon_name}.png"
    root_path = os.path.join(BASE_DIR, fname)
    if os.path.exists(root_path):
        return FileResponse(root_path)
    stat_path = os.path.join(STATIC_DIR, fname)
    if os.path.exists(stat_path):
        return FileResponse(stat_path)
    return {"error": "icon not found"}

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "JeBoss Live & Self-Learning Server",
        "runtime": "Python 3 / FastAPI",
        "model": config.GEMINI_MODEL
    }

@app.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Клиент подключился к WebSocket")

    if not config.GEMINI_API_KEY:
        await websocket.send_text(json.dumps({
            "type": "status",
            "text": "Ошибка: GEMINI_API_KEY не задан на сервере!"
        }))
        await websocket.close()
        return

    try:
        chat = gemini_service.create_chat_session()
    except Exception as e:
        logger.error(f"Chat init error: {e}")
        await websocket.send_text(json.dumps({
            "type": "status",
            "text": f"Ошибка инициализации ИИ: {e}"
        }))
        await websocket.close()
        return

    await websocket.send_text(json.dumps({
        "type": "status",
        "text": "В эфире — говори"
    }))

    audio_buffer = bytearray()
    silence_count = 0
    is_speaking = False
    is_processing = False
    conversation_history: List[str] = []

    try:
        while True:
            msg = await websocket.receive()
            if "bytes" in msg and msg["bytes"]:
                chunk = msg["bytes"]
                audio_buffer.extend(chunk)

                speaking, _ = detect_voice_activity(chunk)
                if speaking:
                    is_speaking = True
                    silence_count = 0
                else:
                    if is_speaking:
                        silence_count += 1

                # Умный триггер окончания фразы (VAD)
                should_trigger = (
                    (is_speaking and silence_count >= config.VAD_SILENCE_CHUNKS and len(audio_buffer) >= config.MIN_AUDIO_BYTES)
                    or (len(audio_buffer) >= config.MAX_AUDIO_BYTES)
                )

                if should_trigger and not is_processing:
                    is_processing = True
                    pcm_to_process = bytes(audio_buffer)
                    audio_buffer.clear()
                    is_speaking = False
                    silence_count = 0

                    loop = asyncio.get_running_loop()
                    user_text = await loop.run_in_executor(None, recognize_speech, pcm_to_process)

                    if user_text and len(user_text.strip()) > 1:
                        logger.info(f"Распознано: {user_text}")
                        conversation_history.append(f"Пользователь: {user_text}")

                        await websocket.send_text(json.dumps({
                            "type": "user_text",
                            "text": user_text
                        }))
                        await websocket.send_text(json.dumps({
                            "type": "status",
                            "text": "JeBoss отвечает..."
                        }))

                        # Запрос в Gemini
                        try:
                            gemini_resp = await loop.run_in_executor(
                                None,
                                lambda: chat.send_message(user_text)
                            )
                            ai_text = gemini_resp.text.strip()
                            logger.info(f"JeBoss ответил: {ai_text}")
                            conversation_history.append(f"JeBoss: {ai_text}")

                            lower_user = user_text.lower()
                            should_write = any(w in lower_user for w in ["напиши", "текстом", "в чат", "скинь текст", "продублируй"])

                            await websocket.send_text(json.dumps({
                                "type": "ai_text",
                                "text": ai_text,
                                "show_text": should_write
                            }))

                            # Генерация живого нейронного голоса
                            mp3_bytes = await synthesize_speech(ai_text)
                            if mp3_bytes:
                                b64_audio = base64.b64encode(mp3_bytes).decode('ascii')
                                await websocket.send_text(json.dumps({
                                    "type": "audio_mp3",
                                    "data": b64_audio
                                }))

                        except Exception as ge:
                            logger.error(f"Gemini error: {ge}")

                        await websocket.send_text(json.dumps({
                            "type": "status",
                            "text": "В эфире — говори"
                        }))

                    is_processing = False

    except WebSocketDisconnect:
        logger.info("Клиент отключился")
    except Exception as e:
        logger.error(f"WS error: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass
        # Фоновое самообучение после завершения разговора
        if conversation_history:
            asyncio.create_task(gemini_service.reflect_and_learn(conversation_history))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host=config.HOST, port=config.PORT, reload=True)
