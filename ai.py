import asyncio
import json
import logging
from typing import List, Optional
from google import genai
from app.core.config import config
from app.services.memory import load_memory, save_memory, build_dynamic_prompt

logger = logging.getLogger("jeboss.ai")

class GeminiService:
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    def create_chat_session(self):
        if not self.client:
            raise ValueError("GEMINI_API_KEY не установлен!")
        prompt = build_dynamic_prompt()
        return self.client.chats.create(
            model=config.GEMINI_MODEL,
            config={"system_instruction": prompt}
        )

    async def reflect_and_learn(self, chat_history: List[str]):
        """Фоновый самообучающийся анализ диалога после завершения звонка"""
        if not chat_history or len(chat_history) < 2 or not self.client:
            return

        logger.info("Запуск фонового самообучения JeBoss по итогам разговора...")
        try:
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

Твоя задача — извлечь новые знания и вернуть СТРОГО валидный JSON:
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
                lambda: self.client.models.generate_content(
                    model=config.GEMINI_MODEL,
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
            logger.info("JeBoss успешно самообучился и сохранил новые факты!")
        except Exception as e:
            logger.error(f"Reflection error: {e}")

gemini_service = GeminiService()
