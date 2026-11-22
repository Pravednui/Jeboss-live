use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine;
use reqwest::Client;
use tracing::error;

/// Вычисление громкости (RMS) 16-bit PCM чанка для детекции активности речи (VAD)
pub fn detect_voice_activity(chunk: &[u8], threshold: u64) -> (bool, u64) {
    if chunk.len() < 320 {
        return (false, 0);
    }
    let samples_count = chunk.len() / 2;
    let mut sum_vol: u64 = 0;
    for i in 0..samples_count {
        let val = i16::from_le_bytes([chunk[i * 2], chunk[i * 2 + 1]]);
        sum_vol += val.abs() as u64;
    }
    let avg_vol = sum_vol / (samples_count as u64);
    (avg_vol > threshold, avg_vol)
}

/// Распознавание речи через Google Speech API v2
pub async fn recognize_speech(client: &Client, pcm_bytes: &[u8]) -> Option<String> {
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

    let url = "http://www.google.com/speech-api/v2/recognize?client=chromium&lang=ru-RU&key=AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw&pFilter=0";
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

/// Высокоскоростной синтез речи с возвратом Base64 MP3
pub async fn synthesize_speech(client: &Client, text: &str) -> Option<String> {
    let encoded = urlencoding::encode(text);
    let url = format!(
        "https://translate.google.com/translate_tts?ie=UTF-8&q={}&tl=ru&client=tw-ob",
        encoded
    );
    match client.get(&url).send().await {
        Ok(res) => {
            if let Ok(bytes) = res.bytes().await {
                if !bytes.is_empty() {
                    return Some(BASE64.encode(bytes));
                }
            }
        }
        Err(e) => {
            error!("TTS error: {}", e);
        }
    }
    None
}
