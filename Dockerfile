# Многоэтапная оптимизированная сборка чистого Rust бинарника
FROM rust:1.80-slim as builder

WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src

# Сборка максимального релизного бинарника
RUN cargo build --release

# Финальный минималистичный контейнер (только бинарник и статика)
FROM debian:bookworm-slim
WORKDIR /app

RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/jeboss-live /app/jeboss-live
COPY index.html /app/index.html
COPY manifest.json /app/manifest.json
COPY sw.js /app/sw.js
COPY apple-touch-icon.png /app/apple-touch-icon.png
COPY icon-192.png /app/icon-192.png
COPY icon-512.png /app/icon-512.png

EXPOSE 8000
ENV HOST=0.0.0.0
ENV PORT=8000

CMD [ "/app/jeboss-live" ]
