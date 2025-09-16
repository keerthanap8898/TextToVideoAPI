//! rust_worker.rs — Redis Streams worker using plain XREAD (+ persisted last_id)
//!
//! DELIVERY MODEL: **at-least-once**
//! - We XREAD entries strictly AFTER `last_id` (persisted) and process them.
//! - If we crash after side effects but before persisting the next `last_id`,
//!   the same entry will be seen again on restart → **make handlers idempotent**.
//!
//! STARTUP POSITION:
//! - If a persisted `last_id` exists, resume **exactly** where we left off.
//! - Else we honor JOBS_START_ID: "$" (new-only) or "0-0" (catch-up from earliest).
//!
//! PERSISTENCE & CHECKPOINTS (stronger guarantees):
//! - Before heavy side-effects, we write a **processing checkpoint** keyed by entry_id & jid.
//! - After success, we write a **completed marker** (and job status).
//! - The handler must check existing markers to be **idempotent** across replays.
//!
//! BATCHING & BACKPRESSURE:
//! - Use XREAD COUNT=N to fetch small batches; persist `last_id` as we advance through the batch.
//! - TODO(backpressure): If jobs are large, consider *smaller COUNT* and/or *streaming I/O*
//!   to avoid memory spikes during large payload processing.
//!
//! ERROR HANDLING:
//! - Never `unwrap()` on untrusted payloads; use lossy UTF-8 fallback or keep raw bytes.
//!
//! OFFLINE BEHAVIOR:
//! - With a persisted `last_id`, we resume from the last checkpoint, replaying anything not advanced.
//!
//! RETENTION & TRIMMING (enterprise scale):
//! - We periodically trim the stream by **time watermark** using `XTRIM MINID`.
//! - Default: keep ~120 minutes (TRIM_MINUTES). This is a pragmatic default for text→video
//!   jobs on GPU clusters (e.g., NVIDIA H100/HGX). If your pipeline has long queues or
//!   slow post-processing, consider:
//!     • 30–60 min for high-throughput, low-latency services (better memory profile).
//!     • 180–240+ min for bursty workloads or multi-stage pipelines (safer for audits/replays).
//!   Pick a value that covers your **worst-case redelivery window**, audit needs, and cost.
//!
//! ACCESS CONTROL (TODO):
//! - Configure Redis ACL users and commands; use TLS for cross-network traffic.
//! - Enforce network policies (firewalls/VPC/Security Groups).
//! - Consider per-tenant auth and scoping if multiplexing many users/groups.
//!
//! TELEMETRY, LOGGING & OBSERVABILITY (TODO):
//! - Metrics: xread.count, jobs.processed, jobs.failed, handler.latency.{p50,p95,p99},
//!   loop.lag_ms, stream.approx_queue_depth (estimate via last_id deltas / XINFO STREAM).
//! - Correlation IDs in logs: include both {entry_id, jid} for traceability.
//!
//! PERFORMANCE & RELIABILITY STRATEGIES (TODO):
//! - Timeouts & circuit breaking: add subprocess timeouts (wait_timeout crate / tokio),
//!   network I/O timeouts, retry with **exponential backoff + jitter**. If downstream flaps,
//!   shed load temporarily with a circuit breaker.
//! - Connection management: hold a long-lived Redis connection; on failure, **reconnect with backoff**.
//!   If using TLS, Sentinel, or Cluster, wire up failover/retry logic accordingly.
//!
//! MAJOR CHANGES (vs. naive XREAD with ">"):
//! - Use `XREAD ... STREAMS <stream> <last_id>` (NOT ">") and persist `last_id`.
//! - Add **processing checkpoint** & **completed marker** for idempotency and stronger guarantees.
//! - Decode fields defensively (no unwrap); tolerate malformed payloads without crashing.
//! - Batch with COUNT, trim by time with MINID, and add comprehensive comments/TODOs for operability.
//!
//! SIMPLER ALTERNATIVE (if complexity is unnecessary):
//! - Start with `$` (new-only) and skip persistence. This is simplest but **drops** entries while offline,
//!   provides only best-effort processing, and is not suitable for most production pipelines.

use anyhow::{bail, Context, Result};
use redis::Commands;
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

