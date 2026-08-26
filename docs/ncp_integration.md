# NCP Integration Boundary

This document defines the order and safety boundary for NCP services.  The
P48 scoped retrieval/evidence path remains frozen while these integrations are
prepared.

## NCP-1: ready in code, disabled by default

### Object Storage

`src.integrations.ncp_object_storage.NcpObjectStorageArtifacts` only uploads a
file when a caller explicitly invokes it.  It records its SHA-256 in object
metadata and refuses to overwrite the same key with different content.

Use it only for immutable, reviewed artifacts such as a frozen dataset,
manifest, evaluation result, or release metadata.  It does not automatically
upload the corpus, drafts, traces, or any runtime request data.

Required server-only variables:

```text
NCP_OBJECT_STORAGE_ENABLED=true
NCP_OBJECT_ENDPOINT=https://kr.object.ncloudstorage.com
NCP_ACCESS_KEY=...
NCP_SECRET_KEY=...
NCP_OBJECT_BUCKET=pension-agent-artifacts
```

Suggested key layout:

```text
datasets/gold-seed-v2/
training/exports/
training/manifests/
evaluation/
releases/
traces/cla/
```

### Cloud Log Analytics custom log

Set `PENSION_TRACE_PATH` on the server, for example
`/var/log/pension-agent/answer_trace.log`.  The browser scoped runtime then
writes one compact JSONL trace per request.  Configure the CLA agent in NCP
Console to collect that file; CLA setup and retention remain server/operator
configuration.

The default trace contains pipeline IDs and status only.  It does **not**
include answer text, evidence text, API keys, or the raw question.  Set
`PENSION_TRACE_INCLUDE_QUESTION=true` only after an explicit retention/privacy
decision.

Trace failures are swallowed by design and cannot alter an `/answer` response.

## Deferred integrations

- **CLOVA Tuning:** blocked until P49-2H data creation, QA, human approval,
  export, and frozen P50 holdout.  It may replace only the final generator;
  resolver, selector, binder, retrieval, and evidence gate stay unchanged.
- **CLOVA Reranker:** start only as a read-only BM25 shadow after its separate
  eval gate.  It must never become answer text or bypass direct-evidence
  validation.
- **API Gateway:** configure after the server's `/answer` and `/health`
  contracts are smoke-tested.  Do not add a mandatory gateway header or change
  the evaluator's method/body/response schema.

## Deployment check

Before enabling either NCP-1 setting on a server:

1. Keep every secret in the server environment, never Git or Object Storage
   manifest metadata.
2. Verify the mounted log directory is writable by the API process.
3. Call `/health`, then a DB operation-party question, and confirm the response
   is unchanged while a trace line appears.
4. Verify a test artifact upload under a staging-only, versioned key; a second
   upload with the same content must be idempotent.
