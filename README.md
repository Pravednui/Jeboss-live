# JeBoss Live — Модульный голосовой ИИ-компаньон (Python 3)

Полностью переведённая на чистую и модульную архитектуру Python серверная часть голосового Telegram Mini App / iOS PWA компаньона **JeBoss**.

---

## 🏛 Архитектура проекта

```text
JeBoss/
├── app/
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py          # Конфигурация, переменные окружения, константы VAD
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ai.py              # Интеграция с Gemini 3.5 Flash Lite и фоновая рефлексия
│   │   ├── audio.py           # Speech-to-Text (16kHz PCM) и Neural TTS (Edge TTS)
│   │   └── memory.py          # Долговременная память, динамический промпт и словарь
│   └── __init__.py
├── static/                    # Статические ассеты PWA и иконки
│   ├── apple-touch-icon.png
│   ├── icon-192.png
│   ├── icon-512.png
│   ├── manifest.json
│   └── sw.js
├── index.html                 # Живой космический UI с Квантовым Порталом и панелью Gemini
├── server.py                  # Точка входа FastAPI (роуты, WebSockets, статика)
├── requirements.txt           # Только реальные Python-зависимости
├── render.yaml                # Конфигурация развертывания на Render.com
├── Dockerfile                 # Легковесный Docker контейнер на Python 3.11-slim
├── .gitignore                 # Исключение секретов и кэша
└── README.md
```

---

## 🚀 Быстрый запуск

### 1. Локально
```bash
pip install -r requirements.txt
python server.py
```
Сервер запустится на `http://localhost:8000`.

### 2. Развертывание на Render.com
1. Загрузите файлы репозитория в GitHub.
2. В Render создайте **Web Service**:
   - **Runtime**: `Python 3` (или `Docker`)
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn server:app --host 0.0.0.0 --port $PORT`
3. В **Environment Variables** укажите:
   - `GEMINI_API_KEY`: ваш ключ Google AI Studio.
