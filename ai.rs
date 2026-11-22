use reqwest::Client;
use serde_json::json;
use tracing::{error, info};
use crate::services::memory::{load_memory, save_memory, Memory};

pub async fn ask_gemini(
    client: &Client,
    api_key: &str,
    system_prompt: &str,
    user_msg: &str,
    model: &str,
) -> Option<String> {
    let url = format!(
        "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent?key={}",
        model, api_key
    );

    let payload = json!({
        "system_instruction": {
            "parts": [{ "text": system_prompt }]
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

pub async fn reflect_and_learn(
    client: &Client,
    api_key: &str,
    model: &str,
    memory_path: &str,
    history: &[String],
) {
    if history.len() < 2 || api_key.is_empty() {
        return;
    }

    info!("Starting background reflection and self-learning loop...");
    let mut mem: Memory = load_memory(memory_path);
    let dialogue = history.join("\n");

    let reflection_prompt = format!(
r#"
Ты — модуль памяти и саморазвития JeBoss.
Вот завершившийся разговор пользователя и JeBoss:
---
{}
---
Текущая память:
{}

Твоя задача — извлечь новые знания и вернуть СТРОГО валидный JSON:
{{
  "new_facts": ["факты о пользователе (имя, хобби, проблемы, работа, детали жизни, если он их упоминал)"],
  "learned_slang": ["новые выражения или манера речи пользователя, которые JeBoss может перенять"],
  "key_topics": ["темы, о которых шла речь"],
  "conversation_summary": "краткий итог диалога в 1 предложении для следующего звонка"
}}
Не пиши ничего кроме чистого JSON!
"#,
        dialogue,
        serde_json::to_string(&mem).unwrap_or_default()
    );

    let url = format!(
        "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent?key={}",
        model, api_key
    );

    let payload = json!({
        "contents": [{
            "parts": [{ "text": reflection_prompt }]
        }]
    });

    if let Ok(res) = client.post(&url).json(&payload).send().await {
        if let Ok(val) = res.json::<serde_json::Value>().await {
            if let Some(text) = val["candidates"][0]["content"]["parts"][0]["text"].as_str() {
                let mut clean_text = text.trim();
                if clean_text.starts_with("```json") {
                    clean_text = clean_text.trim_start_matches("```json").trim_end_matches("```").trim();
                } else if clean_text.starts_with("```") {
                    clean_text = clean_text.trim_start_matches("```").trim_end_matches("```").trim();
                }

                if let Ok(parsed) = serde_json::from_str::<serde_json::Value>(clean_text) {
                    if let Some(facts) = parsed["new_facts"].as_array() {
                        for f in facts {
                            if let Some(s) = f.as_str() {
                                if !mem.facts_about_user.contains(&s.to_string()) {
                                    mem.facts_about_user.push(s.to_string());
                                }
                            }
                        }
                    }
                    if let Some(slang) = parsed["learned_slang"].as_array() {
                        for s in slang {
                            if let Some(w) = s.as_str() {
                                if !mem.learned_vocabulary.contains(&w.to_string()) {
                                    mem.learned_vocabulary.push(w.to_string());
                                }
                            }
                        }
                    }
                    if let Some(topics) = parsed["key_topics"].as_array() {
                        for t in topics {
                            if let Some(w) = t.as_str() {
                                if !mem.inside_jokes_and_topics.contains(&w.to_string()) {
                                    mem.inside_jokes_and_topics.push(w.to_string());
                                }
                            }
                        }
                    }
                    if let Some(summary) = parsed["conversation_summary"].as_str() {
                        mem.last_conversation_summary = summary.to_string();
                    }

                    save_memory(memory_path, &mem);
                    info!("JeBoss memory successfully updated via self-learning loop!");
                } else {
                    error!("Failed to parse reflection JSON: {}", clean_text);
                }
            }
        }
    }
}