/// Keys & defaults
const LAST_ID_KEY: &str = "videogen:last_id"; // persisted last seen stream ID
const PROCESSING_KEY_NS: &str = "videogen:processing"; // Namespace for processing checkpoints
const COMPLETED_KEY_NS: &str = "videogen:completed"; // Namespace for completed markers
const PROCESSING_TTL_SECS: i64 = 24 * 60 * 60; // expire processing markers after 24h
const COMPLETED_TTL_SECS: u64 = 7 * 24 * 60 * 60; // keep completion markers for a week
const RETRY_BACKOFF_ON_ERROR_MS: u64 = 250; // small pause before retrying a failing job

fn main() -> Result<()> {
    // ---------- Configuration ----------
    let redis_url = std::env::var("REDIS_URL").unwrap_or_else(|_| "redis://redis:6379/0".into());
    let stream_name = std::env::var("JOBS_STREAM").unwrap_or_else(|_| "videogen:jobs".into());

    // Startup position:
    //   "$"    → new-only (skip backlog)
    //   "0-0"  → catch-up from earliest
    // If LAST_ID_KEY exists, we ignore JOBS_START_ID and resume from persisted value.
    let startup_id = std::env::var("JOBS_START_ID").unwrap_or_else(|_| "$".into());

    // XREAD tuning
    let block_ms: u64 = std::env::var("XREAD_BLOCK_MS")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(5000);
    let count: usize = std::env::var("XREAD_COUNT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(10);
    // TODO(backpressure): For large jobs, consider setting XREAD_COUNT to 1–3 and stream payloads to reduce memory spikes.

    // Trimming policy: keep ~TRIM_MINUTES minutes of history by MINID time watermark.
    let trim_minutes: u64 = std::env::var("TRIM_MINUTES")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(120);
    // Trim cadence (how often we attempt trimming)
    let trim_every_n_loops: u64 = std::env::var("TRIM_EVERY_LOOPS")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(80);

    // Subprocess timeout (seconds) — implement with wait_timeout/tokio in real code.
    let runner_timeout_s: u64 = std::env::var("RUNNER_TIMEOUT_S")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(600);

    // ---------- Connection (long-lived; reconnect with backoff on failure) ----------
    let client = redis::Client::open(redis_url)?;
    let mut con = connect_with_backoff(&client)?;

    // ---------- Load persisted last_id or use startup_id ----------
    let mut last_id = redis_get_string(&mut con, LAST_ID_KEY)?.unwrap_or(startup_id);

    // simple loop counters for periodic tasks
    let mut loop_count: u64 = 0;

    loop {
        loop_count += 1;

        // --- XREAD: fetch up to COUNT entries after last_id; BLOCK up to block_ms ---
        let resp = redis::cmd("XREAD")
            .arg("BLOCK")
            .arg(block_ms)
            .arg("COUNT")
            .arg(count)
            .arg("STREAMS")
            .arg(&stream_name)
            .arg(&last_id) // strictly AFTER this ID
            .query::<redis::Value>(&mut con);

        let value = match resp {
            Ok(v) => v,
            Err(e) => {
                eprintln!("[xread.error] err={e} last_id={last_id}");
                // reconnect with backoff, then continue loop
                con = connect_with_backoff(&client)?;
                continue;
            }
        };

        // RESPONSE SHAPE: [[stream, [[id, [k,v,k,v,...]], ...]]]
        if let redis::Value::Array(streams) = value {
            let mut advanced_any = false;
            let mut had_batch_error = false;

            'stream_loop: for s in streams {
                let Some(parts) = as_bulk(&s) else { continue };
                if parts.len() != 2 {
                    continue;
                }

                let entries = &parts[1];
                let Some(entries_bulk) = as_bulk(entries) else {
                    continue;
                };

                // Telemetry (TODO): increment xread.count by entries_bulk.len()
                for entry in entries_bulk {
                    let Some(ev) = as_bulk(entry) else { continue };

                    // ----- Extract entry_id -----
                    let entry_id = ev
                        .get(0)
                        .and_then(as_data)
                        .map(|b| {
                            String::from_utf8(b.to_vec())
                                .unwrap_or_else(|_| String::from_utf8_lossy(b).into_owned())
                        })
                        .unwrap_or_default();

                    if entry_id.is_empty() {
                        // malformed; skip but do NOT advance last_id
                        eprintln!("[entry.malformed] missing id; last_id={last_id}");
                        continue;
                    }

                    // ----- Extract fields -----
                    // Expect a Bulk([k,v,k,v,...]) at ev[1]. We use lossy UTF-8 to avoid panics.
                    let mut jid = String::new();
                    if let Some(kv) = ev.get(1).and_then(as_bulk) {
                        for i in (0..kv.len()).step_by(2) {
                            if let (Some(k), Some(v)) = (kv.get(i), kv.get(i + 1)) {
                                if let (Some(kb), Some(vb)) = (as_data(k), as_data(v)) {
                                    if kb == b"id" {
                                        jid = String::from_utf8(vb.to_vec()).unwrap_or_else(|_| {
                                            String::from_utf8_lossy(vb).into_owned()
                                        });
                                    }
                                }
                            }
                        }
                    }

                    // Use both entry_id & jid (if present) as correlation IDs in logs/metrics.
                    let corr = if jid.is_empty() {
                        format!("entry_id={entry_id}")
                    } else {
                        format!("entry_id={entry_id} jid={jid}")
                    };

                    let mut advance_last_id = false;
                    let mut fatal_error = false;

                    if jid.is_empty() {
                        eprintln!("[entry.malformed] {corr} missing job id");
                        advance_last_id = true;
                    } else if is_completed(&mut con, &entry_id, jid.as_str())? {
                        eprintln!("[handler.skip.completed] {corr}");
                        advance_last_id = true;
                    } else {
                        // ----- PROCESSING CHECKPOINT -----
                        // For stronger guarantees/idempotency:
                        // - Write a checkpoint *before* heavy side effects.
                        // - If we crash/replay, handler sees checkpoint/completed markers and acts idempotently.
                        if let Err(e) = mark_processing(&mut con, &entry_id, jid.as_str()) {
                            eprintln!("[processing.mark.error] {corr} err={e}");
                            // If we cannot mark processing, do not proceed; we'll see it again.
                            fatal_error = true;
                        } else {
                            // Mark job hash "status=processing" best-effort (not a hard precondition).
                            if let Err(e) = con.hset::<_, _, _, ()>(
                                format!("job:{jid}"),
                                "status",
                                "processing",
                            ) {
                                eprintln!("[job.status.mark.error] {corr} err={e}");
                            }
                            if let Err(e) = con.hset::<_, _, _, ()>(
                                format!("job:{jid}"),
                                "processing_entry_id",
                                &entry_id,
                            ) {
                                eprintln!("[job.processing_entry.mark.error] {corr} err={e}");
                            }

                            match run_python_for(&mut con, jid.as_str(), runner_timeout_s) {
                                Ok(()) => {
                                    let _ = mark_completed(&mut con, &entry_id, jid.as_str());
                                    if let Err(e) = con.hset::<_, _, _, ()>(
                                        format!("job:{jid}"),
                                        "status",
                                        "completed",
                                    ) {
                                        eprintln!("[job.status.completed.error] {corr} err={e}");
                                    }
                                    advance_last_id = true;
                                    // Telemetry (TODO): increment jobs.processed; record latency histogram
                                }
                                Err(e) => {
                                    eprintln!("[handler.error] {corr} err={e}");
                                    if let Err(err) = con.hset::<_, _, _, ()>(
                                        format!("job:{jid}"),
                                        "status",
                                        "failed",
                                    ) {
                                        eprintln!("[job.status.failed.error] {corr} err={err}");
                                    }
                                    if let Err(err) = con.hset::<_, _, _, ()>(
                                        format!("job:{jid}"),
                                        "error",
                                        e.to_string(),
                                    ) {
                                        eprintln!("[job.error.write.error] {corr} err={err}");
                                    }
                                    fatal_error = true;
                                    // Telemetry (TODO): increment jobs.failed
                                }
                            }
                        }
                    }

                    if advance_last_id {
                        // ----- ADVANCE & PERSIST last_id after handling this entry -----
                        last_id = entry_id.clone();
                        if let Err(e) = con.set::<_, _, ()>(LAST_ID_KEY, &last_id) {
                            eprintln!("[last_id.persist.error] id={last_id} err={e}");
                            // Not fatal: we may reprocess on restart.
                        }
                        advanced_any = true;
                    }

                    if fatal_error {
                        had_batch_error = true;
                        break 'stream_loop;
                    }
                }
            }

            // Optional small sleep only if we got no data (reduce spin)
            if !advanced_any {
                thread::sleep(Duration::from_millis(25));
            }
            if had_batch_error {
                thread::sleep(Duration::from_millis(RETRY_BACKOFF_ON_ERROR_MS));
            }
        } else {
            // XREAD timeout (no entries); small sleep to reduce CPU
            thread::sleep(Duration::from_millis(10));
        }

        // ----- Periodic trimming by MINID watermark -----
        if loop_count % trim_every_n_loops == 0 {
            if let Err(e) = trim_stream_minid(&mut con, &stream_name, &last_id, trim_minutes) {
                eprintln!("[trim.error] err={e}");
            }
        }
    }
}

