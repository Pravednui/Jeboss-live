mod core;
mod services;

use axum::{
    body::Body,
    extract::ws::{Message, WebSocket, WebSocketUpgrade},
    extract::Path,
    http::{header, StatusCode},
    response::{Html, IntoResponse, Json, Response},
    routing::get,
    Router,
};
use futures_util::{SinkExt, StreamExt};
use reqwest::Client;
use serde_json::json;
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::net::TcpListener;
use tower_http::cors::CorsLayer;
use tracing::{error, info};

use crate::core::config::Config;
use crate::services::ai::{ask_gemini, reflect_and_learn};
use crate::services::audio::{detect_voice_activity, recognize_speech, synthesize_speech};
use crate::services::memory::{build_dynamic_prompt, load_memory};

pub struct AppState {
    pub config: Config,
    pub http_client: Client,
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();
    let config = Config::from_env();

    let addr_str = format!("{}:{}", config.host, config.port);
    let addr: SocketAddr = addr_str
        .parse()
        .unwrap_or_else(|_| SocketAddr::from(([0, 0, 0, 0], 8000)));

    let state = Arc::new(AppState {
        config: config.clone(),
        http_client: Client::builder().build().unwrap_or_default(),
    });

    let app = Router::new()
        .route("/", get(serve_index))
        .route("/health", get(health_check))
        .route("/manifest.json", get(serve_manifest))
        .route("/sw.js", get(serve_sw))
        .route("/apple-touch-icon.png", get(serve_apple_icon))
        .route("/icon-192.png", get(serve_icon_192))
        .route("/icon-512.png", get(serve_icon_512))
        .route("/ws/live", get(ws_handler))
        .route("/:filename", get(serve_static_fallback))
        .layer(CorsLayer::permissive())
        .with_state(state);

    info!("⚡ JeBoss Native Rust Server running on http://{}", addr);
    let listener = match TcpListener::bind(addr).await {
        Ok(l) => l,
        Err(e) => {
            error!("Failed to bind to {}: {}", addr, e);
            return;
        }
    };
    axum::serve(listener, app).await.unwrap();
}

async fn serve_index() -> impl IntoResponse {
    let candidates = ["index.html", "static/index.html"];
    for path in &candidates {
        if let Ok(content) = tokio::fs::read_to_string(path).await {
            return Html(content).into_response();
        }
    }
    Html("<h1>JeBoss Native Rust Server is Running</h1>").into_response()
}

async fn health_check() -> impl IntoResponse {
    Json(json!({
        "status": "ok",
        "service": "JeBoss Native Rust Server",
        "runtime": "Rust / Axum / Tokio",
        "version": "2.0.0"
    }))
}

async fn serve_file_with_mime(paths: &[&str], mime_type: &'static str) -> Response {
    for p in paths {
        if let Ok(bytes) = tokio::fs::read(p).await {
            return Response::builder()
                .header(header::CONTENT_TYPE, mime_type)
                .body(Body::from(bytes))
                .unwrap();
        }
    }
    StatusCode::NOT_FOUND.into_response()
}

async fn serve_manifest() -> impl IntoResponse {
    serve_file_with_mime(&["manifest.json", "static/manifest.json"], "application/json").await
}

async fn serve_sw() -> impl IntoResponse {
    serve_file_with_mime(&["sw.js", "static/sw.js"], "application/javascript").await
}

async fn serve_apple_icon() -> impl IntoResponse {
    serve_file_with_mime(&["apple-touch-icon.png", "static/apple-touch-icon.png"], "image/png").await
}

async fn serve_icon_192() -> impl IntoResponse {
    serve_file_with_mime(&["icon-192.png", "static/icon-192.png"], "image/png").await
}

async fn serve_icon_512() -> impl IntoResponse {
    serve_file_with_mime(&["icon-512.png", "static/icon-512.png"], "image/png").await
}

async fn serve_static_fallback(Path(filename): Path<String>) -> impl IntoResponse {
    let local_path = filename.clone();
    let static_path = format!("static/{}", filename);
    let mime = if filename.ends_with(".png") {
        "image/png"
    } else if filename.ends_with(".json") {
        "application/json"
    } else if filename.ends_with(".js") {
        "application/javascript"
    } else {
        "text/plain"
    };
    serve_file_with_mime(&[&local_path, &static_path], mime).await
}

async fn ws_handler(
    ws: WebSocketUpgrade,
    axum::extract::State(state): axum::extract::State<Arc<AppState>>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| handle_socket(socket, state))
}

