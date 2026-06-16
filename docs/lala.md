# Immediate Blockers - Enterprise Production Readiness Review

# Table of Contents

## A. `Sev-1`: Stop-Ship

### a. `consumer.go`

1. **Plaintext password stored in projection**: *credential exposure*
2. **Raw password written to immutable event log**: *permanent secret leakage*
3. **Reset token checked with normal string equality**: *token compromise risk*
4. **Ack after failed processing**: *event loss*
5. **No idempotency/dedupe**: *duplicate delivery corrupts state*
6. **No per-account serialization**: *out-of-order projection updates*
7. **No optimistic concurrency**: *stale writes overwrite newer state*
8. **Ignored JSON decode errors**: *malformed events mutate state*
9. **Unknown event types advance version**: *projection drift*
10. **Ignored JSON marshal errors**: *unsafe event construction*
11. **Password reset event lacks version**: *broken aggregate sequencing*
12. **Timestamp-derived event ID**: *unsafe retry/idempotency behavior*
13. **Blind projection version assignment**: *stale/gap/duplicate versions accepted*
14. **Non-deterministic replay timestamp**: *replay mismatch*

### b. `risk_scorer.py`

1. **Model evaluated on training data**: *invalid production metric*
2. **Accuracy used for rare compromise detection**: *misleading risk score*
3. **Full-history features likely leak future data**: *invalid offline evaluation*
4. **Scoring crashes for unseen accounts**: *production scoring failure*
5. **Raw account/IP logging**: *PII leakage*

## B. `Sev-2`: Must Fix Before QA / Prod-Like Testing

### a. `consumer.go`

1. **One goroutine per event**: *unbounded resource usage*
2. **Missing cancellation behavior**: *unsafe shutdown*
3. **No timeout/retry/backoff/jitter**: *unreliable failure handling*
4. **Opaque ack behavior**: *invisible ack failures*
5. **Unbounded IP history**: *memory/storage growth*
6. **Invalid IP accepted**: *bad state & bad features*
7. **No password-reset rate limits**: *abuse/brute-force risk*
8. **No idempotency key for reset mutation**: *duplicate event writes*
9. **Missing event metadata**: *weak event contract*
10. **Missing request/header validation**: *tenant/auth/schema risk*
11. **Weak logs**: *poor incident traceability*
12. **Weak store interface**: *cannot enforce event-sourcing semantics*
13. **No schema versioning/migrations**: *replay compatibility risk*
14. **No DLQ/quarantine**: *poison event risk*
15. **No rate-limit header handling**: *retry storms*
16. **No severity telemetry**: *weak incident response*
17. **No supply-chain controls**: *CVE/license/version risk*
18. **No CI coverage gates**: *weak release control*

### b. `risk_scorer.py`

1. **Full-history load into memory**: *not scalable*
2. **Empty-history divide risk**: *brittle feature generation*
3. **Oversimplified impossible travel**: *weak fraud feature*
4. **Dict-value feature ordering**: *silent model corruption*
5. **Missing-label crash risk**: *brittle training*
6. **No random seed/config**: *non-reproducible model*
7. **No model governance**: *unsafe ML release*
8. **No scoring schema validation**: *live crash/mis-score risk*
9. **Assumes `predict_proba` class order**: *wrong risk probability*
10. **No scoring request/header/rate-limit contract**: *overload/traceability risk*
11. **No Python/ML supply-chain controls**: *CVE/license/reproducibility risk*
12. **No ML observability/drift telemetry**: *undetected model degradation*

## C. `Sev-2.5`: High Priority

### a. `consumer.go`

1. **Unused `crypto/subtle`**: *build/security-quality issue*
2. **Standard logger only**: *weak structured logging*
3. **Unsafe concurrency implementation despite correct intent**: *scalability bug*

### b. `risk_scorer.py`

1. **Dependency version not visible**: *reproducibility risk*
2. **`print("ship it")`**: *unsafe release signal*
3. **Timestamp sorting is good but incomplete**: *point-in-time gap*

## D. `Sev-3`: Cleanup / Positive Patterns To Preserve

#### a. `consumer.go`

1. **Event struct is readable but under-specified**: *metadata gap*
2. **Store abstraction is useful but incomplete**: *contract gap*

