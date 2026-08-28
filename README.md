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
  │   └── Vertex AI Gemini 3.5      └── Native GitHub PR Review Submitter
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
   - `vertex_client.py`: Vertex AI client factory managing ADC OAuth2 credentials, project quota assignment (`odin-500008`), and Gemini model instances (`gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-3.5-flash`).
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

Open the Fleet Console at [http://127.0.0.1:8080/console](http://127.0.0.1:8080/console), or the Vite preview at [http://127.0.0.1:5173/console/](http://127.0.0.1:5173/console/). It polls `/health`, `/api/bounties/latest`, and `/api/registry` every 2s. Live GitHub webhooks write the Memory Bank; if none have landed yet, a planted-cheat fixture (`auth_bypass`, merge blocked) is shown so the screen is filmable. Cloud Run stays one service: the Dockerfile builds `console-ui` and copies the export into the Python image.

---

## 🧪 Testing Strategy

The test suite enforces a 5-tier testing methodology:
- **Tier 1**: Feature unit coverage.
- **Tier 2**: Boundary and edge-case testing.
- **Tier 3**: Cross-feature combinations.
- **Tier 4**: Real-world application scenarios.
- **Tier 5**: Adversarial and security stress tests.