/// Connect with simple exponential backoff.
fn connect_with_backoff(client: &redis::Client) -> Result<redis::Connection> {
    let mut delay = Duration::from_millis(200);
    for _ in 0..8 {
        match client.get_connection() {
            Ok(c) => return Ok(c),
            Err(e) => {
                eprintln!(
                    "[redis.connect.retry] err={e} delay_ms={}",
                    delay.as_millis()
                );
                thread::sleep(delay);
                delay = std::cmp::min(delay * 2, Duration::from_secs(5));
            }
        }
    }
    // final attempt
    Ok(client.get_connection()?)
}

/// Defensive helpers to parse redis::Value
fn as_bulk(v: &redis::Value) -> Option<&Vec<redis::Value>> {
    match v {
        redis::Value::Array(b) => Some(b),
        _ => None,
    }
}
fn as_data(v: &redis::Value) -> Option<&[u8]> {
    match v {
        redis::Value::BulkString(b) => Some(b.as_slice()),
        redis::Value::SimpleString(s) => Some(s.as_bytes()),
        _ => None,
    }
}

/// Persisted string getter (None if missing or wrong type)
fn redis_get_string(con: &mut redis::Connection, key: &str) -> Result<Option<String>> {
    let v: Option<redis::Value> = con.get(key).ok();
    match v {
        Some(redis::Value::BulkString(b)) => Ok(Some(try_string_from_bytes(&b))),
        Some(redis::Value::SimpleString(s)) => Ok(Some(s.clone())),
        Some(redis::Value::Okay) => Ok(Some("OK".to_string())),
        _ => Ok(None),
    }
}