### b. `risk_scorer.py`

1. **Feature extraction is compact but not production-safe**: *refactor candidate*
2. **Grouping by account is clear but not scalable**: *baseline-only pattern*


## E. Condensed Production Decision

1. ### **Do not merge**: 
- 
    - ***production blockers remain***
2. **Do not promote to normal QA**: 
- 
    - ***use QA only for failure reproduction unless blockers are remediated***


---

## A. `Sev-1`: Stop-Ship

### a. `consumer.go`

| Sl.# | Issue & Ln #                                                                                         | Blocker TL;DR                                                                 | Mitigate/Resolve                                                                                                                          | Notes/tests/long-term fixes                                                                                                                                                                                                                                                                                                            |
| ---: | ---------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|   1. | ***Ln***: 29-36, 89-92<br><br>**Plaintext password stored in projection via `PasswordPlain`**        | Direct credential exposure in an identity system.                             | Remove `PasswordPlain`.<br><br>Store only approved password-hash metadata.                                                                | Test plaintext never appears in state, logs, traces, or events.<br><br>**Refs**: [*cheatsheetseries.owasp.org/password-storage*](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), [*cwe.mitre.org/CWE-256*](https://cwe.mitre.org/data/definitions/256.html)                                         |
|   2. | ***Ln***: 101-109<br><br>**Raw password written into immutable event payload as `NewPassword`**      | Permanently pollutes append-only audit log with credentials.                  | Never place passwords, tokens, or secrets in events.<br><br>Append safe metadata only.                                                    | Add event-schema forbidden-field tests.<br><br>Add secret scanning for generated event fixtures.<br><br>**Refs**: [*cheatsheetseries.owasp.org/logging*](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)                                                                                                      |
|   3. | ***Ln***: 101-103<br><br>**Reset token compared with normal string equality**                        | Timing/replay risk; reset-token lifecycle incomplete.                         | Store hashed reset tokens.<br><br>Use constant-time compare.<br><br>Enforce expiry, single-use, scope, account binding, & attempt limits. | `crypto/subtle` is imported but unused.<br><br>Tests: expired token, reused token, wrong account, attempt throttling.<br><br>**Refs**: [*pkg.go.dev/crypto/subtle*](https://pkg.go.dev/crypto/subtle), [*cheatsheetseries.owasp.org/forgot-password*](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html) |
|   4. | ***Ln***: 62-65<br><br>**Broker `ack(e)` runs even when `apply` fails**                              | Failed events can be permanently lost.                                        | Ack only after durable success.<br><br>Retry, nack, or DLQ on failure.                                                                    | **Tests**: `LoadState` failure, `SaveState` failure, validation failure must not ack success.                                                                                                                                                                                                                                          |
|   5. | ***Ln***: 56-66, 71-96<br><br>**No idempotency/dedupe despite at-least-once delivery**               | Duplicate delivery corrupts counters, IP history, password state, & versions. | Track processed `Event.ID` atomically or enforce version-idempotency.                                                                     | **Tests**: duplicate `LoginFailed` does not increment twice.<br><br>Duplicate `LoginSucceeded` does not append twice.                                                                                                                                                                                                                  |
|   6. | ***Ln***: 56-66, 71-96<br><br>**No per-account serialization**                                       | Same-account events can apply out of order.                                   | Partition/serialize workers by account/aggregate key.                                                                                     | Add race tests & same-account ordering tests.<br><br>**Refs**: [*go.dev/race-detector*](https://go.dev/doc/articles/race_detector)                                                                                                                                                                                                     |
|   7. | ***Ln***: 39-43, 94-96<br><br>**`SaveState` has no optimistic concurrency / expected-version check** | Stale projection writes can overwrite newer account state.                    | Change API to `SaveState(ctx, state, expectedVersion)` with CAS/transaction semantics.                                                    | **Tests**: stale write, gap version, duplicate version, concurrent same-account update.                                                                                                                                                                                                                                                |
|   8. | ***Ln***: 82-91<br><br>**`json.Unmarshal` errors ignored**                                           | Malformed payloads silently mutate state with zero values.                    | Check all decode errors.<br><br>Validate schema, required fields, field types, & payload sizes.                                           | **Tests**: malformed JSON, missing fields, wrong types, empty IP/password.<br><br>**Refs**: [*pkg.go.dev/encoding/json*](https://pkg.go.dev/encoding/json)                                                                                                                                                                             |
|   9. | ***Ln***: 80-92, 94-96<br><br>**Unknown event types silently advance projection version**            | Projection can skip required state changes while moving forward.              | Add `default` case.<br><br>Reject/quarantine unknown types.<br><br>Do not save as success.                                                | **Tests**: unknown type does not advance version.<br><br>DLQ/quarantine path emits telemetry.                                                                                                                                                                                                                                          |
|  10. | ***Ln***: 103<br><br>**`json.Marshal` error ignored**                                                | Bad payload construction can silently proceed.                                | Check marshal error.<br><br>Prefer typed event-schema encoder.                                                                            | Add forced marshal-error test where feasible.<br><br>**Refs**: [*go.dev/error-handling*](https://go.dev/blog/error-handling-and-go)                                                                                                                                                                                                    |
|  11. | ***Ln***: 104-109<br><br>**Password reset appends `PasswordChanged` with no `Version`**              | Breaks aggregate sequencing & deterministic replay.                           | Append via event store that atomically assigns next aggregate version.                                                                    | **Tests**: reset emits correct next version.<br><br>Zero-version mutation rejected.                                                                                                                                                                                                                                                    |
|  12. | ***Ln***: 105<br><br>**Event ID generated from timestamp**                                           | Unsafe for retries/idempotency; collision & replay ambiguity.                 | Use UUID/ULID or idempotency-key-derived event ID.                                                                                        | **Tests**: retry same request uses same idempotency key/event result.                                                                                                                                                                                                                                                                  |
|  13. | ***Ln***: 94<br><br>**Projection version assigned blindly from event**                               | Allows stale, duplicate, zero, or gap versions.                               | Validate `event.Version == state.Version + 1`, except safe duplicate no-op.                                                               | **Tests**: stale, gap, duplicate, & zero-version handling.                                                                                                                                                                                                                                                                             |
|  14. | ***Ln***: 95<br><br>**`time.Now()` mixed into replayed projection**                                  | Same event stream can rebuild to different state.                             | Separate deterministic domain state from operational rebuild metadata.                                                                    | Replay same stream twice must produce identical domain projection.<br><br>**Refs**: [*pkg.go.dev/time*](https://pkg.go.dev/time)                                                                                                                                                                                                       |

### b. `risk_scorer.py`

| Sl.# | Issue & Ln #                                                                    | Blocker TL;DR                                                                   | Mitigate/Resolve                                                               | Notes/tests/long-term fixes                                                                                                                                                                                                                                                                             |
| ---: | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|   1. | ***Ln***: 60-70<br><br>**Model trains & evaluates on same data**                | Training accuracy is invalid for production readiness.                          | Use time-based train/validation/test split.                                    | CI must reject training-set-only metrics.<br><br>**Refs**: [*scikit-learn.org/model-evaluation*](https://scikit-learn.org/stable/modules/model_evaluation.html), [*scikit-learn.org/train-test-split*](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.train_test_split.html) |
|   2. | ***Ln***: 7-8, 67-69<br><br>**Accuracy used for rare compromise detection**     | Always-negative classifier can look excellent when compromise rate is under 1%. | Use PR-AUC, recall at fixed FPR, precision@K, calibration, & threshold curves. | Add rare-class baseline & threshold tests.<br><br>**Refs**: [*scikit-learn.org/precision-recall*](https://scikit-learn.org/stable/modules/model_evaluation.html#precision-recall-f-measure-metrics)                                                                                                     |
|   3. | ***Ln***: 45-57, 73-76<br><br>**Full-history features likely leak future data** | Offline training may use events unavailable at scoring time.                    | Build point-in-time features with event-time cutoff.                           | **Tests**: no post-score events in feature window.<br><br>Label window starts after feature window.                                                                                                                                                                                                     |
|   4. | ***Ln***: 73-76<br><br>**Scoring crashes for unseen accounts**                  | New/sparse accounts are normal production cases.                                | Add cold-start defaults & safe fallback score.                                 | **Tests**: missing account, missing fields, empty history, sparse history.                                                                                                                                                                                                                              |
|   5. | ***Ln***: 49<br><br>**Logs account ID & raw IP history**                        | PII leakage into app logs.                                                      | Remove raw IP/account logging.<br><br>Use aggregates, hashes, or redaction.    | Add log-redaction tests.<br><br>**Refs**: [*docs.python.org/logging*](https://docs.python.org/3/library/logging.html), [*cheatsheetseries.owasp.org/logging*](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)                                                                  |

---

## B. `Sev-2`: Must Fix Before QA / Prod-Like Testing

### a. `consumer.go`

| Sl.# | Issue & Ln #                                                                        | Blocker TL;DR                                                                         | Mitigate/Resolve                                                                                   | Notes/tests/long-term fixes                                                                                                                                                                                                                         |
| ---: | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|   1. | ***Ln***: 54-66<br><br>**One goroutine per event**                                  | Unbounded concurrency can exhaust memory, DB connections, FDs, & CPU.                 | Use bounded worker pool, semaphores, queues, & backpressure.                                       | Burst-load test must assert max concurrency.<br><br>**Refs**: [*pkg.go.dev/sync*](https://pkg.go.dev/sync)                                                                                                                                          |
|   2. | ***Ln***: 56-66<br><br>**No explicit cancellation behavior inside processing loop** | Shutdown may continue work or ack unexpectedly.                                       | Check `ctx.Done()` before scheduling & inside workers.                                             | Test graceful shutdown with in-flight events.<br><br>**Refs**: [*pkg.go.dev/context*](https://pkg.go.dev/context)                                                                                                                                   |
|   3. | ***Ln***: 71-96<br><br>**No timeout/retry/backoff/jitter policy**                   | Transient failures can cause loss, storms, or stuck work.                             | Add deadlines, retry budget, capped exponential backoff + jitter.                                  | Fake-clock tests for timeout/backoff.<br><br>**Refs**: [*rfc-editor.org/RFC-9110-Retry-After*](https://www.rfc-editor.org/rfc/rfc9110.html#name-retry-after)                                                                                        |
|   4. | ***Ln***: 62-65, 115<br><br>**`ack` is opaque & not error-aware**                   | Ack failures are invisible.                                                           | Make `ack` return error.<br><br>Handle retry/metric/log policy.                                    | Test ack failure path & broker redelivery behavior.                                                                                                                                                                                                 |
|   5. | ***Ln***: 85<br><br>**`LastSeenIPs` grows unbounded**                               | Memory/storage growth & duplicate amplification.                                      | Bound, dedupe, TTL, or move to normalized/audit feature store.                                     | **Tests**: IP cap, dedupe, history compaction.                                                                                                                                                                                                      |
|   6. | ***Ln***: 83-85<br><br>**Empty/invalid IP accepted**                                | Bad projection & bad model features.                                                  | Validate IP format & required payload fields.                                                      | Payload validation tests for empty/malformed IP.                                                                                                                                                                                                    |
|   7. | ***Ln***: 101-112<br><br>**Password reset lacks rate limiting**                     | Enables reset abuse & brute-force attempts.                                           | Add per-account, per-IP, per-tenant, per-token attempt limits.                                     | Tests for throttling/429 behavior.<br><br>**Refs**: [*rfc-editor.org/RFC-6585-429*](https://www.rfc-editor.org/rfc/rfc6585#section-4)                                                                                                               |
|   8. | ***Ln***: 101-112<br><br>**No idempotency key for reset mutation**                  | Retries can append duplicate password-change events.                                  | Require idempotency key & persist replayed result.                                                 | Same key/same payload returns original result.<br><br>Same key/different payload rejected.                                                                                                                                                          |
|   9. | ***Ln***: 18-26<br><br>**Event lacks explicit schema/content metadata**             | Weak long-term compatibility for append-only events.                                  | Add schema version, content type, producer, trace/correlation fields.                              | Contract tests with golden events.                                                                                                                                                                                                                  |
|  10. | ***Ln***: 18-26, 71-96<br><br>**No request/header metadata validation implied**     | Tenant, partition, auth, content-type, idempotency, trace context cannot be verified. | Validate required API/broker envelope fields before append/apply.                                  | **Tests**: missing tenant, mismatched account, unsupported content type, missing schema version.                                                                                                                                                    |
|  11. | ***Ln***: 62-65<br><br>**Logs only event ID & error**                               | Insufficient incident traceability.                                                   | Use structured logging with trace ID, event ID, account hash, tenant, partition, severity.         | Confirm no secrets/PII in logs.<br><br>**Refs**: [*cheatsheetseries.owasp.org/logging*](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)                                                                                    |
|  12. | ***Ln***: 39-43<br><br>**Store interface too weak for event sourcing**              | Cannot express CAS, dedupe, transactions, DLQ, or idempotency.                        | Extend store API for atomic append, save-with-version, processed-event markers.                    | Integration tests with conflict simulation.                                                                                                                                                                                                         |
|  13. | ***Ln***: 80-92<br><br>**No schema versioning/migrations for event payloads**       | Old/new permanent events may not replay safely.                                       | Versioned event schemas & compatibility policy.                                                    | Golden replay fixtures for old versions.                                                                                                                                                                                                            |
|  14. | ***Ln***: 71-96<br><br>**No DLQ/quarantine path**                                   | Poison events can loop or be dropped.                                                 | Route invalid/non-retryable events to DLQ with metadata.                                           | Tests for malformed/unknown events to DLQ.                                                                                                                                                                                                          |
|  15. | ***Ln***: All<br><br>**No downstream rate-limit handling**                          | 429/503 can trigger retry storms or event loss.                                       | Honor `Retry-After`, `X-RateLimit-*`; add adaptive throttling & circuit breakers.                  | Fake server tests for 429/503 & headers.<br><br>**Refs**: [*rfc-editor.org/RFC-9110-Retry-After*](https://www.rfc-editor.org/rfc/rfc9110.html#name-retry-after), [*rfc-editor.org/RFC-9333-RateLimit*](https://www.rfc-editor.org/rfc/rfc9333.html) |
|  16. | ***Ln***: All<br><br>**No Sev-1/2/2.5/3 telemetry model**                           | Incidents cannot be routed or triaged reliably.                                       | Metrics & alerts for event loss, DLQ, lag, rate limits, validation failures, projection conflicts. | Alert tests for each severity.                                                                                                                                                                                                                      |
|  17. | ***Ln***: All<br><br>**No supply-chain controls shown**                             | Enterprise prod needs CVE, version, package, & license governance.                    | Pin deps/images; generate SBOM; run CVE/license scans; track EOL.                                  | Block critical CVEs, unknown licenses, & prohibited licenses.<br><br>**Refs**: [*cyclonedx.org/SBOM*](https://cyclonedx.org/), [*spdx.org/licenses*](https://spdx.org/licenses/), [*nvd.nist.gov*](https://nvd.nist.gov/)                           |
|  18. | ***Ln***: All<br><br>**No CI coverage gates shown**                                 | Critical AI-generated code lacks release protection.                                  | Require unit/validation/regression/integration tests & 80-85% coverage.                            | Add changed-line coverage, race detector, lint, secret scan.                                                                                                                                                                                        |

### b. `risk_scorer.py`

| Sl.# | Issue & Ln #                                                                         | Blocker TL;DR                                                                | Mitigate/Resolve                                                                                       | Notes/tests/long-term fixes                                                                                                                                                                                                                                                            |
| ---: | ------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|   1. | ***Ln***: 19-24, 79-82<br><br>**Loads full event history into memory**               | Not scalable for long histories & hundreds of thousands of accounts.         | Use streaming/partitioned reads, incremental features, feature store.                                  | Large-history memory/perf tests.                                                                                                                                                                                                                                                       |
|   2. | ***Ln***: 45-57<br><br>**`failed_ratio` divides by `len(evs)` with no empty guard**  | Empty/sparse grouped data path can fail.                                     | Define empty-history defaults.                                                                         | Unit test empty event list/account.                                                                                                                                                                                                                                                    |
|   3. | ***Ln***: 39-42<br><br>**`detect_impossible_travel` is oversimplified**              | Country-count heuristic is not actual impossible travel.                     | Use geo distance/time deltas & validated feature definition.                                           | Feature-review test & doc.                                                                                                                                                                                                                                                             |
|   4. | ***Ln***: 61, 76<br><br>**Feature vector uses `dict.values()` order**                | Future refactor can silently corrupt model input.                            | Define `FEATURE_COLUMNS`; vectorize by explicit schema.                                                | Schema compatibility test.<br><br>**Refs**: [*docs.python.org/dict*](https://docs.python.org/3/library/stdtypes.html#mapping-types-dict)                                                                                                                                               |
|   5. | ***Ln***: 62<br><br>**Label lookup can crash on missing label**                      | Training can fail or create biased workaround risk.                          | Validate label coverage; define unlabeled-account policy.                                              | Tests for missing/extra labels.                                                                                                                                                                                                                                                        |
|   6. | ***Ln***: 64<br><br>**`RandomForestClassifier()` has no seed/config**                | Non-reproducible model artifacts.                                            | Set `random_state`; store config/code/data versions.                                                   | Deterministic training test.<br><br>**Refs**: [*scikit-learn.org/RandomForestClassifier*](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html)                                                                                              |
|   7. | ***Ln***: 64-70<br><br>**No model artifact governance**                              | No model version, registry, approval, rollback, threshold record.            | Store model version, feature schema, metrics, threshold, data snapshot.                                | Release gate requires model card/approval.                                                                                                                                                                                                                                             |
|   8. | ***Ln***: 73-76<br><br>**No event schema validation at scoring**                     | Bad live events can crash or mis-score.                                      | Validate required fields & types before scoring.                                                       | **Tests**: missing `account_id`, malformed event.                                                                                                                                                                                                                                      |
|   9. | ***Ln***: 76<br><br>**Assumes `predict_proba(...)[0][1]` maps to positive class**    | Wrong class order can return wrong risk probability.                         | Use `clf.classes_` to locate positive class index.                                                     | Test class-order handling.<br><br>**Refs**: [*scikit-learn.org/predict_proba*](https://scikit-learn.org/stable/glossary.html#term-predict_proba)                                                                                                                                       |
|  10. | ***Ln***: All<br><br>**No request/header/rate-limit contract for live scoring path** | Scoring can be overloaded or lose traceability.                              | Require request ID, trace ID, tenant/account metadata, schema version, & idempotency where applicable. | Metrics for scoring latency, throttling, missing headers.                                                                                                                                                                                                                              |
|  11. | ***Ln***: All<br><br>**No supply-chain controls for Python/ML deps**                 | Unpinned ML deps can create CVE, license, reproducibility, & migration risk. | Pin Python/sklearn versions; lock deps; SBOM; CVE/license scan.                                        | Block unknown licenses & critical CVEs.<br><br>**Refs**: [*pip.pypa.io/requirements*](https://pip.pypa.io/en/stable/reference/requirements-file-format/), [*packaging.python.org/dependency-specifiers*](https://packaging.python.org/en/latest/specifications/dependency-specifiers/) |
|  12. | ***Ln***: All<br><br>**No ML observability/drift telemetry**                         | Live model degradation cannot be detected.                                   | Emit score distribution, feature drift, missing feature rate, threshold crossings, latency.            | Drift alerts & shadow-mode metrics.                                                                                                                                                                                                                                                    |

---

## C. `Sev-2.5`: High Priority

### a. `consumer.go`

| Sl.# | Issue & Ln #                                                                                | Blocker TL;DR                                            | Mitigate/Resolve                                                      | Notes/tests/long-term fixes                                                                                                |
| ---: | ------------------------------------------------------------------------------------------- | -------------------------------------------------------- | --------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
|   1. | ***Ln***: 10<br><br>**Unused `crypto/subtle` import**                                       | Go build may fail; also signals abandoned security work. | Remove import or implement constant-time token comparison.            | Run `go test ./...` in CI.<br><br>**Refs**: [*go.dev/unused-imports*](https://go.dev/doc/faq#unused_variables_and_imports) |
|   2. | ***Ln***: 13, 63<br><br>**Standard logger only, no structured logging**                     | Poor prod diagnostics & weak log governance.             | Use structured logger with redaction & standard fields.               | Include trace/event/tenant IDs.<br><br>Verify no secrets.                                                                  |
|   3. | ***Ln***: 54-55<br><br>**Comment identifies throughput issue but implementation is unsafe** | Good intent, poor concurrency model.                     | Replace goroutine-per-event with partition-aware bounded worker pool. | Keep goal: slow account should not block unrelated accounts.                                                               |

### b. `risk_scorer.py`

| Sl.# | Issue & Ln #                                                                    | Blocker TL;DR                                                    | Mitigate/Resolve                                              | Notes/tests/long-term fixes                        |
| ---: | ------------------------------------------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------- | -------------------------------------------------- |
|   1. | ***Ln***: 14<br><br>**Dependency version not visible**                          | Reproducibility, CVE, & license posture unclear.                 | Pin `scikit-learn` & transitive deps in lockfile.             | Add dependency/CVE/license scan.                   |
|   2. | ***Ln***: 67-69<br><br>**`print("ship it")` release signal**                    | Unsafe promotion signal for security ML.                         | Remove print-based approval.<br><br>Use formal release gates. | CI should fail on training-only approval language. |
|   3. | ***Ln***: 47-48<br><br>**Events sorted by timestamp before feature extraction** | Good local ordering habit but insufficient point-in-time safety. | Preserve sorting but add cutoff-aware feature generation.     | Positive pattern to keep, with leakage tests.      |

---

## D. `Sev-3`: Cleanup / Positive Patterns To Preserve

### a. `consumer.go`

| Sl.# | Issue & Ln #                                                                                     | Blocker TL;DR                                   | Mitigate/Resolve                                                                                       | Notes/tests/long-term fixes                      |
| ---: | ------------------------------------------------------------------------------------------------ | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------ |
|   1. | ***Ln***: 18-26<br><br>**Event struct is readable but under-specified**                          | Good start, missing enterprise metadata.        | Keep typed event struct.<br><br>Add schema version, content type, trace ID, tenant/partition metadata. | Positive pattern: explicit event object.         |
|   2. | ***Ln***: 39-43<br><br>**Store abstraction improves testability but lacks production semantics** | Useful interface boundary, incomplete contract. | Preserve abstraction.<br><br>Extend for CAS, idempotency, DLQ, transactions.                           | Positive pattern: side effects behind interface. |

### b. `risk_scorer.py`

| Sl.# | Issue & Ln #                                                          | Blocker TL;DR                                     | Mitigate/Resolve                                                                         | Notes/tests/long-term fixes                  |
| ---: | --------------------------------------------------------------------- | ------------------------------------------------- | ---------------------------------------------------------------------------------------- | -------------------------------------------- |
|   1. | ***Ln***: 45-57<br><br>**Feature extraction is compact & reviewable** | Good structure, but not production-safe yet.      | Keep small feature-builder shape.<br><br>Make it schema-bound, cutoff-aware, & scalable. | Positive pattern for assistant skill memory. |
|   2. | ***Ln***: 32-36<br><br>**Grouping by account is simple & clear**      | Useful baseline organization, not scalable alone. | Replace with streaming/partitioned grouping for prod scale.                              | Positive pattern for small tests/fixtures.   |

---

## E. Condensed Production Decision

Do not merge or promote this code to production.

Do not push to normal QA as-is unless QA is explicitly being used for failure reproduction.

### Primary blockers

1. Credential handling is unsafe.
2. Immutable event log can be polluted with secrets.
3. At-least-once delivery is not handled idempotently.
4. Same-account ordering is not preserved.
5. Projection writes are not concurrency-safe.
6. Failed events can be acknowledged & lost.
7. Event schemas are not validated or versioned.
8. Rate-limit headers, request metadata, & throttling are not enforced.
9. Risk model evaluation is invalid for rare-event compromise detection.
10. Feature generation likely leaks future data.
11. Scoring path is brittle for unseen accounts.
12. Logs can leak PII.
13. Supply-chain, CVE, package-version, license, & SBOM controls are absent.
14. CI coverage gates across unit, validation, regression, & integration tests are absent.
