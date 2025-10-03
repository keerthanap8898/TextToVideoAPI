# Text-to-Video Orchestrator

An open-source scaffold for an asynchronous text-to-video API service.

## ✨ Features
- **Async job lifecycle**: submit → queue → track → result
- **FastAPI gateway** for HTTP APIs
- **Redis Streams** as durable, high-speed event backbone
- **Rust worker** scaffold with at-least-once semantics and checkpointing
- **Kubernetes manifests** for API, worker, Redis, ingress
- **Minimal front-end** to submit and poll jobs

## 🚧 Status
This repo provides the **infrastructure backbone** for text-to-video generation.  
It does *not* include model weights or GPU-bound video generation yet.

**Progress so far**
- Async APIs, Redis-backed queue, worker scaffold
- Dockerized API + worker
- Kubernetes templates for multi-replica deployments
- Basic UI for job submission + status

**Next milestones**
- Integrate Genmo Mochi-1 model
- Artifact persistence to S3/MinIO
- Observability (Prometheus, Grafana, logging)
- Security (JWT/OIDC auth, rate limiting, RBAC)

## 🚀 Quickstart (local demo) 
- Will make a proper build setup runbook/wiki once I push some tests.
```bash
# 1. Start Redis
docker run --rm -p 6379:6379 redis:7

# 2. Run API
cd VideoGenerator_API/back-end
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 3. Run worker (placeholder)
cd ../rust-worker
cargo run
```

