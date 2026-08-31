# The Universal Bounty Fleet

> Autonomous multi-agent bounty execution with a fail-closed Victory Audit. Fortified Enterprise Fleet track.

Cataloged agents (Intake, Executor, Auditor) claim funded GitHub issues, open a draft PR, and **cannot merge until a separate auditor passes**. The live camera is `/console` — not a chatbot.

---

## 🏛️ System Architecture

```
[GitHub Platform / Webhooks]
           │
           ▼
[Cloud Run Webhook Gateway (FastAPI / Stateless)]
   ├── HMAC-SHA256 Webhook Verification
   └── Firestore Ephemeral Idempotency & Distributed Lock
           │
     ┌─────┴────────────────────────────────┐
     ▼                                      ▼
[Intake Taskmaster Agent]         [Victory Audit Fleet Agent]
  ├── 5-Stage Sniper Filter         ├── 3-Pillar Security Analyzer
  │   ├── Platform Whitelist/Blacklist  │   ├── Cryptographic Integrity (No fake host mocks)
  │   ├── Archived Repo Gate            │   ├── Authorization Enforcement (require_auth)
  │   └── Subjective Task Disqualifier  │   └── Assertion Preservation (No loosened checks)
  ├── Semantic Escrow Engine        ├── Vertex AI Gemini Code Reasoner
  │   └── Vertex AI Gemini 3.7 Pro  └── Native GitHub PR Review Submitter
  └── Autonomous Intent Staking         ├── APPROVE / REQUEST_CHANGES
      ├── Post /try on Issue            └── Headless gh pr ready Trigger
      └── Multi-chain Payout Block
```

---

## 🚀 Key Modules & Components

1. **Stateless Webhook Gateway (`app/main.py`)**:
   - High-throughput FastAPI event dispatcher deployed to Google Cloud Run.
   - HMAC-SHA256 signature verification (`app/security/hmac_validator.py`).
   - Ephemeral event deduplication and distributed locking (`app/security/firestore_lock.py`).

2. **Security & Utilities (`app/security/`, `app/utils/`)**:
   - `hmac_validator.py`: Timing-attack resistant signature validation.
   - `firestore_lock.py`: Atomic distributed locking with configurable TTL and in-memory mock fallback.
   - `vertex_client.py`: Vertex AI client factory managing ADC OAuth2 credentials, project quota assignment (`odin-500008`), and Gemini 3.7 Pro (`gemini-3.7-pro`) via the Google GenAI SDK. Antigravity sidecars use the same 3.7 / Pro family.
   - `github_client.py`: Stateless GitHub REST & GraphQL API client for issue commenting, PR reviews, and automated draft-to-ready status transitions.

3. **Intake Taskmaster (`app/intake/`)**:
   - 5-Stage Sniper Filter (Banned platforms: Algora, Polar, twentyhq/twenty, Opire; Archive checks; Competitor claim detector).
   - Vertex AI Semantic Escrow Verifier: Multicurrency financial parser and escrow proof validation.
   - Autonomous Intent Staking: Posts `/try` comments and appends standard Web3 payout routing.

4. **Victory Audit Fleet (`app/audit/`)**:
   - 3-Pillar Murder Board Analyzer:
     * **Pillar 1**: Cryptographic Integrity (Zero mock host functions, real EC primitives).
     * **Pillar 2**: Authorization Enforcement (Mandatory `require_auth()` / caller validation on all state transitions).
     * **Pillar 3**: Assertion Preservation (Original test assertions intact; zero bypassed assertions).
   - Native GitHub PR Review Submitter (`APPROVE` or `REQUEST_CHANGES` with file/line annotations).

---

## 🔒 Security & Payout Routing Invariants

### Web3 Payout Routing
All bounty engagements conclude with the standardized multi-chain payout block:
```markdown
## Payout Routing
- **EVM (Base/Arbitrum/Polygon/ETH):** `0xF7b492cCBA473254E392Df444ce2dF4BE0AA29F4`
- **Stellar:** `GCL6OXAMLD75BMTINA6EMRUDWK5THQUSHMYNLSNBCJAPZJHNYJTUNIBC`
```

---

## 🛠️ Configuration & Deployment

### Environment Variables
```bash
GCP_PROJECT="odin-500008"
GCP_REGION="us-central1"
VERTEX_AI_LOCATION="us-central1"
GITHUB_TOKEN="ghp_..."
GITHUB_WEBHOOK_SECRET="your-webhook-secret"
PORT=8080
```

### Local Development
```bash
# Setup environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run test suite
pytest tests/ -v

# Run local development server
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# Design the Fleet Console without a rebuild (proxies /api and /health to :8080)
cd console-ui && npm install && npm run dev

# Export the console into app/static/console for uvicorn / Cloud Run
cd console-ui && npm run build
```

Open the Fleet Console at [http://127.0.0.1:8080/console](http://127.0.0.1:8080/console), or the Vite preview at [http://127.0.0.1:5173/console/](http://127.0.0.1:5173/console/). Routes: `/console` live camera, `/console/ops` sprint stats, `/console/history` all sprint PRs, `/console/claims` issue pipeline, `/console/archive` parked prior history. The live page polls `/health`, `/api/bounties/latest`, and `/api/registry` every 2s. History pages read `/api/history` (the cleaned overseer workbook). Cloud Run stays one service: the Dockerfile builds `console-ui` and copies the export into the Python image.

**Live camera (Cloud Run):** [https://bounty-fleet-gateway-113376683730.us-central1.run.app/console](https://bounty-fleet-gateway-113376683730.us-central1.run.app/console)

GCP: `odin-500008` / `us-central1` / service `bounty-fleet-gateway` / Firestore `bounty_memory`. Architecture diagram: [`docs/Universal_Bounty_Fleet_Architecture.png`](docs/Universal_Bounty_Fleet_Architecture.png).

---

## 🧪 Reproducible testing (judges)

No GCP login required for the local path:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export APP_ENV=test USE_IN_MEMORY_FIRESTORE=true GCP_PROJECT=odin-500008
pytest tests/ -q
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Then open `http://127.0.0.1:8080/console` (also `/console/ops`, `/console/history`, `/console/claims`, `/api/registry`).

The suite is five tiers: feature, boundary, combinations, real-world scenarios, and adversarial / security stress tests.
