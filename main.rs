use axum::{
    extract::ws::{Message, WebSocket, WebSocketUpgrade},
    response::{Html, IntoResponse, Json},
    routing::{get, Router},
};
use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine;
use futures_util::{SinkExt, StreamExt};
use serde_json::json;
use std::env;
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::net::TcpListener;
use tower_http::cors::CorsLayer;

const SYSTEM_PROMPT: &str = r#"
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
"#;

struct AppState {
    http_client: reqwest::Client,
    gemini_api_key: String,
}

#[tokio::main]
async fn main() {
    dotenvy::dotenv().ok();
    tracing_subscriber::fmt::init();

    let gemini_api_key = env::var("GEMINI_API_KEY").unwrap_or_default();
    let port = env::var("PORT").unwrap_or_else(|_| "8000".to_string());
    let addr: SocketAddr = format!("0.0.0.0:{}", port).parse().unwrap();

    let state = Arc::new(AppState {
        http_client: reqwest::Client::new(),
        gemini_api_key,
    });

    let app = Router::new()
        .route("/", get(serve_index))
        .route("/health", get(health_check))
        .route("/ws/live", get(ws_handler))
        .layer(CorsLayer::permissive())
        .with_state(state);

    println!("⚡ JeBoss Rust Server running on http://{}", addr);
    let listener = TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

async fn serve_index() -> impl IntoResponse {
    match tokio::fs::read_to_string("index.html").await {
        Ok(content) => Html(content).into_response(),
        Err(_) => Html("<h1>JeBoss Server is running</h1>").into_response(),
    }
}

async fn health_check() -> impl IntoResponse {
    Json(json!({"status": "ok", "engine": "Rust / Axum"}))
}

async fn ws_handler(
    ws: WebSocketUpgrade,
    axum::extract::State(state): axum::extract::State<Arc<AppState>>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| handle_socket(socket, state))
}

async fn handle_socket(socket: WebSocket, state: Arc<AppState>) {
    let (mut sender, mut receiver) = socket.split();

    if state.gemini_api_key.is_empty() {
        let err_msg = json!({
            "type": "status",
            "text": "Ошибка: GEMINI_API_KEY не задан!"
        });
        let _ = sender.send(Message::Text(err_msg.to_string())).await;
        return;
    }

    let _ = sender.send(Message::Text(
        json!({"type": "status", "text": "В эфире — говори"}).to_string(),
    )).await;

    let mut audio_buffer: Vec<u8> = Vec::new();
    let mut is_speaking = false;
    let mut silence_count = 0;

    let sender = Arc::new(tokio::sync::Mutex::new(sender));

    while let Some(Ok(msg)) = receiver.next().await {
        match msg {
            Message::Binary(chunk) => {
                audio_buffer.extend_from_slice(&chunk);

                // Быстрый анализ громкости (RMS на Rust)
                if chunk.len() >= 320 {
                    let samples_count = chunk.len() / 2;
                    let mut sum_vol: u64 = 0;
                    for i in 0..samples_count {
                        let val = i16::from_le_bytes([chunk[i * 2], chunk[i * 2 + 1]]);
                        sum_vol += val.abs() as u64;
                    }
                    let avg_vol = sum_vol / (samples_count as u64);

                    if avg_vol > 350 {
                        is_speaking = true;
                        silence_count = 0;
                    } else if is_speaking {
                        silence_count += 1;
                    }
                }

                let should_trigger = (is_speaking && silence_count >= 6 && audio_buffer.len() >= 20000)
                    || (audio_buffer.len() >= 64000);

                if should_trigger {
                    let pcm_data = std::mem::take(&mut audio_buffer);
                    is_speaking = false;
                    silence_count = 0;

                    let client = state.http_client.clone();
                    let api_key = state.gemini_api_key.clone();
                    let ws_sender = sender.clone();

                    tokio::spawn(async move {
                        if let Some(user_text) = speech_to_text(&client, &pcm_data).await {
                            if user_text.trim().len() > 1 {
                                {
                                    let mut s = ws_sender.lock().await;
                                    let _ = s.send(Message::Text(json!({
                                        "type": "user_text",
                                        "text": user_text
                                    }).to_string())).await;
                                }

                                if let Some(ai_text) = ask_gemini(&client, &api_key, &user_text).await {
                                    {
                                        let mut s = ws_sender.lock().await;
                                        let _ = s.send(Message::Text(json!({
                                            "type": "ai_text",
                                            "text": ai_text
                                        }).to_string())).await;
                                    }

                                    if let Some(audio_b64) = text_to_speech(&client, &ai_text).await {
                                        let mut s = ws_sender.lock().await;
                                        let _ = s.send(Message::Text(json!({
                                            "type": "audio_mp3",
                                            "data": audio_b64
                                        }).to_string())).await;
                                    }
                                }
                            }
                        }
                    });
                }
            }
            Message::Close(_) => break,
            _ => {}
        }
    }
}

