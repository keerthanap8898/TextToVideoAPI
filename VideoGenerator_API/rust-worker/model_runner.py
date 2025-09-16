# TODO: Future features roadmap — tagged by software quality attribute
# (1) [Reliability]
#   - Honor server rate-limit headers (Retry-After, X-RateLimit-*) and back off accordingly.
#   - Local adaptive throttling based on CPU/memory, file descriptors, and event-loop lag.
#   - Network-aware throttling using measured RTT/jitter/packet loss and bandwidth caps.
#   - Work-size throttling by prompt complexity/length, estimated cost, estimated output size.
#   - Circuit breaker & bulkhead patterns to isolate failing endpoints/pools.
#   - Hedged/parallel requests with cancellation to cut tail latency.
#   - Idempotency keys for safe retries on non-GET operations.
#   - Retries with exponential backoff + configurable timeouts/limits.
#   - Scheduling/prioritization by subscription tier/user group.
#
# (2) [Maintainability]
#   - Request/response templating with versioned schemas and sane defaults.
#   - Centralized config via typed settings and environment overlays.
#   - Lint/format hooks and static analysis (mypy, ruff) gated in CI.
#   - Clear layering (transport → client → domain) and ADRs for key decisions.
#
# (3) [Readability]
#   - Consistent naming, docstrings, and public API examples.
#   - Small, single-purpose functions; prefer early returns to deep nesting.
#   - Inline rationale where trade-offs are non-obvious.
#
# (4) [Reusability]
#   - Pluggable strategy interfaces (auth, retry, backoff, serialization).
#   - Extractable client library with minimal framework deps.
#   - Reusable CLI + SDK sharing the core execution engine.
#
# (5) [Testability]
#   - Deterministic unit tests w/ fake clocks, fixtures, golden files.
#   - Contract tests against mock servers (OpenAPI/JSON Schema).
#   - Fault injection (timeouts, 5xx, partial reads) and chaos tests.
#   - Repro command to replay a failing job from stored inputs.
#
# (6) [Portability]
#   - OS-agnostic file/network ops; avoid platform-specific syscalls.
#   - Multi-arch containers (linux/amd64 + arm64); devcontainers.
#   - No hard vendor lock-in; swappable adapters for storage/queue.
#
# (7) [Scalability]
#   - Priority queues with weighted-fair scheduling by tenant/tier.
#   - Concurrency limits per-tenant, per-endpoint, and global.
#   - Sharded workers + horizontal scale; work stealing between queues.
#   - Batching/coalescing for small requests; streaming for large payloads.
#   - Async/await non-blocking I/O (where applicable).
#
# (8) [Performance / Efficiency]
#   - HTTP/2(/3) with connection pooling/keep-alives.
#   - Zero-copy streaming; multipart & resumable transfers.
#   - Async I/O throughout; producer backpressure.
#   - Metrics-driven tuning (p99 latency, CPU%, mem/req, GB transferred).
#
# (9) [Security]
#   - Pluggable auth (OAuth2, API keys, mTLS), scoped tokens, key rotation.
#   - Secrets management via env/keystore; never log secrets.
#   - Request/response validation; strict content-type allowlists.
#   - TLS enforcement, optional cert pinning; SBOM + dependency scanning.
#
# (10) [Usability]
#   - Human-friendly errors with remediation hints and correlation IDs.
#   - CLI progress, dry-run mode, and rich `--help`; ergonomic SDK defaults.
#   - Accessible logs (structured + pretty) with minimal boilerplate.
#
# (11) [Flexibility / Extensibility]
#   - Extension hooks (pre/post request, admission controllers, transformers).
#   - Policy-as-code (simple rules or OPA) for routing/quotas.
#   - Feature flags with gradual rollout per tenant.
#
# (12) [Interoperability]
#   - Multiple content types (JSON, NDJSON, XML, CSV, multipart).
#   - OpenAPI spec for the client; gRPC/REST adapters.
#   - Proxy support, custom DNS resolvers, corporate CA bundles.
#
# (13) [Robustness]
#   - Dead-letter queue for permanently failing jobs; quarantine + review.
#   - Input sanitation and size limits; graceful degradation paths.
#
# (14) [Modularity]
#   - Clear module boundaries: core, transport, auth, scheduling, storage.
#   - Dependency inversion for side-effects (clock, RNG, network).
#   - Replaceable storage backends (in-memory, sqlite, redis, s3-like).
#
# (15) [Traceability / Auditability]
#   - Structured logs with Request-ID/Trace-ID and user/tenant tags.
#   - Metrics & alerts (rate, errors, saturation) with SLO reports.
#   - Audit trail of config changes, retries, and policy decisions.
#
# (16) [Adaptability]
#   - Hot-reload of configs/limits without restart.
#   - Auto-tune concurrency based on live error/latency budgets.
#   - Pluggable cost models and quota strategies per tenant.
#
#===============================================================================
#===============================================================================