fn try_string_from_bytes(bytes: &[u8]) -> String {
    String::from_utf8(bytes.to_vec()).unwrap_or_else(|e| {
        // lossy fallback to avoid panics on corrupted storage
        String::from_utf8_lossy(&e.into_bytes()).into_owned()
    })
}

/// Mark a processing checkpoint: we record intent to process before side effects.
/// This allows the handler to act idempotently on replays.
/// Data model choices (simple & explicit):
///  - Hash: videogen:processing:<entry_id> → { jid, ts_ms } with TTL for leak prevention
///  - Key : videogen:completed:<entry_id>  → ts_ms (string) with TTL to cap growth
fn mark_processing(con: &mut redis::Connection, entry_id: &str, jid: &str) -> Result<()> {
    let key = format!("{PROCESSING_KEY_NS}:{entry_id}");
    let ts_ms = now_ms();
    let _: () = con.hset(&key, "jid", jid)?;
    let _: () = con.hset(&key, "ts_ms", ts_ms)?;
    let _: bool = con.expire(&key, PROCESSING_TTL_SECS)?;
    Ok(())
}

fn is_completed(con: &mut redis::Connection, entry_id: &str, _jid: &str) -> Result<bool> {
    // For multi-tenant you could key per-stream/tenant; we keep it simple.
    let key = format!("{COMPLETED_KEY_NS}:{entry_id}");
    if con.exists(&key)? {
        return Ok(true);
    }
    // Backward compatibility for legacy Set-based markers.
    con.sismember(COMPLETED_KEY_NS, entry_id)
        .map_err(Into::into)
}

