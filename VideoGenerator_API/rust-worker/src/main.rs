use anyhow::*;
use redis::{Commands, StreamsCommands};
use std::process::Command;
use std::time::Duration;

fn main() -> Result<()> {
    let redis_url = std::env::var("REDIS_URL").unwrap_or("redis://redis:6379/0".into());
    let jobs_stream = std::env::var("JOBS_STREAM").unwrap_or("videogen:jobs".into());
    let mut con = redis::Client::open(redis_url)?.get_connection()?;

    loop {
        // Block until 1 message arrives on the stream
        let resp: redis::Value = con.xread_options(&[&jobs_stream], &[">"], None, 1, 0)?;
        if let redis::Value::Bulk(ref outer) = resp {
            for entry in outer {
                if let redis::Value::Bulk(items) = entry {
                    if let redis::Value::Bulk(entries) = &items[1] {
                        for e in entries {
                            if let redis::Value::Bulk(ev) = e {
                                if let redis::Value::Bulk(kv) = &ev[1] {
                                    let mut jid = String::new();
                                    for i in (0..kv.len()).step_by(2) {
                                        if let (redis::Value::Data(k), redis::Value::Data(v)) = (&kv[i], &kv[i+1]) {
                                            if k == b"id" { jid = String::from_utf8(v.clone()).unwrap(); }
                                        }
                                    }
                                    if !jid.is_empty() {
                                        let _ : () = con.hset(format!("job:{jid}"), "status", "processing")?;
                                        if let Err(e) = run_python_for(&mut con, &jid) {
                                            let _ : () = con.hset(format!("job:{jid}"), "status", "failed")?;
                                            let _ : () = con.hset(format!("job:{jid}"), "error", e.to_string())?;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        std::thread::sleep(Duration::from_millis(50));
    }
}

fn run_python_for(con: &mut redis::Connection, jid: &str) -> Result<()> {
    // Call the tiny python runner to do the actual model/encode/upload work.
    let status = Command::new("python3")
        .arg("/app/model_runner.py")
        .arg(jid)
        .status()?;
    if !status.success() {
        bail!("python runner failed with status {:?}", status.code());
    }
    let url: String = con.hget(format!("job:{jid}"), "result_url")?;
    if url.is_empty() { bail!("no result_url set by runner"); }
    let _: () = con.hset(format!("job:{jid}"), "status", "completed")?;
    Ok(())
}