import os
import sys
import json
import time
import base64
import redis
from pathlib import Path
from urllib import request, error



# Reads environment settings for Redis connection, output directory, & MinIO usage.
# Redis is expected to be reachable at `REDIS_URL` & contain job metadata hashes
# under keys like `job:<id>`. The job hash must contain at least a 'prompt' field,
# may optionally include 'seconds', 'quality', & 'resolution' fields.
# The resulting video URL is written back to the same hash under the 'result_url' field.
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
OUT_DIR    = Path(os.getenv("OUT_DIR", "/data/videos"))
USE_MINIO  = os.getenv("USE_MINIO", "false").lower() == "true"

# Reads environment settings for the MinIO upload (if `USE_MINIO=true`).
# MinIO is expected to be reachable at `MINIO_ENDPOINT` with the given access/secret keys.
# The target bucket must already exist. If not using MinIO, output files are left on disk under `OUT_DIR` to be served via the API's `/videos` static route.
MINIO_EP=os.getenv("MINIO_ENDPOINT","http://minio:9000")
MINIO_KEY=os.getenv("MINIO_ACCESS_KEY","minioadmin")
MINIO_SEC=os.getenv("MINIO_SECRET_KEY","minioadmin")
MINIO_BUCKET=os.getenv("MINIO_BUCKET","videos")


def maybe_upload(outfile: Path) -> str:
    # Uploads the finished MP4 either to MinIO (when `USE_MINIO=true`) or leaves it on disk to be served from `/videos`. 
    # MinIO uploads include a presigned URL so the API can hand back a direct link.
    if USE_MINIO:
        import boto3
        s3 = boto3.client("s3", endpoint_url=MINIO_EP,
            aws_access_key_id=MINIO_KEY, aws_secret_access_key=MINIO_SEC)
        s3.upload_file(str(outfile), MINIO_BUCKET, outfile.name)
        url = s3.generate_presigned_url("get_object",
                Params={"Bucket": MINIO_BUCKET, "Key": outfile.name},
                ExpiresIn=3600*24)
        return url
    # default: serve via API from PVC
    base = os.getenv("VIDEO_BASE_URL","/videos")
    return f"{base}/{outfile.name}"


def main():
    # Grabs the job id from argv, pulls job metadata from Redis,
    # Normalizes the 'prompt'/'seconds'/'quality'/'resolution', etc. fields, & dispatches synthesis via `generate_with_mochi()`,
    # Stores the resulting download URL back into the same Redis hash & finally the output files land under the configured `OUT_DIR`.
    if len(sys.argv) < 2:
        raise RuntimeError("Usage: model_runner.py <job-id>")
    jid = sys.argv[1]
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    job = r.hgetall(f"job:{jid}")
    prompt = job.get("prompt","")
    if not prompt:
        raise RuntimeError("Job is missing required 'prompt' field")

    # Ensure output directory exists.
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    outfile = OUT_DIR / f"{jid}.mp4"

    # Normalize & apply optional parameters.
    seconds = _coerce_int(job.get("seconds"), default=6)
    quality = _clean_str(job.get("quality"), default="medium")
    resolution = _clean_str(job.get("resolution"), default="576p")
    print(f"Generating job {jid}: prompt='{prompt}' seconds={seconds} quality='{quality}' resolution='{resolution}' -> {outfile}", file=sys.stderr)

    # Dispatch the request to generate the video via the Mochi API.
    generate_with_mochi(prompt, seconds, quality, resolution, outfile)
    url = maybe_upload(outfile)
    r.hset(f"job:{jid}", mapping={"result_url": url})