fn mark_completed(con: &mut redis::Connection, entry_id: &str, _jid: &str) -> Result<()> {
    let key = format!("{COMPLETED_KEY_NS}:{entry_id}");
    let ts_ms = now_ms();
    con.set_ex::<_, _, ()>(&key, ts_ms, COMPLETED_TTL_SECS)?;

    // Best-effort cleanup of the processing checkpoint now that we are done.
    let processing_key = format!("{PROCESSING_KEY_NS}:{entry_id}");
    if let Err(e) = redis::cmd("DEL")
        .arg(&processing_key)
        .query::<()>(&mut *con)
    {
        eprintln!("[processing.cleanup.error] entry_id={entry_id} err={e}");
    }
    Ok(())
}

/// Run the external Python job runner with a soft timeout.
/// NOTE: std::process has no built-in timeout; in production:
///   - Use the `wait_timeout` crate or run under Tokio and `tokio::time::timeout`.
///   - If timeout elapses, kill the child and return an error.
///   - Add retries with **exponential backoff + jitter** (TODO circuit-breaker integration).
fn run_python_for(con: &mut redis::Connection, jid: &str, timeout_s: u64) -> Result<()> {
    // Idempotency hint: If the job already has a stable result (e.g., result_url),
    // short-circuit to success to avoid duplicate side effects.
    if let Ok(Some(url)) = get_nonempty_hget(con, &format!("job:{jid}"), "result_url") {
        eprintln!("[handler.idempotent.shortcut] jid={jid} url={url}");
        return Ok(());
    }

    let mut child = Command::new("python3")
        .arg("/app/model_runner.py")
        .arg(jid)
        .stdin(Stdio::null())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .spawn()
        .context("failed to spawn python runner")?;

    // Pseudo-timeout (best-effort) — replace with wait_timeout or tokio in production.
    let start = std::time::Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(status)) => {
                if !status.success() {
                    bail!("python runner failed with status {:?}", status.code());
                }
                break;
            }
            Ok(None) => {
                if start.elapsed() >= Duration::from_secs(timeout_s) {
                    // Kill and error
                    let _ = child.kill();
                    bail!("python runner timeout after {}s", timeout_s);
                }
                thread::sleep(Duration::from_millis(100));
            }
            Err(e) => {
                let _ = child.kill();
                bail!("python runner wait error: {e}");
            }
        }
    }

    // Ensure the runner wrote a result
    let url: String = con
        .hget(format!("job:{jid}"), "result_url")
        .unwrap_or_default();
    if url.is_empty() {
        bail!("no result_url set by runner");
    }
    Ok(())
}

fn get_nonempty_hget(
    con: &mut redis::Connection,
    key: &str,
    field: &str,
) -> Result<Option<String>> {
    let v: Option<String> = con.hget(key, field).ok();
    Ok(v.filter(|s| !s.is_empty()))
}

/// Trim the stream by time watermark using XTRIM MINID ~ "<ms>-0".
/// Uses current time minus `trim_minutes`. MINID is a **safer** policy than MAXLEN for time-based retention:
/// it preserves recent items regardless of burst size. Use MAXLEN (approx) when you care only about memory bounds.
/// For services with SLAs tied to “redelivery window” and audits, time-based MINID is more predictable.
fn trim_stream_minid(
    con: &mut redis::Connection,
    stream: &str,
    last_id: &str,
    trim_minutes: u64,
) -> Result<()> {
    if last_id.is_empty() || last_id == "0-0" {
        // Nothing processed yet; do not risk trimming backlog.
        return Ok(());
    }

    let cutoff_ms = now_ms().saturating_sub(trim_minutes * 60 * 1000);
    let last_ms = last_id
        .split('-')
        .next()
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(0);

    if last_ms == 0 {
        return Ok(());
    }

    let target_ms = cutoff_ms.min(last_ms);
    if target_ms == 0 {
        return Ok(());
    }

    let effective_minid = if target_ms == last_ms {
        last_id.to_string()
    } else {
        format!("{target_ms}-0")
    };

    // XTRIM MINID keeps entries with ID >= given MINID; older are trimmed.
    // The "~" option allows approximate trimming for speed.
    let _: () = redis::cmd("XTRIM")
        .arg(stream)
        .arg("MINID")
        .arg("~")
        .arg(&effective_minid)
        .query(con)?;
    Ok(())
}

fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}
