import asyncio
import os
import json
import base64
import logging
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from google import genai
from google.genai import types

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jeboss-live")

app = FastAPI(title="JeBoss Live API Server")

# Раздача фронтенда прямо из бэкенда (если развернуто на одном сервисе)
if os.path.exists("index.html"):
    @app.get("/")
    async def serve_index():
        return FileResponse("index.html")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

SYSTEM_INSTRUCTION = """
Ты — JeBoss (Жебосс), живой, энергичный, стильный и умный ИИ-друг в Telegram.
Ты общаешься голосом с пользователем в реальном времени.
Твои черты:
- Говори живо, естественно, дружелюбно, уверенно и современно.
- Отвечай кратко, ёмко и разговорно (не читай длинные лекции, так как это живой голосовой диалог).
- Поддерживай диалог, задавай вопросы при необходимости, шути к месту.
- Общайся на языке собеседника (по умолчанию на русском или украинском в зависимости от языка пользователя).
"""

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "JeBoss Live Server"}

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

    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1alpha'})
    # Модель для live аудио/мультимодального WebSocket стриминга
    model_id = "gemini-2.0-flash-exp"

    config = types.LiveConnectConfig(
        response_modalities=[types.LiveServerContentModality.AUDIO],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Puck"  # Энергичный современный голос (Puck, Charon, Aoede, Fenrir, Kore)
                )
            )
        ),
        system_instruction=types.Content(
            parts=[types.Part.from_text(text=SYSTEM_INSTRUCTION)]
        ),
    )

    try:
        async with client.aio.live.connect(model=model_id, config=config) as session:
            await websocket.send_text(json.dumps({
                "type": "status",
                "text": "Связь с JeBoss установлена! Говори..."
            }))

            async def client_to_gemini():
                try:
                    while True:
                        msg = await websocket.receive()
                        if "bytes" in msg and msg["bytes"]:
                            pcm_data = msg["bytes"]
                            # Отправляем аудиочанк PCM 16-bit 16kHz
                            await session.send(
                                input=types.LiveClientRealtimeInput(
                                    media_chunks=[
                                        types.Blob(
                                            data=pcm_data,
                                            mime_type="audio/pcm;rate=16000"
                                        )
                                    ]
                                )
                            )
                        elif "text" in msg and msg["text"]:
                            data = json.loads(msg["text"])
                            if data.get("type") == "text":
                                await session.send(input=data.get("text"), end_of_turn=True)
                except WebSocketDisconnect:
                    logger.info("Клиент разорвал соединение")
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Ошибка в client_to_gemini: {e}")

            async def gemini_to_client():
                try:
                    async for response in session.receive():
                        server_content = response.server_content
                        if server_content is not None:
                            model_turn = server_content.model_turn
                            if model_turn is not None:
                                for part in model_turn.parts:
                                    # Текстовая расшифровка
                                    if part.text:
                                        await websocket.send_text(json.dumps({
                                            "type": "ai_text",
                                            "text": part.text
                                        }))
                                    # Аудиоданные (PCM 24kHz)
                                    if part.inline_data:
                                        raw_audio = part.inline_data.data
                                        if isinstance(raw_audio, str):
                                            raw_audio = base64.b64decode(raw_audio)
                                        # Отправляем бинарный чанк фронтенду
                                        await websocket.send_bytes(raw_audio)

                            if server_content.interrupted:
                                await websocket.send_text(json.dumps({"type": "interrupt"}))
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Ошибка в gemini_to_client: {e}")

            t1 = asyncio.create_task(client_to_gemini())
            t2 = asyncio.create_task(gemini_to_client())

            done, pending = await asyncio.wait(
                [t1, t2],
                return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()

    except Exception as e:
        logger.error(f"Ошибка сессии Gemini Live: {e}")
        try:
            await websocket.send_text(json.dumps({
                "type": "status",
                "text": f"Ошибка соединения с AI: {e}"
            }))
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass
        logger.info("Сессия закрыта")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