# Reads environment settings for the OpenAI/Mochi endpoint, keys, polling cadence, & known resolution presets.
API_BASE = os.getenv("MOCHI_API_BASE", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("MOCHI_API_KEY")
OPENAI_ORG = os.getenv("OPENAI_ORG") or os.getenv("OPENAI_ORGANIZATION")
OPENAI_PROJECT = os.getenv("OPENAI_PROJECT")
MODEL_ID = os.getenv("MOCHI_MODEL", "mochi-1-preview") # The only available model as of mid-2024.
POLL_INTERVAL = float(os.getenv("MOCHI_POLL_INTERVAL", "2.0")) # seconds
POLL_TIMEOUT = float(os.getenv("MOCHI_POLL_TIMEOUT", "300")) # seconds
RESOLUTION_MAP = {
    "360p": "640x360",
    "480p": "854x480",
    "576p": "1024x576",
    "720p": "1280x720",
    "1080p": "1920x1080",
} # known presets

def generate_with_mochi(prompt: str, seconds: int, quality: str, resolution: str, outfile: Path) -> None:
    # Uses the Mochi API to generate a video based on the given prompt & parameters.
    # Polls the API until the job is complete, then downloads the resulting MP4 & writes it to the specified `outfile` path.
    # Raises RuntimeError on any failure.
    if not API_KEY:
        raise RuntimeError("OPENAI_API_KEY or MOCHI_API_KEY must be set for mochi generation")

    # Construct the initial request payload.
    # See https://platform.openai.com/docs/models/mochi-1-preview for payload details.
    payload = {
        "model": MODEL_ID,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt or "Generate a short cinematic establishing shot.",
                    }
                ],
            }
        ],
        "video": {
            "format": "mp4",
        },
    }

    # If `resolution` &/or `quality` is not a known preset, &/or `seconds` is not a positive integer, default values are passed through.
    # Note that request-user & request-device specifications are not currently supported - TODO as part of future-updates & features.
    # Hence, normalize & apply optional parameters.
        # - `seconds` is an integer duration (default 6)
        # - `quality` is one of "low", "medium", "high" (default "medium")
        # - `resolution` is one of the known presets (default "576p")
    if seconds:
        payload["video"]["duration"] = float(seconds)
    if quality:
        payload["video"]["quality"] = quality.lower()
    resolution_key = (resolution or "").lower()
    resolution_value = RESOLUTION_MAP.get(resolution_key, resolution if resolution_key else "")
    if resolution_value:
        payload["video"]["resolution"] = resolution_value

    # Dispatch the request to create a new video generation response.
    # Poll the response status until it is "completed" or a terminal failure state.
    # On success, download the resulting MP4 & write it to `outfile`.
    # On failure, raise RuntimeError with details.
    response = _post_json("responses", payload)
    response_id = response.get("id")
    status = response.get("status")
    result = response
    start = time.time()

    # Poll until complete, failed, cancelled, or errored.
    while status and status not in {"completed", "failed", "cancelled", "errored"}:
        if time.time() - start > POLL_TIMEOUT:
            raise RuntimeError("mochi generation timed out")
        time.sleep(POLL_INTERVAL)
        if not response_id:
            break
        result = _get_json(f"responses/{response_id}")
        status = result.get("status")
        print(f"mochi generation status: {status}", file=sys.stderr)

    # If the final status is not "completed", raise an error with details.
    if status != "completed":
        message = result.get("error") or result
        raise RuntimeError(f"mochi generation failed: {message}")

    # Locate the video artifact in the response, which may be a file ID, direct URL, or base64-encoded string.
    # Download the MP4 data & write it to `outfile`.
    locator = _find_video_locator(result)
    if not locator:
        raise RuntimeError("mochi generation completed but no video artifact was returned")
    mode, value = locator
    if mode == "file_id":
        blob = _download_file(value)
    elif mode == "url":
        blob = _download_url(value)
    elif mode == "b64":
        blob = base64.b64decode(value)
    else:
        raise RuntimeError("Unknown video artifact type from mochi response")
    with open(outfile, "wb") as f:
        f.write(blob)


