import os, uuid, time
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
JOBS_STREAM = os.getenv("JOBS_STREAM", "videogen:jobs")
JOBS_INDEX  = os.getenv("JOBS_INDEX", "videogen:jobs:index")
VIDEO_BASE  = os.getenv("VIDEO_BASE_URL", "/videos")  # if serving from API/pvc

r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
app = FastAPI(title="VoltagePark VideoGen API", version="0.1")

class SubmitReq(BaseModel):
    prompt: str
    seconds: Optional[int] = 6
    quality: Optional[str] = "medium"   # "low|medium|high"
    resolution: Optional[str] = "576p"  # "360p|576p|720p|1080p"

@app.post("/jobs")
def submit(req: SubmitReq):
    jid = str(uuid.uuid4())
    job = {
        "id": jid, "prompt": req.prompt,
        "seconds": str(req.seconds), "quality": req.quality, "resolution": req.resolution,
        "status": "pending", "created_at": str(int(time.time()))
    }
    r.hset(f"job:{jid}", mapping=job)
    r.lpush(JOBS_INDEX, jid)
    r.xadd(JOBS_STREAM, fields={"id": jid}, maxlen=10000, approximate=True)
    return {"job_id": jid}

@app.get("/jobs/{jid}")
def status(jid: str):
    d = r.hgetall(f"job:{jid}")
    if not d: raise HTTPException(404, "job not found")
    return {
        "id": d["id"],
        "status": d.get("status","unknown"),
        "error": d.get("error"),
        "result_url": d.get("result_url"),
    }

@app.get("/jobs")
def list_jobs(limit: int = Query(50, ge=1, le=200)):
    ids = r.lrange(JOBS_INDEX, 0, limit-1)
    out = []
    for jid in ids:
        d = r.hgetall(f"job:{jid}")
        if d: out.append({"id": d["id"], "status": d.get("status","?"), "created_at": d.get("created_at")})
    return {"items": out}

@app.get("/jobs/{jid}/result")
def result(jid: str):
    d = r.hgetall(f"job:{jid}")
    if not d: raise HTTPException(404, "job not found")
    if d.get("status") != "completed": raise HTTPException(409, "job not completed")
    return {"result_url": d["result_url"]}
