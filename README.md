o [View the full design document here (PDF)](https://github.com/keerthanap8898/TextToVideoAPI/blob/main/Text_to_Video_API_Docx_combined.pdf)

## Latest Updates:
 1. **Research Cost analysis.**
 2. **Minimal features needed to convincingly prove my hypothesis:**
     - ***... that Rust core threads can in fact ensure Correctness in HPC system structures & typically risky correctness-critical modules or use-cases.***
 3. **Hierarchial Testing & Release Strategy.**

# 1-pager (closer to a 5-Pager at this point...)
## Text-to-Video API – MVP & Open-source Design Document
    - Author: Keerthana Purushotham
    - Date: 2025-08-08
    - Purpose: This document outlines the design for a Kubernetes-deployed Text-to-Video API service using the Genmo Mochi-1 model to solve the problem of scalable, asynchronous, prompt-driven video generation.
    - This repository & work is fully maintained & owned by me (Keerthana), personally. You're welcome to pull what I've laid out, I've set up basic Licensing too.
    - This MVP (not Production) isn't complete yet but everything successfully builds. I'll post a detailed wiki soon.
---

## Table of Contents
    1. [Problem Statement](#1-problem-statement-the-why)  
    2. [Proposed Solution](#2-proposed-solution-the-what)  
    3. [Success Metrics](#3-success-metrics-the-how-does-one-know-it-worked)  
    4. [Research Cost Analysis](#research-cost-analysis)
    5. [Open Questions & Assumptions](#4-open-questions--assumptions)  
    6. [Feature Prioritization & Risk Analysis](#feature-prioritization--risk-analysis)   
    7. [Testing Strategy](#testing-strategy) 
    8. [Other Corner Cases](#edge-cases-and-post-production-checks)  
    9. [Appendix](#appendix-team-input-to-vote-and-choose-v1-production-release-features)  

---

## 1. Problem Statement (The Why)
   - **Customers**: Users & maintainers etc.,including & not restricted to Developers, researchers, & creative teams who need a scalable, programmatic text-to-video generation service.
   - **Pain Points**: Current GenAI tools are often single-instance, blocking, & lack scalable API endpoints. Customers require asynchronous, concurrent, multi-GPU processing to handle high request volumes.
   - **Urgency**: Demand for generative AI content is growing rapidly; this solution enables fast iteration & deployment.
---

## 2. Proposed Solution (The What)
   ***Goal is to build an asynchronous text-to-video API using the Genmo Mochi-1 model hosted on an 8×H100 GPU Kubernetes worker node. The backend will handle job submission, tracking, & retrieval via JSON-based endpoints. A basic React-based frontend will allow prompt submission, status monitoring, & file downloads. The system will be deployed on Kubernetes (K8s) with GPU resource allocation, multi-replica redundancy, & horizontal scaling.***
   - **Non-Goals**: This MVP will not include advanced scheduling algorithms, RBAC, LLM-based load estimation, or zero-knowledge security layers - those are reserved for post-MVP.
- ### Flow Diagram for the system design:
   - ![flowdiagram](https://github.com/keerthanap8898/TextToVideoAPI/blob/main/Resources/Other/Images/Flowchart.png)
---

## 3. Success Metrics (The How does one know it worked?)
   ### MVP Success:
         - ≥95% job success rate.
         - P95 end-to-end latency ≤10 min.
         - Queue wait P95 ≤2 min.
         - Throughput ≥4 parallel jobs.
         - API availability ≥99% during demo.
         - 100% output artifact validity.
   ### Production Success:
         - API availability ≥99.9%.
         - P95 latency ≤6 min, P99 ≤10 min.
         - Job retries <1%, DLQ <0.1%.
         - GPU utilization 70–90%.
         - Auth coverage 100%.
         - 0 critical CVEs in running images.
---

## 4. Research Cost Analysis
   ### Visualization of **GPU usage & cost trends across all phases**.  

 - ![Research Cost analysis](https://github.com/keerthanap8898/TextToVideoAPI/blob/main/Resources/Other/Images/Text_to_Video_CostAnalysis.png)  

       - Captures the "best", "average" & "worst" case GPU costs estimated to completely test & prove my hypothesis.  
       - Includes 5-day rolling mean GPU usage line.  
       - Highlights phase peaks at correctness-heavy workloads (Multi-GPU support, Fault Tolerance, Load Testing).  
---

## 5. Open Questions & Assumptions

### **Considerations & Estimations:**
  - Load visualization for video length vs prompt length - Estimated Runtime vs. Video Duration & Prompt Length
  - Isolines show approximate VRAM contours per sister node (illustrative)
      - ![Load+space estimates projected across effort vs video length](https://github.com/keerthanap8898/TextToVideoAPI/blob/main/Resources/Other/Images/video_length_vs_duration.png)
  - Scale: Deployment patterns to prevent DoS by region, user-group etc.,with rollback, canary testing, retries, rate-limits etc.
  - **Exceptions**:
      - Buggy prompt context from user – poor quality / lack of response
      - Prompt work load exceeds resource allocation thresholds
      - Infra security breaks -> retry & log relevant details
      - Are all tools compatible with potential upgrades & tool integrations without high refactoring costs?
      - Ensure the OOPS aspects optimize computation without logical gaps or duplicate calculations.
  - **Concurrency**:
      - Handled by Python orchestration over encapsulated, asynchronous Rust worker modules that run atomized request threads that close by virtue of Rust’s memory/garbage management semantics that ensure that failed jobs do not break the validity of the session
   
#### NP-Completeness & Determinism
  - **Performance (latency)**: `Scheduling is NP-hard`, handled with heuristics (queues, batching, rate limits); stable statistically, not per run.
  - **Correctness (Rust ownership)**: General correctness is undecidable, but Rust enforces memory safety at compile time; `modules behave deterministically`.  
  - **Concurrency (async threads)**: `Deadlocks/races are NP-hard`, but bounded with small Rust workers + idempotent tasks; validated with stress/schedule tests.
  - **HPC inference**: `Load balancing is NP-hard & is thus, approximated`; with async streaming + job routing; predictable at cluster level via forecasts.  
  - **Cross-language orchestration**: `Protocol conformance is NP-hard`, simplified with schemas, versioning, & idempotent IDs that can be retried upon failure, observed &/or tested appropriately for correctness.

#### Complexity class landscape (`P`/ `NP`/ `NP-hard`/ `Unclear`) annotated with the calculated placement of system layers in a hybrid Rust+Python orchestration design.
    - To conclude, I’m thus sharing a complexity-class-inclusion-diagram (attached).
    - It helps visualize how P ⊂ NP, NP-complete, NP-hard, & Undecidable classes map against this project specifically.*
### The img is annotated with where each system layer sits in the proposed design. :)
    
* ![P/NP/NP-hard/unclear - complexity class Venn diagram](https://github.com/keerthanap8898/TextToVideoAPI/blob/main/Resources/Other/Images/NP-ness_Text-to-video_API.png)

---

#### ***Hence, to summarize***:

### Assumptions:
    - Video length ≤10s for MVP.
    - Resolution ≤768p.
    - API structure is REST over JSON.
    - External object storage (S3/MinIO) is available.
### `Open Questions`:
    - Will the control plane ELB DNS be stable for external access? (known to cause costly DoS across regions resulting in downtime & loss)
    - Expected concurrency limits at demo vs production scale?
    - Any constraints on video length/quality &/or time limits from stakeholders?
    - Complex multi-part prompts requiring state management, explicit network hardening (over sandboxing) plus encryption.
---

## 6. Feature Prioritization & Risk Analysis

### Table mapping **minimal correctness-critical features** vs optional research ones.  

- ![Feature Prioritization Table](https://github.com/keerthanap8898/TextToVideoAPI/blob/main/Resources/Other/Images/FeaturePrioritization_RiskAnalysis_Table.png)  

      Tier 1 (High):
        - Fault tolerance, scheduling, scalability, correctness validation.  
      Tier 2 (Medium):
        - Monitoring, cost/resource management, inference stability.  
      Tier 3 (Low):
        - UI/UX, API versioning, access control, prompt validation.  
---
     
# 7. Testing Strategy
***The system is designed for reliability & correctness under diverse workloads. Model nondeterminism vs “golden” tests; flaky performance from noisy neighbors. Since text-to-video generation involves GPU scheduling, multi-process execution, & distributed infra, the testing layers span both functional & non-functional validation.***
Hence, my testing methodology includes:

### A. Core Functional Testing
  1. **Model Nondeterminism vs “Golden” Tests**:  
     ***Manage drift in generated outputs. Golden baselines should be reproducible within a tolerance margin. Meant to detect flaky performance caused by noisy neighbors in shared GPU environments.***
      - **Category:** *Pre-release* & *Nightly regression*
  2. **Validation**:
     ***Check if things are right under expected inputs & conditions.*** 
      - **Category:** *Pre-release*  
  3. **Sanity**:
     ***Ensure wrong or impossible things can’t happen (bad configs, invalid data).***
      - **Category:** *Pre-release* & *CI/CD blocking*  
  4. **Unit**:
     ***Cover as many test cases as possible, including edge cases, corner cases, & outlier scenarios.***  
      - **Category:** *Pre-release* & *Continuous integration*  
  5. **Integration**:
     ***Verify cross-tool & cross-module workflows behave correctly.*** 
      - *(e.g., pre-processing → model inference → post-processing → storage).*  
    - **Category:** *Pre-release* & *Continuous integration*  
  6. **Regression**:
     ***Ensure that new changes don’t break existing functionality or previously fixed bugs.***
      - **Category:** *Pre-release* & *Nightly regression*  

### B. Advanced / Non-Functional Testing
  1. **Load Testing**:
     ***Simulate heavy usage across multiple GPUs/nodes; measure throughput, latency, & memory pressure at scale.***
      - **Category:** *Pre-release* for capacity planning; *Canary* for production safety  
  2. **Stress Testing**:
     ***Push system beyond expected limits (e.g., GPU memory exhaustion, burst API calls, long video generations) to observe controlled failures & recovery.***
      - **Category:** *Pre-release* only  
  3. **Chaos Testing**:
     ***Inject faults (GPU preemption, node restarts, throttled APIs, network partitions) to validate resilience, correctness under disruption, & graceful degradation.***
      - **Category:** *Canary* (production experiments)  
  4. **Soak Testing**:
     ***Run long-duration jobs to uncover resource leaks, GPU overheating issues, or slow degradation of performance/quality.***
      - **Category:** *Pre-release (staging clusters)*  
  5. **Concurrency & Safety**:
     ***Explicitly test multi-GPU scheduling, thread/process safety, & race-condition scenarios in distributed pipelines.***
      - **Category:** *Pre-release* & *CI/CD*  

### C. Test Deployment Strategy
  1. **Pre-release (staging)**:  
      - Unit, validation, sanity, integration, regression, load, soak.  
      - ***Goal***: *ensure correctness & performance before shipping.*  
  2. **Continuous Integration (CI/CD)**:  
      - Sanity, unit, integration, concurrency.  
      - Fast, automated feedback loop for every PR/merge.  
  3. **Nightly Regression**:  
      - Golden tests, regression, validation.  
      - Ensures long-term reproducibility & stability.  
  4. **Canary (production)**: 
      - Chaos tests, partial-load tests.  
      - Safely run in production with a subset of traffic or limited GPU pool.  
      - ***Goal***: *detect real-world issues without full rollout risk.*  

### D. Suggested Tools/Frameworks
1. **Unit/Regression/Integration** – `pytest`, `unittest`, `tox`, `pytest-benchmark`  
2. **Load/Stress** – `locust`, `wrk2`, `k6`, `gpu-burn` (CUDA stress testing)  
3. **Chaos** – `chaos-mesh`, `gremlin`, custom fault-injection scripts  
4. **Soak/Long-run** – Kubernetes cron-jobs, Prometheus metrics, Grafana dashboards  
5. **Concurrency** – `pytest-xdist`, `ray`, distributed pipeline simulators  
6. **CI/CD** – GitHub Actions, GitLab CI, Jenkins pipelines with GPU runners  


#### `Together, this layered testing strategy ensures that the **Text-to-Video API** is correct, robust, fault-tolerant, & performant — validated before release, continuously monitored in CI/CD, & safely hardened in production via canaries.`
---
     
## 8. Other Corner Cases:
  1. **Pre-signed URL misuse / role changes mid-job / token skew.**
     - recover any state from persistent storage & retry
  2. **Hot-keying in rate limiter; retry storms; DLQ loops.**
     - (fastapi-limiter &/or redis). Link: [stackoverflow & documentation](https://stackoverflow.com/questions/65491184/ratelimit-in-fastapi#:~:text=In%20order%20to,this%20to%20work) for the caveat explained below..
     - **NOTE**: FastAPI doesn't natively support this, but it's possible with a few libraries such the ones below, but will usually require some sort of database backing (redis, memcached, etc.), although slowapi has a memory fallback in case of no database.
     - reference documentation:
         * [fastapi-limiter | vendor reference doc link - PyPI - https://pypi.org/project/fastapi-limiter](https://pypi.org/project/fastapi-limiter/)
         * [slowapi | vendor reference doc link - PyPI - https://pypi.org/project/slowapi](https://pypi.org/project/slowapi/)
             - Vendor has noted issues with no patches suggesting that the project may be well on its way into being deprecated upstream & is hence, a poor design choice by default. 
     - `In order to use fastapi-limiter, as seen in their documentation: You will need a running Redis for this to work.` - [Redis reference](https://redis.io/)
  3. **Starvation of long jobs; convoy effects; head-of-line blocking.**
     - dedicated long-task exception handler node with critical Alarm if task still fails;
     - some job length estimator module returning Boolean value paired with a dashboard tracking accuracy trends for the query – “is this potentially a long task based on context, linguistics, user/env metrics? Yes/No”
     - …alarms at sev-2.5 if accuracy (true positives & negatives) consistently falls over time (false values are increasing. Check estimator logic), alarm at sev 2 if it falls immediately
  4. **Log PII, high-cardinality labels; sampling hiding tail latency.**
     - outliers & adversarial samples. Check if data corruption occurred via access/edit-logs, stack-trace, etc., to ensure no security exploitation broke the ML model.
  5. **Kubernetes deployment Policies & Cluster-platform maintenance** - with split-brain deploys across regions; partial rollbacks. Key **`kubectl`** commands for RBAC & other global/regional release strategy optimized for cluster resilience &/or network-traffic/load-metrics/schema-status/node-health, etc., specific scaling; i.e., I included hooks for advanced scheduling & cost estimation modules in these NP-complete problem
     - `rollout`[kubectl-ref](https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#rollout)
     - `set` [kubectl-ref](https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#set)
     - `scale` [kubectl-ref](https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#scale)
     - `autoscale` [kubectl-ref](https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#autoscale)
     - `auth` [kubectl-ref](https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#auth)
  6. **Stakeholders & Next Steps**:
     - Key Stakeholders:
        1. Users: API consumers (developers, researchers)
        2. Tech Support: Handles incidents & outages
        3. Developers: Build & maintain backend/frontend
        4. Vendor Organization: Voltage Park infrastructure team
        5. Network Peers: Any API gateway/CDN providers
        6. Node Cluster: K8s worker node (8×H100)
        7. Control Plane: Managed by vendor, not directly accessible
     - Next Steps:
        1. Deploy initial API & worker pods on K8s.
        2. Implement asynchronous endpoints.
        3. Finalize v1 prod features critical to release for enterprise scale.
        4. Build basic React frontend.
        5. Integrate Prometheus/Grafana monitoring.
        6. Conduct load test for target throughput.
        7. Prepare for demo & stakeholder review.
---


## 9. Appendix: team input – Vote & choose v1 release features for prod.

  ### Post-MVP Features – Prioritization Matrix
    - Purpose: Enable the team to quickly assess, vote, & sequence high-impact improvements after the MVP launch.
    - ### >> **`Voting Format: ✓ = must-have next, ?? = later, ✗ = not now.`**
       - ![Compare & assess relevant prod features](https://github.com/keerthanap8898/TextToVideoAPI/blob/main/Resources/Other/Images/feature_comparison_table.png)
       - More readable format - ![table_img_link](https://github.com/keerthanap8898/TextToVideoAPI/blob/main/Resources/Other/Images/Effort_vs_Impact_big_table.png)

#### Effort (developer hours) VS Impact Visualization:
-  ![plot Post MVP dev-effort-hrs vs impact with a normalized decimal score value](https://github.com/keerthanap8898/TextToVideoAPI/blob/main/Resources/Other/Images/dev-workload_vs_impact.png)

**I’ve mapped each feature into an Effort vs Impact matrix so it’s easy to see trade-offs for a given feature, on the overall code quality & performance trends of the Service:**

    - Green = Immediate High-Impact / Low Effort (01, 02, 03)
    - Blue = High-Impact / Medium Effort (04, 05, 06)
    - Purple = Medium Impact / Higher Effort (07, 08)
    - Orange = Niche Impact / High Effort (09, 10)
    
    See full documentation for details.
o MVP Repo Tree Diagram - so far ...
![MVP Repo Tree Diagram - so far ...](https://github.com/keerthanap8898/TextToVideoAPI/blob/main/Resources/Other/Images/MVP_folder_tree.png)