## LinkedIn Updates:
1. 1st Update [https://www.linkedin.com/posts/keerthanapurushotham_opensrc-video-genai-activity-7373897756567851008-xrA4](https://www.linkedin.com/posts/keerthanapurushotham_opensrc-video-genai-activity-7373897756567851008-xrA4)
  - Text:
  ```
  Finally pushing some opensrc code 🙆🏻‍♀️ - github: keerthanap8898/TextToVideoAPI

Video GenAI is as much about infra, orchestration & reliability as the model itself. So I set up a FastAPI + Redis-stream + Rust-worker codebase for async job submission, status tracking & high-throughput processing.
P.S: Yet to integrate Mochi-1 across GPUs & my commits are messy.

My proposed research explores the hypothesis that correctness-critical logic can be isolated into atomic Rust modules; while orchestration, scheduling & higher-level control-flow are implemented in a productivity-core language like Python/C++. The expected benefit is a reduction in concurrency & memory-safety defects without sacrificing scalability/performance. The Text-to-Video API stack designed around the Genmo Mochi-1 model provides an ideal validation environment for this hypothesis.

I use a hybrid architecture with layers for
• Orchestration(Python: FastAPI,Celery, Redis)—managing job-runs, retries, state etc.,
• Correctness-critical execution(Rust GPU workers)—to run model inference, designed for memory safety & fault isolation.

It mirrors the research premise of combining a productivity-oriented orchestration language with correctness-oriented Rust workers.

Features
1. Concurrency+Correctness
Asynchronous job management, GPU concurrency & isolation of failed jobs without dropping session validity.
2. Hybrid Boundary Risks
Use of gRPC in Py & Rust mirrors the cross-language boundaries in the research hypothesis. Evaluating defect propagation, performance overhead & maintainability at these interfaces for validation.
3. Representative Workload
The pipeline is compute-heavy, memory-bound, latency-sensitive, making it a suitable stand-in for HPC-style correctness & concurrency challenges.
4. Security
Designed to minimize CVEs, enforcing correctness via testing & managing nondeterminism.

This work is consistent with the proposed idea. Analyzing this system’s correctness behavior under varying configs, serves as a practical testbed for validating my correctness hypothesis. Insights derived from here can be generalized to other domains where HPC-critical loads must balance safety+scalability.

Next Milestones (TO DO)-
1. Model Integration.
2. Persistence:
Adding object storage support (S3/MinIO)+CI/CD.
3. Observability:
Dashboards for queue depth, GPU use, LowLatency-p95/p99, logs.
4. Load Testing & tuning:
Running stress tests under burst workloads to validate stability, scaling & tail-latency performance. Metrics to measure solid improvements.
5. Security/ Reliability:
Authentication (JWT/ OIDC), role-based-access(RBAC), throttling, rate-limit & DLQ for failures.
6. Kubernetes:
Enabling Horizontal Pod Autoscaling for workers & ingress routing with back-pressure-aware traffic shaping.
7. Front-End:
React/ts/js client that supports job submission, status tracking & output mgmt.
  ```
2. 2nd Update [https://www.linkedin.com/posts/keerthanapurushotham_np-npcompleteness-api-activity-7374229827672862720-WDYV](https://www.linkedin.com/posts/keerthanapurushotham_np-npcompleteness-api-activity-7374229827672862720-WDYV?)
  - Text:
  ```
  #NP-completeness vs. practical determinism

💫 Just pushed a new commit exploring the intersection of NPcompleteness and model-determinism in my Text-to-Video API project:-
🔗 https://lnkd.in/gSAqn-Tz

👉🏽 Context:
 • Several system-design attributes like scheduling, concurrency, and load_balancing are all well-known to be NP-hard in theory.
 • I try to indirectly accommodate these anticipated blocks, preemptively at the base layer, instead of relying on patches later that lead to refactoring overhead, risk, & tech-debt by isolating correctness-critical modules & executing them in lightweight rust-threads.
 • Result - statistical determinism in latency & reliability, even if individual runs are non-deterministic.

👉🏽 Takeaways:
 •  You can’t “solve” NP-complete problems in production, but you can engineer around them with the right abstractions. It's provably easier to address as many blockers as it takes to get to the pre-decided goal than to try & identify which blockers to avoid on your way to a goal that you hope to potentially reach.
 •  This argument is like comparing the pros & cons of BFS vs. DFS as a metaphor/analogy; wherein the former is best used to assess all the easiest ways to get to every outcome that's plausible and the latter is best used to support finding the one pre-decided outcome with the highest priority and little consideration to alternative goals as long as it knows which goal is 1st priority.
 •  The proposed system avoids NP-complete complexity by combining Rust’s safety guarantees with Python’s orchestration heuristics, & enforces practical determinism by measuring, forecasting, logging, and visualizing use-case-specific assumptions & safety rails. This includes validation, stress, chaos, and cross-language integration testing to cover as many probabilistically likely corner cases as possible. Goal clarity + context visualization, in parallel & from ground-up is key.

👉🏽 Conclusion:
I’m sharing a complexity class inclusion diagram attached to this post. It shows how P ⊂ NP, NP-complete, NP-hard, and Undecidable classes map against this project. The diagram is annotated with where each system layer sits in the hybrid Rust+Python orchestration design. 🙂 🙆🏻‍♀️

✍️ Note:
Feel free to share questions, suggestions, etc. I’m sharing this project iteratively to refine & communicate the design + goals with as much accuracy as possible while working backwards from the outcome. This way I don’t waste time trying things I don’t need to & can’t risk. 

The aim is to eventually communicate my Rx goals so well that I can demonstrate the proposed logic convincingly in & across, any/all domains, use-cases & configs; by analyzing, generalizing & schematizing the core logical-'knots' & considerations raised by the community into verified, formal proof-backed features to handle HPC-correctness at a global, enterprise scale.
```

3. 3rd Update [https://www.linkedin.com/posts/keerthanapurushotham_estimated-financial-investment-needed-to-activity-7379975825049391106-2HoI](https://www.linkedin.com/posts/keerthanapurushotham_estimated-financial-investment-needed-to-activity-7379975825049391106-2HoI)
- Text:
```
Estimated Financial Investment needed to support GPU Usage for my HPC-Rust infra project

Main Hypothesis: Correctness-critical logic in HPC/AI pipelines can be reliably isolated into atomic Rust workers, with high-lvl orchestration in Py/C++, thus ensuring correctness, fault isolation & concurrency without sacrificing scalability/ performance.

To validate this, I prove practical feasibility before theoretical correctness:
⟾ Can the system handle large-scale workloads predictably?
⟾ What is the realistic cost of correctness testing (chaos, stress, regression, integration)?
⟾ Investment (GPU-hours, budget, etc.) needed to sustain all planned steps?

🔍 How the Data Provides Insight [see images] —

◈ 1• Filter Critical Features: This mapping allows us to see where funds should flow first: correctness-first features dominate the cost.
⟼ Broke down the system into 10 features.
⟼ Classified into Tier-1 High Priority (must prove correctness), Tier-2 Medium (supports validation) & Tier-3 Low (ancillary).

◈ 2• Timeline & Scaling: first 3 weeks of set-up demand high GPU use, followed by another burst during load testing.
⟼ Plan scaled to 120 days with each feature’s execution window mapped sequentially on this timeline.
⟼ Helps anticipate when funds are needed over reviewing at bulk.

◈ 3• Unit of Cost/phase: GPUhrs × compute-intensity= $$
⟼ GPU concurrency × avg hrs/day × days = Total GPUhrs (e.g. Load testing at 8 GPUs ×15.8 hrs/day ×10days ≈1264 GPU-hrs).
⟼ Converted into cost ($/GPU-hour) for best, avg & worst-cases.

◈ 4• Aggregation into 5-Day Windows: Stakeholders can see when peaks occur; justifies burst-capacity funding over flat-line allocation.
⟼ Split GPUhrs into 24–25 slices = 5 days.
⟼ Calculated mean GPU-hrs/day per window, a time-series of resource consumption.
⟼ Plotted $ costs to show dual perspective of money & machine time.

◈ 5• Visualizing Peaks, Valleys & Risks: high upfront cost in GPU credits/testing infra,
⟼ Peak GPU use = 128 GPU-hrs/day (baseline chaos + multi-GPU integration).
⟼ Idle valleys = <20 GPU-hrs/day during offline phases.

👉 Why This Matters:
1. Predictability: GPU & monetary resources needed can estimated before building at scale,
2. Prioritization: Tier-1 features (Fault tolerance, Scheduling, Validation) absorb ~70% of cost → investors know where funds create the strongest correctness proof.
3. Risk Reduction: Estimating upfront avoids overspend & de-risks commitments — can request credits/funds proportional to real workload spikes.
4. Hypothesis Proof: By mapping correctness → GPU-hrs → cost, I prove Rust-thread isolation is not just conceptually correct, but economically sustainable.

Thus the data provides a funding roadmap — it bridges research logic with real investment decisions. It shows the price of correctness, when it peaks & why correctness-first design in HPC with Rust cores is both necessary & financially justified.
```