def _headers(json_body: bool = False) -> dict:
    # Constructs the standard headers for API requests, including authorization & content type.
    # TODO - set up OpenAI API &/or mochi API key rotation if needed.
    if not API_KEY:
        raise RuntimeError("OPENAI_API_KEY or MOCHI_API_KEY must be set for mochi generation")

    # Common headers for all requests.
    headers = {"Authorization": f"Bearer {API_KEY}"}
    if OPENAI_ORG:
        headers["OpenAI-Organization"] = OPENAI_ORG
    if OPENAI_PROJECT:
        headers["OpenAI-Project"] = OPENAI_PROJECT
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def _api_url(path: str) -> str:
    # Constructs the full API URL for a given path.
    return f"{API_BASE}/{path.lstrip('/')}"


def _post_json(path: str, payload: dict) -> dict:
    # Sends a POST request with a JSON payload to the specified API path & returns the JSON response.
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(_api_url(path), data=data, headers=_headers(True), method="POST")
    return _read_json(req)


def _get_json(path: str) -> dict:
    # Sends a GET request to the specified API path & returns the JSON response.
    req = request.Request(_api_url(path), headers=_headers(), method="GET")
    return _read_json(req)


def _download_file(file_id: str) -> bytes:
    # Downloads a file from the API given its file ID & returns the raw bytes.
    # The file ID is expected to be in the format "file-xxxx".
    if not file_id.startswith("file-"):
        raise RuntimeError(f"Invalid file ID: {file_id}")

    # The `files/{id}/content` endpoint returns the actual binary payload for a file.
    # Each `content[i].asset` entry in the response points at the MP4 via a short‑lived, presigned URL;
    # the file is downloaded & saved locally &/or pushed into other persistent storage resources.
    req = request.Request(_api_url(f"files/{file_id}/content"), headers=_headers(), method="GET")
    return _read_bytes(req)


def _download_url(url: str) -> bytes:
    # Downloads a file from a direct URL & returns the raw bytes.
    try:
        with request.urlopen(url, timeout=300) as resp:
            return resp.read()
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
        raise RuntimeError(f"HTTP {exc.code} error downloading video asset: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Failed to download video asset: {exc}") from exc


def _read_json(req: request.Request) -> dict:
    # Reads & parses a JSON response from the given request, raising RuntimeError on failure.
    raw = _read_bytes(req)
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("Invalid JSON response from mochi API") from exc


def _read_bytes(req: request.Request) -> bytes:
    # Reads raw bytes from the given request, raising RuntimeError on failure.
    try:
        with request.urlopen(req, timeout=300) as resp:
            return resp.read()
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
        raise RuntimeError(f"HTTP {exc.code} error from mochi API: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Failed to reach mochi API: {exc}") from exc


def _find_video_locator(payload: object):
    # Recursively searches the given payload for a video locator, which can be:
        # - A base64-encoded string under "b64_json"
        # - A file ID under "file_id" or "id" (if it starts with "file-")
        # - A direct URL under "url" (if it starts with "http")
    # Returns a tuple of (mode, value) or None if not found.
    if isinstance(payload, dict):
        if "b64_json" in payload and isinstance(payload["b64_json"], str):
            return "b64", payload["b64_json"]
        if "file_id" in payload and isinstance(payload["file_id"], str):
            return "file_id", payload["file_id"]
        if "id" in payload and str(payload.get("id", "")).startswith("file-"):
            return "file_id", payload["id"]
        if "url" in payload and isinstance(payload["url"], str) and payload["url"].startswith("http"):
            return "url", payload["url"]
        for key in ("video", "videos", "file", "output", "content", "data", "items", "result"):
            if key in payload:
                locator = _find_video_locator(payload[key])
                if locator:
                    return locator
    elif isinstance(payload, list):
        for item in payload:
            locator = _find_video_locator(item)
            if locator:
                return locator
    return None


def _coerce_int(value, default: int) -> int:
    # Attempts to coerce the given value to an integer, returning the default if it is None, empty, "none", or invalid.
    try:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return int(value)
        text = str(value).strip()
        if not text or text.lower() == "none":
            return default
        return int(float(text))
    except (TypeError, ValueError):
        return default


def _clean_str(value, default: str = "") -> str:
    # Cleans the given value by stripping whitespace & returning the default if it is None, empty, or "none".
    if value is None:
        return default
    text = str(value).strip()
    if not text or text.lower() == "none":
        return default
    return text

if __name__ == "__main__":
    main()
