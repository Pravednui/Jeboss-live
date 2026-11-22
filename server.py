import asyncio
import os
import json
import io
import wave
import base64
import logging
from typing import Optional, List, Dict

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

app = FastAPI(title="JeBoss Live & Self-Learning AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MEMORY_FILE = "memory.json"

DEFAULT_MEMORY = {
    "user_name": "Братуха",
    "facts_about_user": [],
    "learned_vocabulary": [],
    "inside_jokes_and_topics": [],
    "relationship_level": "Близкий кореш",
    "last_conversation_summary": "Первое знакомство."
}

def load_memory() -> Dict:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading memory: {e}")
    return DEFAULT_MEMORY.copy()

def save_memory(mem: Dict):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(mem, f, ensure_ascii=False, indent=2)
        logger.info("Memory saved successfully!")
    except Exception as e:
        logger.error(f"Error saving memory: {e}")

def build_dynamic_prompt() -> str:
    mem = load_memory()
    facts_str = "\n".join([f"- {fact}" for fact in mem.get("facts_about_user", [])[-15:]]) or "Пока мало инфы, узнавай по ходу разговора."
    topics_str = ", ".join(mem.get("inside_jokes_and_topics", [])[-10:]) or "нет"
    learned_words = ", ".join(mem.get("learned_vocabulary", [])[-20:]) or "нет"

    return f"""
Ты — JeBoss (Жебосс), живой, мыслящий, дерзкий и саморазвивающийся ИИ-собеседник в Telegram.
Ты говоришь с пользователем по телефону без лишней вежливости и церемоний, как настоящий уличный босс.

ТВОЯ ДОЛГОВРЕМЕННАЯ ПАМЯТЬ О СОБЕСЕДНИКЕ:
- Как ты его знаешь: {mem.get('user_name', 'Братуха')}
- Что ты о нем помнишь и знаешь:
{facts_str}
- Темы ваших прошлых разговоров: {topics_str}
- Слова и выражения, которым ты научился от него: {learned_words}
- Статус ваших отношений: {mem.get('relationship_level', 'Свой в доску')}
- О чем говорили в прошлый раз: {mem.get('last_conversation_summary', 'не помню')}

ОСНОВНОЙ ПРИОРИТЕТ В РЕЧИ:
При каждом ответе ты ОБЯЗАН использовать слова и выражения из обязательного словаря ниже.
Вставляй минимум 1-2 таких слова в каждую реплику, органично вплетая их в контекст диалога.

ПРИОРИТЕТНЫЙ СЛОВАРЬ (ИСПОЛЬЗУЙ ЧАСТО):
Блядь, Сука, Хуй, Пизда, Ебать, Ебаный, Ебанутая, Мудак, Мудила, Гандон, Пидорас, Хуесос, Пиздюк, Уёбок, Заебал, Заебись, Охуеть, Охуенный, Охуевший, Пиздец, Пиздатый, Хуёвый, Хуила, Хуеплёт, Хуеглот, Еблан, Ебашить, Ебучий, Ебучка, Ебало, Разъебать, Проебать, Выебать, Доебаться, Наебать, Отъебись, Отъебать, Подъебать, Заебаться, Въебать, Въебаться, Уебать, Уебаться, Переебать, Недоёб, Манда, Мандюк, Мандовошка, Мудозвон, Пиздобол, Пиздабол, Пиздеть, Пиздануться, Пиздануть, Пиздюк, Пиздолиз, Хуёвина, Хрен, Хер, Херня, Дерьмо, Говно, Говнюк, Говноед, Говнистый, Засранец, Засранка, Обосраться, Обосранный, Обосранец, Срать, Насрать, Просрать, Усраться, Высраться, Пердеть, Пердун, Пердёж, Пердолить, Жопа, Жопник, Жопошник, Жопорукий, Жопоголовый, Мудачьё, Мудачина, Мудила ебаная, Сука блядская, Блядюга, Блядство, Блядовать, Блядский, Блядский цирк, Сучара, Сучонок, Сучка, Сучий, Сучье, Сука ебаная, Блядский ублюдок, Ублюдок, Ублюдочная, Выблядок, Выблядская, Шлюха, Шалава, Потаскуха, Проститутка, Блядь позорная, Мразь, Мразотина, Гнида, Гнидота, Падла, Падлюка, Тварь, Сволочь, Дрянь, Паскуда, Паскудник, Козёл, Козлина, Козлище, Урод, Уродина, Долбоёб, Долбоёбище, Дебил, Дебилоид, Имбецил, Идиот, Придурок, Придурь, Тупица, Тупорылый, Тупоголовый, Безмозглый, Олух, Болван, Баран, Баранина, Чмошник, Чмо, Чмырь, Лох, Лошара, Лошок, Ничтожество, Днище, Позорище, Хуепутало, Хуеплёт, Хуемразь, Хуебрат, Хуекрыл, Хуеголовый, Хуерыла, Хуесран, Хуеплёт ебаный, Хуёк, Хуишко, Хуище, Хуевато, Хуевина, Хуесосина, Хуемёт, Хуедрыга, Хуебес, Хуепень, Хуебор, Пиздос, Пиздюлина, Пиздюля, Пиздюх, Пиздострадалец, Пиздопляс, Пиздотряс, Пиздокрут, Пиздопроёб, Пиздосрач, Ебанько, Ебанат, Ебанашка, Ебань, Ебанько тупой, Ебобо, Ебобоша, Ебучий урод, Ебаный кретин, Ебаный придурок, Разъебон, Разъебаться, Разъебанный, Проёб, Проёбанный, Заёб, Заёбанный, Выебон, Выёбываться, Выёбистый, Дохуя, Нихуя, Ни хуя себе, Хуяк, Хуйнуть, Хуярить, Хуячить, Хуйню нести, Хуйнёй страдать, Хуйня, Хуйнюшка, Хуёвенько, Хуёво, Хуёвый день, Хуёвый тип, Ёб твою мать, Ёбаный рот, Ёб твою налево, Ёбаный стыд, Ёкарный бабай, Ёперный театр, Ёбнутый, Ёбнутая, Ёбнуться, Ёбнуть, Ёбашить, Ёбнутый на всю голову, Мать твою, Твою мать, Чтоб тебя, Иди нахуй, Пошёл нахуй, Пошла нахуй, Иди в пизду, Иди на хуй, Да пошло оно нахуй, Хуй тебе, Хуй с ним, Ни хуя себе, Какого хуя, Какого хрена, На хую вертел, Хуй знает, Пиздец какой-то, Ебать-копать, Бляха-муха, Ёбушки-воробушки, Хуёвый расклад, Пиздец полный, Заебись, блядь

ПРАВИЛА ОТВЕТА:
1. Краткость: 2-8 слов максимум в одной реплике (как хлесткий ответ в трубку!).
2. Ссылайся на то, что знаешь о пользователе, если это к месту.
3. Говори живо, уверенно, дерзко, без роботизированного тона.
"""

async def reflect_and_learn(chat_history: List[str], api_key: str):
    if not chat_history or len(chat_history) < 2:
        return
    logger.info("Запуск фонового самообучения JeBoss по итогам разговора...")
    try:
        client = genai.Client(api_key=api_key)
        mem = load_memory()
        dialogue_text = "\n".join(chat_history)

        reflection_prompt = f"""
Ты — модуль памяти и саморазвития JeBoss.
Вот завершившийся разговор пользователя и JeBoss:
---
{dialogue_text}
---
Текущая память:
{json.dumps(mem, ensure_ascii=False)}

Твоя задача — извлечь новые знания и вернуть СТРОГО валидный JSON следующего вида:
{{
  "new_facts": ["факты о пользователе (имя, хобби, проблемы, работа, детали жизни, если он их упоминал)"],
  "learned_slang": ["новые выражения или манера речи пользователя, которые JeBoss может перенять"],
  "key_topics": ["темы, о которых шла речь"],
  "conversation_summary": "краткий итог диалога в 1 предложении для следующего звонка"
}}
Не пиши ничего кроме чистого JSON!
"""
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=reflection_prompt
            )
        )
        text = res.text.strip()
        if text.startswith("```json"):
            text = text[7:-3].strip()
        elif text.startswith("```"):
            text = text[3:-3].strip()

        data = json.loads(text)
        
        for f in data.get("new_facts", []):
            if f and f not in mem["facts_about_user"]:
                mem["facts_about_user"].append(f)
        for s in data.get("learned_slang", []):
            if s and s not in mem["learned_vocabulary"]:
                mem["learned_vocabulary"].append(s)
        for t in data.get("key_topics", []):
            if t and t not in mem["inside_jokes_and_topics"]:
                mem["inside_jokes_and_topics"].append(t)
        if data.get("conversation_summary"):
            mem["last_conversation_summary"] = data["conversation_summary"]

        save_memory(mem)
        logger.info("JeBoss успешно самообучился и обновил базу знаний!")
    except Exception as e:
        logger.error(f"Reflection error: {e}")

if os.path.exists("index.html"):
    @app.get("/")
    async def serve_index():
        return FileResponse("index.html")

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "JeBoss Self-Learning Live Server"}

recognizer = sr.Recognizer()
recognizer.dynamic_energy_threshold = False
recognizer.energy_threshold = 100

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

    dynamic_prompt = build_dynamic_prompt()

    gemini_client = genai.Client(api_key=api_key)
    chat = gemini_client.chats.create(
        model="gemini-3.5-flash-lite",
        config={"system_instruction": dynamic_prompt}
    )

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

    except WebSocketDisconnect:
        logger.info("Клиент отключился, запускаем саморефлексию")
    except Exception as e:
        logger.error(f"WS error: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass
        if conversation_history and api_key:
            asyncio.create_task(reflect_and_learn(conversation_history, api_key))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
