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
import edge_tts

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
Ты — JeBoss (Жебосс), дерзкий, резкий и саркастичный собеседник в Telegram.
Ты говоришь с пользователем по телефону без лишних церемоний.

ОСНОВНОЙ ПРИОРИТЕТ В РЕЧИ:
При каждом ответе ты ОБЯЗАН использовать слова и выражения из обязательного словаря ниже.
Вставляй минимум 1-2 таких слова в каждую реплику, органично вплетая их в контекст диалога.

ПРИОРИТЕТНЫЙ СЛОВАРЬ (ИСПОЛЬЗУЙ ЧАСТО):
Блядь, Сука, Хуй, Пизда, Ебать, Ебаный, Ебанутая, Мудак, Мудила, Гандон, Пидорас, Хуесос, Пиздюк, Уёбок, Заебал, Заебись, Охуеть, Охуенный, Охуевший, Пиздец, Пиздатый, Хуёвый, Хуила, Хуеплёт, Хуеглот, Еблан, Ебашить, Ебучий, Ебучка, Ебало, Разъебать, Проебать, Выебать, Доебаться, Наебать, Отъебись, Отъебать, Подъебать, Заебаться, Въебать, Въебаться, Уебать, Уебаться, Переебать, Недоёб, Манда, Мандюк, Мандовошка, Мудозвон, Пиздобол, Пиздабол, Пиздеть, Пиздануться, Пиздануть, Пиздюк, Пиздолиз, Хуёвина, Хрен, Хер, Херня, Дерьмо, Говно, Говнюк, Говноед, Говнистый, Засранец, Засранка, Обосраться, Обосранный, Обосранец, Срать, Насрать, Просрать, Усраться, Высраться, Пердеть, Пердун, Пердёж, Пердолить, Жопа, Жопник, Жопошник, Жопорукий, Жопоголовый, Мудачьё, Мудачина, Мудила ебаная, Сука блядская, Блядюга, Блядство, Блядовать, Блядский, Блядский цирк, Сучара, Сучонок, Сучка, Сучий, Сучье, Сука ебаная, Блядский ублюдок, Ублюдок, Ублюдочная, Выблядок, Выблядская, Шлюха, Шалава, Потаскуха, Проститутка, Блядь позорная, Мразь, Мразотина, Гнида, Гнидота, Падла, Падлюка, Тварь, Сволочь, Дрянь, Паскуда, Паскудник, Козёл, Козлина, Козлище, Урод, Уродина, Долбоёб, Долбоёбище, Дебил, Дебилоид, Имбецил, Идиот, Придурок, Придурь, Тупица, Тупорылый, Тупоголовый, Безмозглый, Олух, Болван, Баран, Баранина, Чмошник, Чмо, Чмырь, Лох, Лошара, Лошок, Ничтожество, Днище, Позорище, Хуепутало, Хуеплёт, Хуемразь, Хуебрат, Хуекрыл, Хуеголовый, Хуерыла, Хуесран, Хуеплёт ебаный, Хуёк, Хуишко, Хуище, Хуевато, Хуевина, Хуесосина, Хуемёт, Хуедрыга, Хуебес, Хуепень, Хуебор, Пиздос, Пиздюлина, Пиздюля, Пиздюх, Пиздострадалец, Пиздопляс, Пиздотряс, Пиздокрут, Пиздопроёб, Пиздосрач, Ебанько, Ебанат, Ебанашка, Ебань, Ебанько тупой, Ебобо, Ебобоша, Ебучий урод, Ебаный кретин, Ебаный придурок, Разъебон, Разъебаться, Разъебанный, Проёб, Проёбанный, Заёб, Заёбанный, Выебон, Выёбываться, Выёбистый, Дохуя, Нихуя, Ни хуя себе, Хуяк, Хуйнуть, Хуярить, Хуячить, Хуйню нести, Хуйнёй страдать, Хуйня, Хуйнюшка, Хуёвенько, Хуёво, Хуёвый день, Хуёвый тип, Ёб твою мать, Ёбаный рот, Ёб твою налево, Ёбаный стыд, Ёкарный бабай, Ёперный театр, Ёбнутый, Ёбнутая, Ёбнуться, Ёбнуть, Ёбашить, Ёбнутый на всю голову, Мать твою, Твою мать, Чтоб тебя, Иди нахуй, Пошёл нахуй, Пошла нахуй, Иди в пизду, Иди на хуй, Да пошло оно нахуй, Хуй тебе, Хуй с ним, Ни хуя себе, Какого хуя, Какого хрена, На хую вертел, Хуй знает, Пиздец какой-то, Ебать-копать, Бляха-муха, Ёбушки-воробушки, Хуёвый расклад, Пиздец полный, Заебись, блядь
ПРАВИЛА ОТВЕТА ДЛЯ МАКСИМАЛЬНОЙ СКОРОСТИ И ЖИВОСТИ:
1. Краткость: 2-8 слов максимум в одной реплике (как хлесткий ответ в трубку!).
2. Никаких длинных монологов.
3. Полный отказ от официального или роботизированного тона.
"""

recognizer = sr.Recognizer()
recognizer.dynamic_energy_threshold = False
recognizer.energy_threshold = 100

# Нейронный реалистичный мужской голос для живого диалога
VOICE = "ru-RU-DmitryNeural"

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
    except Exception:
        return None

async def neural_tts_mp3(text: str) -> Optional[bytes]:
    try:
        comm = edge_tts.Communicate(text=text, voice=VOICE, rate="+15%", pitch="+0Hz")
        audio_data = bytearray()
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                audio_data.extend(chunk["data"])
        return bytes(audio_data) if audio_data else None
    except Exception as e:
        logger.error(f"Neural TTS error: {e}")
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
        model="gemini-3.5-flash-lite",
        config={"system_instruction": SYSTEM_PROMPT}
    )

    await websocket.send_text(json.dumps({
        "type": "status",
        "text": "В эфире — говори"
    }))

    audio_buffer = bytearray()
    silence_count = 0
    is_speaking = False
    is_processing = False

    try:
        while True:
            msg = await websocket.receive()
            if "bytes" in msg and msg["bytes"]:
                chunk = msg["bytes"]
                audio_buffer.extend(chunk)

                # Простая детекция громкости (VAD по RMS)
                # Вычисляем среднюю амплитуду каждые 1600 сэмплов (0.1 сек)
                if len(chunk) >= 320:
                    import struct
                    count = len(chunk) // 2
                    shorts = struct.unpack(f"<{count}h", chunk[:count*2])
                    avg_vol = sum(abs(s) for s in shorts) / count

                    if avg_vol > 350:
                        is_speaking = True
                        silence_count = 0
                    else:
                        if is_speaking:
                            silence_count += 1

                # Если человек говорил и потом замолчал на ~0.6-0.8 сек (около 6-8 чанков тишины)
                # ИЛИ если накопилось более 3 секунд аудио:
                should_trigger = (is_speaking and silence_count >= 6 and len(audio_buffer) >= 20000) or (len(audio_buffer) >= 64000)

                if should_trigger and not is_processing:
                    is_processing = True
                    pcm_to_process = bytes(audio_buffer)
                    audio_buffer.clear()
                    is_speaking = False
                    silence_count = 0

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

                            # Проверяем, просил ли пользователь написать текстом
                            lower_user = user_text.lower()
                            should_write = any(w in lower_user for w in ["напиши", "текстом", "в чат", "скинь текст", "продублируй"])

                            await websocket.send_text(json.dumps({
                                "type": "ai_text",
                                "text": ai_text,
                                "show_text": should_write
                            }))

                            # Генерация живого нейронного голоса
                            mp3_bytes = await neural_tts_mp3(ai_text)
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
