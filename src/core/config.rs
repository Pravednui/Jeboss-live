use std::env;

#[derive(Clone, Debug)]
pub struct Config {
    pub gemini_api_key: String,
    pub host: String,
    pub port: u16,
    pub gemini_model: String,
    pub memory_file: String,
    pub vad_rms_threshold: u64,
    pub vad_silence_chunks: usize,
    pub min_audio_bytes: usize,
    pub max_audio_bytes: usize,
}

impl Config {
    pub fn from_env() -> Self {
        dotenvy::dotenv().ok();
        let gemini_api_key = env::var("GEMINI_API_KEY").unwrap_or_default();
        let host = env::var("HOST").unwrap_or_else(|_| "0.0.0.0".to_string());
        let port = env::var("PORT")
            .ok()
            .and_then(|p| p.parse().ok())
            .unwrap_or(8000);

        Self {
            gemini_api_key,
            host,
            port,
            gemini_model: "gemini-3.5-flash-lite".to_string(),
            memory_file: "memory.json".to_string(),
            vad_rms_threshold: 350,
            vad_silence_chunks: 6,
            min_audio_bytes: 20000,
            max_audio_bytes: 64000,
        }
    }
}
