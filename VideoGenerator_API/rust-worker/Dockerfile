# Build rust binary
FROM rust:1.79 as build
WORKDIR /src
COPY Cargo.toml /src/
COPY src /src/src
RUN cargo build --release

# Runtime with CUDA-capable base (can switch to full CUDA image when wiring the model)
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04
RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /src/target/release/videogen_worker /usr/local/bin/videogen_worker
COPY model_runner.py /app/model_runner.py
# Install Python deps for MinIO only (model deps come later)
RUN pip3 install --no-cache-dir boto3 redis
ENV REDIS_URL=redis://redis:6379/0 OUT_DIR=/data/videos
CMD ["videogen_worker"]
