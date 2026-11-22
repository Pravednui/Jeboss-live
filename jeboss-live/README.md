# JeBoss Live — Голосовой ИИ-компаньон для Telegram

Полноценная система для двустороннего голосового общения в реальном времени с искусственным интеллектом в Telegram Mini App, работающая на **Google Gemini Multimodal Live API**.

---

## 🚀 Архитектура проекта

1. **Frontend (Telegram Mini App)**:
   - Захват аудио с микрофона (PCM 16-bit, 16 000 Гц).
   - WebSocket стриминг на бэкенд.
   - Воспроизведение входящего потокового аудио от Gemini (PCM 16-bit, 24 000 Гц) без задержек через Web Audio API.
   - Поддержка перебивания (Barge-in / Interrupt): если пользователь начинает говорить, ИИ мгновенно останавливает свою речь.

2. **Backend (Python / FastAPI)**:
   - WebSocket endpoint `/ws/live`.
   - Прямой стриминг в **Gemini 2.0 Live WebSocket API** с поддержкой голосовых модальностей.
   - Настроенная личность **JeBoss** (системный промпт, голос `Puck`).

---

## 🛠 Запуск проекта

### 1. Локальный запуск

1. Перейдите в папку проекта:
   ```bash
   cd C:\Users\Pravednui\.gemini\antigravity\scratch\jeboss-live
   ```

2. Создайте файл `.env` на основе `.env.example` и укажите ваш API-ключ Gemini:
   ```env
   GEMINI_API_KEY=ваш_ключ_из_aistudio_google_com
   ```

3. Запустите сервер:
   ```bash
   python server.py
   ```
   Сервер запустится на `http://localhost:8000`.

4. Для работы в Telegram Mini App нужен защищённый адрес **WSS**. Пробросьте порт через **ngrok** или **cloudflared**:
   ```bash
   ngrok http 8000
   ```
   Полученный адрес вида `https://xxxx.ngrok-free.app` вставьте в Telegram BotFather как ссылку на Mini App, либо передайте параметром:
   `https://ваш-сайт.com/?ws=wss://xxxx.ngrok-free.app`

---

## ☁️ Бесплатный деплой в облако (Render / Railway)

1. Загрузите файлы в ваш GitHub-репозиторий.
2. Зайдите на [render.com](https://render.com) -> **New Web Service** -> выберите ваш репозиторий.
3. Укажите:
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn server:app --host 0.0.0.0 --port $PORT`
4. В разделе **Environment Variables** добавьте:
   - `GEMINI_API_KEY`: ваш API ключ.
5. Render выдаст готовый домен с поддержкой HTTPS и WSS (например, `https://jeboss-live.onrender.com`).
6. Укажите этот адрес в BotFather в Telegram.
