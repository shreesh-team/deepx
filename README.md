## Think of it as 4 connected pieces:

```
User → Chatbot UI → [SDK Wrapper] → LLM API
                         ↓
                  Ingestion API → Database

```
'''
1. Chatbot — A simple chat interface that talks to an LLM (Claude, GPT, etc.) and remembers the conversation history.
2. SDK/Wrapper — Every time the chatbot calls the LLM, this wrapper intercepts it and records: how long it took, how many tokens were used, did it succeed, what was said. Then ships that log somewhere.
3. Ingestion API — A backend endpoint that receives those logs, validates them, and saves them to a database.
4. Database — Stores messages and logs in a sensible schema.
'''


The Actual Work, Layer by Layer
LayerWhat to BuildComplexityFrontendChat UI + conversation list/resume/cancelMediumLLM WrapperIntercept calls, capture metadata, POST to ingestionLow-MediumIngestion APIREST endpoint, validate, storeLow-MediumDatabaseSchema for messages + logsLowBonusStreaming, dashboards, Docker, PII redaction, k8sHigh

What They're Actually Evaluating

Can you design a clean schema (messages, sessions, logs)?
Do you understand observability (latency, tokens, errors)?
Can you make sensible tradeoffs and articulate them?
Is your code organized and readable?

The bonus items (k8s, event-based architecture, dashboards) are a stretch goal — they're separating good candidates from exceptional ones.

Recommended Stack (pragmatic)

Frontend: React + simple chat UI
LLM: Gemini or Claude or OpenAI (easiest APIs)
SDK: Python class wrapping the API call
Ingestion API: FastAPI (Python)
Database: PostgreSQL

