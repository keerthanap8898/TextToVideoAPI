import os, sys, redis
from pathlib import Path

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
OUT_DIR    = Path(os.getenv("OUT_DIR", "/data/videos"))
USE_MINIO  = os.getenv("USE_MINIO", "false").lower() == "true"

MINIO_EP=os.getenv("MINIO_ENDPOINT","http://minio:9000")
MINIO_KEY=os.getenv("MINIO_ACCESS_KEY","minioadmin")
MINIO_SEC=os.getenv("MINIO_SECRET_KEY","minioadmin")
MINIO_BUCKET=os.getenv("MINIO_BUCKET","videos")

def maybe_upload(outfile: Path) -> str:
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
    jid = sys.argv[1]
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    job = r.hgetall(f"job:{jid}")
    prompt = job.get("prompt","")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    outfile = OUT_DIR / f"{jid}.mp4"

    # TODO: Replace this stub with the real mochi-1-preview generation.
    # For MVP demo, write a tiny file so the flow completes.
    with open(outfile, "wb") as f:
        f.write(b"\x00")

    url = maybe_upload(outfile)
    r.hset(f"job:{jid}", mapping={"result_url": url})

if __name__ == "__main__":
    main()
