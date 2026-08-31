# Devpost lock — paste these answers

Category: **Fortified Enterprise Fleet**. One repo only.

## Additional info

| Field | Answer |
| --- | --- |
| Startup Excellence | Leave unchecked |
| Submitter type | Team of individuals |
| Country | United States |
| Category | Fortified Enterprise Fleet |
| Organization name | N/A |
| Start date | 08/15/2026 (valid; period is Aug 3–31) |
| Code repo | `https://github.com/s6pa1rta3n-lab/universal_bounty_fleet` |
| README testing? | **Yes** |
| Hosted project URL | `https://bounty-fleet-gateway-113376683730.us-central1.run.app/console` |
| Google SDK | **Google GenAI SDK** + **Antigravity SDK** (not ADK, not Genkit) |
| Google Cloud | **Cloud Run** + **Firestore** |
| Architecture diagram | Upload `docs/Universal_Bounty_Fleet_Architecture.png` |
| Google AI models | Gemini 3.7 / Pro (3.5 or newer). Do not list 2.5. Do not list Veo/Lyria/Gemma unless wired. |

Do not list `bounty_operations` or `universal_bounty_v2` as equal repos.

### Optional testing instructions (judges-only box)

```
Judge path (5 minutes, no GCP login):

1. Clone https://github.com/s6pa1rta3n-lab/universal_bounty_fleet
2. python3 -m venv .venv && source .venv/bin/activate
3. pip install -r requirements.txt
4. export APP_ENV=test USE_IN_MEMORY_FIRESTORE=true GCP_PROJECT=odin-500008
5. pytest tests/ -q
6. uvicorn app.main:app --host 127.0.0.1 --port 8080
7. Open http://127.0.0.1:8080/console

Live camera:
https://bounty-fleet-gateway-113376683730.us-central1.run.app/console

GCP: odin-500008 / us-central1 / bounty-fleet-gateway / Firestore bounty_memory
Models: Gemini 3.7 Pro on Vertex (Antigravity sidecars use 3.7 or Pro)
```

## Demo video shot list (4 min, one take)

English voiceover. Public YouTube or Vimeo. First four minutes only.

1. Open `/console` — banner **BLOCKED**. Say: fail-closed fleet, not a chatbot.
2. GitHub issue — Intake `/try` on a funded bounty.
3. Draft PR with planted `require_auth()` bypass.
4. Auditor **REQUEST_CHANGES** (Pillar 2). Console stays BLOCKED.
5. Fix the bypass. Auditor **APPROVE**. Banner **CLEARED**.
6. Five seconds: browser bar `*.run.app/console` + Cloud Console (`odin-500008`, Cloud Run, Vertex **3.7 or Pro**).
7. Cut. Do not show a batch of merges.

## Bonus write-up (publish public, not unlisted)

Paste the block in `docs/hackathon_writeup.md` to dev.to or Medium. Include the required sentence. Then paste that URL into Devpost.

Social: tweet already drafted. Paste the **tweet URL** (not x.com/home) into the bonus field. Hashtag: `#AllThingsAgenticHackathon`.
