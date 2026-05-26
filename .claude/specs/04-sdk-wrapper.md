# Feature: Lightweight SDK / Wrapper for LLM Call Observability

## Problem

Developers integrating LLMs into their applications have no built-in way to capture inference metadata — things like latency, token usage, or errors — without writing custom logging code for every call. This instrumentation is repetitive, fragile, and inconsistent across projects. Without a standard wrapper, observability data either never gets collected or gets implemented differently each time, making it impossible to aggregate and compare across services.

## Goal

A developer can drop the DeepX SDK into their existing LLM integration with minimal code changes and automatically have every call's metadata — including model, provider, latency, token usage, timestamps, status, and conversation ID — sent to the DeepX platform for analysis.

---

## User Stories

- As a **developer**, I want to wrap my existing LLM client with the DeepX SDK so that I don't have to rewrite my application logic to gain observability.
- As a **developer**, I want the SDK to capture latency and token usage automatically so that I can see performance trends without manual instrumentation.
- As a **developer**, I want to associate LLM calls with a conversation or session ID so that I can trace multi-turn interactions end to end.
- As a **developer**, I want the SDK to capture errors and failed requests so that I can monitor reliability without adding separate try/catch logging.
- As a **platform user**, I want to see previews of inputs and outputs alongside metadata so that I can quickly understand what was sent and received during any logged call.
- As a **developer**, I want the SDK to fail silently on ingestion errors so that my application's core LLM functionality is never disrupted by the observability layer.

---

## Scope

### In Scope
- A Python SDK package that wraps calls to supported LLM providers (starting with Google Gemini)
- Automatic capture of: model name, provider, request timestamp, response timestamp, latency (ms), input token count, output token count, total token count, request status (success / error), error message (if any), conversation/session ID, input text preview, output text preview
- Sending captured metadata to the DeepX ingestion API after each call completes
- Support for both streaming and non-streaming LLM calls
- Optional configuration: ingestion endpoint URL, API key for authentication, whether to include input/output previews, max preview length
- A `conversation_id` parameter the developer can supply to group related calls
- Silent failure mode — if the SDK cannot reach the ingestion API, the LLM response is still returned normally

### Out of Scope
- Support for providers other than Google Gemini in the initial release
- SDK packages for languages other than Python in the initial release
- Modifying or intercepting the LLM response payload in any way
- Storing raw prompts or full outputs (only previews/truncated versions)
- Real-time streaming of metadata mid-call; metadata is sent after call completion
- Authentication or user identity management within the SDK

---

## User Flow

1. Developer installs the DeepX SDK package in their Python project.
2. Developer imports the SDK and initializes it with their DeepX ingestion endpoint and (optionally) an API key.
3. Developer wraps their existing LLM client or call site with the DeepX wrapper — typically a one-line change.
4. Developer makes LLM calls exactly as before; the wrapper intercepts the call transparently.
5. The SDK records the timestamp when the call is made, sends the request to the LLM provider, and records the timestamp when the response arrives.
6. The SDK extracts token counts, model name, and provider from the response.
7. The SDK sends a metadata payload to the DeepX ingestion API in the background (non-blocking).
8. The developer receives the LLM response as normal — no change to their application's behavior.
9. If the developer supplies a `conversation_id`, the metadata is tagged with it so calls can be grouped in the DeepX dashboard.
10. If the ingestion call fails (network error, bad endpoint), the SDK logs a warning locally but does not raise an exception or affect the returned LLM response.

---

## Edge Cases & Constraints

- **Streaming responses**: Latency should reflect time-to-first-token and time-to-last-token; metadata is sent after the stream is fully consumed.
- **Failed LLM calls**: If the LLM provider returns an error, the SDK still sends a metadata record with `status: error` and the error message captured.
- **Missing token counts**: Some providers or response types may not include token usage; the SDK should send `null` for those fields rather than failing.
- **Preview truncation**: Input and output previews must be capped at a configurable max length (default 500 characters) to avoid sending large payloads to the ingestion API.
- **No conversation ID supplied**: Calls without a `conversation_id` are still logged; they appear as standalone (ungrouped) calls in the dashboard.
- **Ingestion API unavailable**: The SDK must not block the LLM response or raise exceptions — it should retry once, then drop the event and log a local warning.
- **Concurrent calls**: The SDK must handle multiple simultaneous LLM calls without metadata from one call contaminating another.

---

## Definition of Done

1. A developer can install the SDK and wrap their Gemini client with no more than 3 lines of new code.
2. Every successful LLM call results in a metadata record appearing in the DeepX platform containing: model, provider, latency, token counts, timestamps, status, and input/output previews.
3. Every failed LLM call results in a metadata record with `status: error` and the error message — the application itself is unaffected.
4. Streaming calls produce a complete metadata record after the stream finishes.
5. When a `conversation_id` is supplied, all calls with that ID are grouped correctly in the platform.
6. If the ingestion API is unreachable, the LLM response is still returned to the caller and no exception is raised.
7. Input/output previews are truncated to the configured max length and never exceed it.
8. The SDK ships with a README showing a minimal before/after integration example.