// Быстрый вызов Google Speech Recognition
async fn speech_to_text(client: &reqwest::Client, pcm_bytes: &[u8]) -> Option<String> {
    let mut wav_data = Vec::with_capacity(44 + pcm_bytes.len());
    let data_len = pcm_bytes.len() as u32;
    let file_len = data_len + 36;

    wav_data.extend_from_slice(b"RIFF");
    wav_data.extend_from_slice(&file_len.to_le_bytes());
    wav_data.extend_from_slice(b"WAVEfmt ");
    wav_data.extend_from_slice(&16u32.to_le_bytes());
    wav_data.extend_from_slice(&1u16.to_le_bytes()); // PCM
    wav_data.extend_from_slice(&1u16.to_le_bytes()); // Mono
    wav_data.extend_from_slice(&16000u32.to_le_bytes()); // 16kHz
    wav_data.extend_from_slice(&32000u32.to_le_bytes()); // Byte rate
    wav_data.extend_from_slice(&2u16.to_le_bytes()); // Block align
    wav_data.extend_from_slice(&16u16.to_le_bytes()); // Bits per sample
    wav_data.extend_from_slice(b"data");
    wav_data.extend_from_slice(&data_len.to_le_bytes());
    wav_data.extend_from_slice(pcm_bytes);

    let url = "https://www.google.com/speech-api/v2/recognize?output=json&lang=ru-RU&key=";
    let res = client
        .post(url)
        .header("Content-Type", "audio/l16; rate=16000")
        .body(wav_data)
        .send()
        .await
        .ok()?;

    let body = res.text().await.ok()?;
    for line in body.lines() {
        if let Ok(val) = serde_json::from_str::<serde_json::Value>(line) {
            if let Some(transcript) = val["result"][0]["alternative"][0]["transcript"].as_str() {
                return Some(transcript.to_string());
            }
        }
    }
    None
}

// Запрос в Gemini 3.5 Flash Lite
async fn ask_gemini(client: &reqwest::Client, api_key: &str, user_msg: &str) -> Option<String> {
    let url = format!(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={}",
        api_key
    );

    let payload = json!({
        "system_instruction": {
            "parts": [{ "text": SYSTEM_PROMPT }]
        },
        "contents": [{
            "parts": [{ "text": user_msg }]
        }]
    });

    let res = client.post(&url).json(&payload).send().await.ok()?;
    let val: serde_json::Value = res.json().await.ok()?;
    let reply = val["candidates"][0]["content"]["parts"][0]["text"].as_str()?;
    Some(reply.trim().to_string())
}

// Синтез речи
async fn text_to_speech(client: &reqwest::Client, text: &str) -> Option<String> {
    let url = format!(
        "https://translate.google.com/translate_tts?ie=UTF-8&q={}&tl=ru&client=tw-ob",
        urlencoding::encode(text)
    );
    let bytes = client.get(&url).send().await.ok()?.bytes().await.ok()?;
    Some(BASE64.encode(bytes))
}
