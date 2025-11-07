# FastAPI backend for VideoGen API
# Handles job submission, status queries, job listing, and result retrieval via Redis.
import os, uuid, time  # Import OS, UUID, and time utilities
from typing import Optional  # For optional type hints
from fastapi import FastAPI, HTTPException, Query  # FastAPI framework imports
from pydantic import BaseModel  # For request validation
import redis  # Redis client

# Read environment variables for Redis connection and job stream/index names
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
JOBS_STREAM = os.getenv("JOBS_STREAM", "videogen:jobs")
JOBS_INDEX  = os.getenv("JOBS_INDEX", "videogen:jobs:index")
VIDEO_BASE  = os.getenv("VIDEO_BASE_URL", "/videos")  # Base URL for serving videos

# Connect to Redis using the provided URL
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
# Initialize FastAPI app
app = FastAPI(title="VoltagePark VideoGen API", version="0.1")

# Request model for job submission
class SubmitReq(BaseModel):
    prompt: str  # Text prompt for video generation
    seconds: Optional[int] = 6  # Duration in seconds
    quality: Optional[str] = "medium"   # Video quality: low|medium|high
    resolution: Optional[str] = "576p"  # Video resolution: 360p|576p|720p|1080p

# Endpoint to submit a new video generation job
@app.post("/jobs")
def submit(req: SubmitReq):
    jid = str(uuid.uuid4())  # Generate a unique job ID
    job = {
        "id": jid, "prompt": req.prompt,
        "seconds": str(req.seconds), "quality": req.quality, "resolution": req.resolution,
        "status": "pending", "created_at": str(int(time.time()))
    }
    r.hset(f"job:{jid}", mapping=job)  # Store job metadata in Redis hash
    r.lpush(JOBS_INDEX, jid)  # Add job ID to index list
    r.xadd(JOBS_STREAM, fields={"id": jid}, maxlen=10000, approximate=True)  # Publish job to stream
    return {"job_id": jid}  # Return job ID to client

# Endpoint to get status of a specific job
@app.get("/jobs/{jid}")
def status(jid: str):
    d = r.hgetall(f"job:{jid}")  # Fetch job metadata from Redis
    if not d: raise HTTPException(404, "job not found")  # Error if job does not exist
    return {
        "id": d["id"],
        "status": d.get("status","unknown"),
        "error": d.get("error"),
        "result_url": d.get("result_url"),
    }

# Endpoint to list recent jobs
@app.get("/jobs")
def list_jobs(limit: int = Query(50, ge=1, le=200)):
    ids = r.lrange(JOBS_INDEX, 0, limit-1)  # Get job IDs from index list
    out = []
    for jid in ids:
        d = r.hgetall(f"job:{jid}")  # Fetch job metadata
        if d: out.append({"id": d["id"], "status": d.get("status","?"), "created_at": d.get("created_at")})
    return {"items": out}  # Return list of jobs

# Endpoint to get result URL for a completed job
@app.get("/jobs/{jid}/result")
def result(jid: str):
    d = r.hgetall(f"job:{jid}")  # Fetch job metadata
    if not d: raise HTTPException(404, "job not found")  # Error if job does not exist
    if d.get("status") != "completed": raise HTTPException(409, "job not completed")  # Error if job not done
    return {"result_url": d["result_url"]}  # Return result URL
