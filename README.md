o [View the full design document here (PDF)](https://github.com/keerthanap8898/xCompany_TechAssessment_Keerthana/blob/main/Text_to_Video_API_Docx_combined.pdf)

# 1-pager
## Text-to-Video API – MVP & Production Design Document
    - Author: Keerthana Purushotham
    - Date: 2025-08-08
    - Purpose: This document outlines the design for a Kubernetes-deployed Text-to-Video API service using the Genmo Mochi-1 model to solve the problem of scalable, asynchronous, prompt-driven video generation.

1. Problem Statement (The Why)
  - Customers: Users and maintainers etc including and not restricted to Developers, researchers, and creative teams who need a scalable, programmatic text-to-video generation service.
  - Pain Points: Current video generation tools are often single-instance, blocking, and lack scalable API endpoints. Customers require asynchronous, concurrent, multi-GPU processing to handle high request volumes.
  - Urgency: Demand for generative AI video content is growing rapidly; this solution enables fast iteration and deployment.

2. Proposed Solution (The What)
  - Goal is to build an asynchronous text-to-video API using the Genmo Mochi-1 model hosted on an 8×H100 GPU Kubernetes worker node. The backend will handle job submission, tracking, and retrieval via JSON-based endpoints. A basic React-based frontend will allow prompt submission, status monitoring, and file downloads. The system will be deployed on Kubernetes (K8s) with GPU resource allocation, multi-replica redundancy, and horizontal scaling.

  - Non-Goals: This MVP will not include advanced scheduling algorithms, RBAC, LLM-based load estimation, or zero-knowledge security layers - those are reserved for post-MVP.

  - Flow Diagram for the system design:
     - ![flowdiagram](https://github.com/keerthanap8898/xCompany_TechAssessment_Keerthana/blob/main/Resources/Other/Images/Flowchart.png)

3. Success Metrics (The How do we know it worked?)
  - MVP Success:
    - ≥95% job success rate.
    - P95 end-to-end latency ≤10 min.
    - Queue wait P95 ≤2 min.
    - Throughput ≥4 parallel jobs.
    - API availability ≥99% during demo.
    - 100% output artifact validity.

  - Production Success:
    - API availability ≥99.9%.
    - P95 latency ≤6 min, P99 ≤10 min.
    - Job retries <1%, DLQ <0.1%.
    - GPU utilization 70–90%.
    - Auth coverage 100%.
    - 0 critical CVEs in running images.

4. Open Questions & Assumptions

**Considerations and Estimations:**
  - Load visualization for video length vs prompt length - Estimated Runtime vs. Video Duration & Prompt Length
  - Isolines show approximate VRAM contours per sister node (illustrative)

    - ![Load+space estimates projected across effort vs video length](https://github.com/keerthanap8898/xCompany_TechAssessment_Keerthana/blob/main/Resources/Other/Images/video_length_vs_duration.png)

  - Scale: Deployment patterns to prevent DoS by region, user-group etc with rollback, canary testing, retries, rate-limits etc.
  - Exceptions:
    - Buggy prompt context from user – poor quality / lack of response
    - Prompt work load exceeds resource allocation thresholds
    - Infra security breaks -> retry / log relevant details
    - Are all tools compatible with potential upgrades and tool integrations without high refactoring costs?
    - ensure the OOPS aspects optimize computation without logical gaps or duplicate calculations
  - Concurrency
    - handled by python orchestration over encapsulated, asynchronous Rust worker modules that run atomized request threads that close by virtue of Rust’s memory/garbage management semantics that ensure that failed jobs do not break the validity of the session

#### Assumptions:
  - Video length ≤10s for MVP.
  - Resolution ≤768p.
  - API structure is REST over JSON.
  - External object storage (S3/MinIO) is available.

#### Open Questions:
  - Will the control plane ELB DNS be stable for external access? (known to cause costly DoS across regions resulting in downtime and loss)
  - Expected concurrency limits at demo vs production scale?
  - Any constraints on video length/quality &/or time limits from stakeholders?
  - Complex multi-part prompts requiring state management, explicit network hardening (over sandboxing) plus encryption.

##### Other Corner Cases:
  1. Pre-signed URL misuse / role changes mid-job / token skew.
     - recover any state from persistent storage and retry
  2. Hot-keying in rate limiter; retry storms; DLQ loops.
     - (fastapi-limiter &/or redis). Link: stackoverflow & documentation for the caveat described below
     - NOTE: FastAPI doesn't natively support this, but it's possible with a few libraries such the ones below, but will usually require some sort of database backing (redis, memcached, etc), although slowapi has a memory fallback in case of no database.
     - reference documentation:
         * https://pypi.org/project/fastapi-limiter/
         * https://pypi.org/project/slowapi/
     - `In order to use fastapi-limiter, as seen in their documentation: You will need a running Redis for this to work.`
  3. Starvation of long jobs; convoy effects; head-of-line blocking.
     - dedicated long-task exception handler node with critical Alarm if task still fails;
     - some job length estimator module returning Boolean value paired with a dashboard tracking accuracy trends for the query – “is this potentially a long task based on context, linguistics, user/env metrics? Yes/No”
     - …alarms at sev-2.5 if accuracy (true positives and negatives) consistently falls over time (false values are increasing. Check estimator logic), alarm at sev 2 if it falls immediately
  4. Log PII, high-cardinality labels; sampling hiding tail latency.
     - outliers and adversarial samples. Check if data corruption occurred via access/edit-logs, stack trace, etc to ensure no security exploitation broke the ML model.
  5. Split-brain deploys across regions; partial rollbacks.
     - rollout[ref](https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#rollout)
     - set [ref](https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#set)
     - Scale [ref](https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#scale)
     - Autoscale [ref](https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#autoscale)
     - Auth [ref](https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#auth)
  6. Model nondeterminism vs “golden” tests; flaky perf from noisy neighbors.
     - Validation – check if things are right
     - Sanity – ensure wrong things can’t happen
     - Unit – cover as many test cases, corner cases and outlier cases
     - Integration – check if cross-tool features are ok
     - Regression – ensure that new changes don’t break existing functionality
  
  7. Stakeholders & Next Steps
     - Key Stakeholders:
       - Users: API consumers (developers, researchers)
       - Tech Support: Handles incidents & outages
       - Developers: Build & maintain backend/frontend
       - Vendor Organization: Voltage Park infrastructure team
       - Network Peers: Any API gateway/CDN providers
       - Node Cluster: K8s worker node (8×H100)
       - Control Plane: Managed by vendor, not directly accessible
     - Next Steps:
       - Deploy initial API & worker pods on K8s.
       - Implement asynchronous endpoints.
       - Finalize v1 prod features critical to release for enterprise scale.
       - Build basic React frontend.
       - Integrate Prometheus/Grafana monitoring.
       - Conduct load test for target throughput.
       - Prepare for demo & stakeholder review.
----------------

##Appendix: team input – Vote and choose v1 release features for prod.

  ###Post-MVP Features – Prioritization Matrix
    - Purpose: Enable the team to quickly assess, vote, and sequence high-impact improvements after the MVP launch.
    - ### >> **`Voting Format: ✓ = must-have next, ?? = later, ✗ = not now.`**
       - ![Compare and assess relevant prod features](https://github.com/keerthanap8898/xCompany_TechAssessment_Keerthana/blob/main/Resources/Other/Images/feature_comparison_table.png)

  - I’ve mapped each feature into an Effort vs Impact matrix so it’s easy to see trade-offs:
      * Green = Immediate High-Impact / Low Effort (01, 02, 03)
      * Blue = High-Impact / Medium Effort (04, 05, 06)
      * Purple = Medium Impact / Higher Effort (07, 08)
      * Orange = Niche Impact / High Effort (09, 10)
    **Effort (developer hours) VS Impact Visualization** - (***for a given feature, on the overall code quality and performance trends of the Service***)**:**
      - See full documentation for details.
      - ![plot Post MVP dev-effort-hrs vs impact with a normalized decimal score value](https://github.com/keerthanap8898/xCompany_TechAssessment_Keerthana/blob/main/Resources/Other/Images/dev-workload_vs_impact.png)

o MVP Repo Tree Diagram - so far ...
![MVP Repo Tree Diagram - so far ...](https://github.com/keerthanap8898/xCompany_TechAssessment_Keerthana/blob/main/Resources/Other/Images/MVP_folder_tree.png)
