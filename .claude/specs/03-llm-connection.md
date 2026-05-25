# Feature: LLM Connection — Live Chat via Google Gemini

## Problem

Users of the DeepX observability platform need to send conversations to Google Gemini models through the UI. The UI sends the request to the DeepX backend, which in turn calls the Gemini API — the backend acts as the intermediary, not the browser. Without this, users cannot run live conversations or observe real model responses through the platform.

## Goal

A user can supply a Gemini API key and conversation context, see the response stream in real time in the UI, and have the full exchange automatically logged in the platform. The model used is always `gemini-3-flash-preview`, regardless of what model name the UI sends.

---

## User Stories

- As a **developer**, I want to **send a conversation to Gemini using my own API key** so that **I can test my Gemini integrations without leaving the platform**.
- As a **developer**, I want to **see the model's response appear in real time as it streams** so that **the experience feels as responsive as talking to the model directly**.
- As a **platform user**, I want to **every AI response to be automatically saved** so that **I can review the conversation history and usage later**.

---

## Scope

### In Scope
- Accepting an API key and conversation context (ordered list of user/AI turns) from the frontend
- Always calling `gemini-3-flash-preview`, ignoring any model name sent by the UI
- Forwarding the full conversation context to the model
- Streaming the model's response back to the UI in real time
- Saving the completed AI response (and any relevant metadata) to the database

### Out of Scope
- Managing or storing API keys on the server beyond the lifetime of a single request
- Validating whether an API key has sufficient quota or billing enabled
- Supporting multi-modal inputs (images, audio, files)
- Supporting any provider other than Google Gemini
- Selecting or switching providers mid-conversation
- Rate limiting or quota enforcement by the platform

---

## User Flow

1. User opens a conversation in the DeepX UI and enters their Gemini API key.
2. User pastes or enters their API key for that provider.
3. User types a message and sends it. The UI includes the full conversation history (all prior turns) with the request.
4. The UI sends the request (API key, conversation context) to the DeepX backend. The backend always calls `gemini-3-flash-preview` via the Gemini API, regardless of any model name the UI may include.
5. The model's response begins appearing in the UI as it streams — word by word or chunk by chunk — without waiting for the full response.
6. Once the response is complete, it is saved to the conversation history in the database.
7. The completed message appears in the conversation view alongside the prior turns.

---

## Edge Cases & Constraints

- If the API key is invalid or rejected by Gemini, the user sees a meaningful error (e.g. "API key rejected") rather than a generic failure.
- If the model produces an error mid-stream (e.g. safety filter, context length exceeded), the partial response so far should still be shown and saved, with the error reason surfaced to the user.
- If the conversation context is empty (no prior turns), the request should still proceed with just the new user message.
- Long-running responses should not time out prematurely — the connection must stay open until the model finishes or explicitly errors.
- The API key must not be logged, stored, or persisted beyond the duration of the request.

---

## Definition of Done

1. User can send a conversation with an API key from the UI and receive a response via `gemini-3-flash-preview`.
2. The response streams into the UI in real time — visible before the model finishes generating.
3. The completed AI response is saved to the database and visible in conversation history on page reload.
4. If the API key is invalid, the UI shows a clear error message and no partial data is saved.
5. Partial responses from an interrupted stream are saved with an error state, not silently dropped.