async fn handle_socket(socket: WebSocket, state: Arc<AppState>) {
    let (mut sender, mut receiver) = socket.split();

    if state.config.gemini_api_key.is_empty() {
        let err = json!({
            "type": "status",
            "text": "Ошибка: GEMINI_API_KEY не задан на сервере!"
        });
        let _ = sender.send(Message::Text(err.to_string())).await;
        return;
    }

    let _ = sender
        .send(Message::Text(
            json!({"type": "status", "text": "В эфире — говори"}).to_string(),
        ))
        .await;

    let mut audio_buffer: Vec<u8> = Vec::new();
    let mut is_speaking = false;
    let mut silence_count = 0;
    let mut conversation_history: Vec<String> = Vec::new();

    let sender = Arc::new(tokio::sync::Mutex::new(sender));

    while let Some(Ok(msg)) = receiver.next().await {
        match msg {
            Message::Binary(chunk) => {
                audio_buffer.extend_from_slice(&chunk);

                let (speaking, _) =
                    detect_voice_activity(&chunk, state.config.vad_rms_threshold);
                if speaking {
                    is_speaking = true;
                    silence_count = 0;
                } else if is_speaking {
                    silence_count += 1;
                }

                let should_trigger = (is_speaking
                    && silence_count >= state.config.vad_silence_chunks
                    && audio_buffer.len() >= state.config.min_audio_bytes)
                    || (audio_buffer.len() >= state.config.max_audio_bytes);

                if should_trigger {
                    let pcm_to_process = std::mem::take(&mut audio_buffer);
                    is_speaking = false;
                    silence_count = 0;

                    let client = state.http_client.clone();
                    let api_key = state.config.gemini_api_key.clone();
                    let model = state.config.gemini_model.clone();
                    let mem_file = state.config.memory_file.clone();
                    let ws_sender = sender.clone();

                    let (tx_history, mut rx_history) = tokio::sync::mpsc::channel::<String>(2);

                    tokio::spawn(async move {
                        if let Some(user_text) = recognize_speech(&client, &pcm_to_process).await {
                            if user_text.trim().len() > 1 {
                                let _ = tx_history.send(format!("Пользователь: {}", user_text)).await;

                                {
                                    let mut s = ws_sender.lock().await;
                                    let _ = s
                                        .send(Message::Text(
                                            json!({
                                                "type": "user_text",
                                                "text": user_text
                                            })
                                            .to_string(),
                                        ))
                                        .await;
                                    let _ = s
                                        .send(Message::Text(
                                            json!({
                                                "type": "status",
                                                "text": "JeBoss отвечает..."
                                            })
                                            .to_string(),
                                        ))
                                        .await;
                                }

                                let mem = load_memory(&mem_file);
                                let dynamic_prompt = build_dynamic_prompt(&mem);

                                if let Some(ai_text) =
                                    ask_gemini(&client, &api_key, &dynamic_prompt, &user_text, &model).await
                                {
                                    let _ = tx_history.send(format!("JeBoss: {}", ai_text)).await;

                                    let lower_user = user_text.to_lowercase();
                                    let should_write = ["напиши", "текстом", "в чат", "скинь текст", "продублируй"]
                                        .iter()
                                        .any(|&w| lower_user.contains(w));

                                    {
                                        let mut s = ws_sender.lock().await;
                                        let _ = s
                                            .send(Message::Text(
                                                json!({
                                                    "type": "ai_text",
                                                    "text": ai_text,
                                                    "show_text": should_write
                                                })
                                                .to_string(),
                                            ))
                                            .await;
                                    }

                                    if let Some(audio_b64) = synthesize_speech(&client, &ai_text).await {
                                        let mut s = ws_sender.lock().await;
                                        let _ = s
                                            .send(Message::Text(
                                                json!({
                                                    "type": "audio_mp3",
                                                    "data": audio_b64
                                                })
                                                .to_string(),
                                            ))
                                            .await;
                                    }

                                    {
                                        let mut s = ws_sender.lock().await;
                                        let _ = s
                                            .send(Message::Text(
                                                json!({
                                                    "type": "status",
                                                    "text": "В эфире — говори"
                                                })
                                                .to_string(),
                                            ))
                                            .await;
                                    }
                                }
                            }
                        }
                    });

                    while let Ok(entry) = rx_history.try_recv() {
                        conversation_history.push(entry);
                    }
                }
            }
            Message::Close(_) => break,
            _ => {}
        }
    }

    if !conversation_history.is_empty() && !state.config.gemini_api_key.is_empty() {
        reflect_and_learn(
            &state.http_client,
            &state.config.gemini_api_key,
            &state.config.gemini_model,
            &state.config.memory_file,
            &conversation_history,
        )
        .await;
    }
}
