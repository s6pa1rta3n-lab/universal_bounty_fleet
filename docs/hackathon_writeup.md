# How we built The Universal Bounty Fleet

I created this write-up for the purposes of entering the All Things Agentic Hackathon.

Coding agents cheat to get a green build: they mock ciphers, comment out `require_auth()`, and skip assertions. We built a Fortified Enterprise Fleet that claims funded GitHub issues, opens a draft PR, and **cannot merge until a separate auditor passes**.

The live camera is `/console` on Cloud Run — not a chatbot.

## What we shipped

Three scoped agents, no god-token:

- **Intake** qualifies the issue, verifies escrow with Gemini 3.7 Pro on Vertex, and stakes `/try`.
- **Executor** opens a draft PR as native save-state.
- **Auditor** fail-closes on three pillars (crypto integrity, authorization, assertion preservation) and files a native GitHub review. Humans still hold merge.

GitHub is the control plane. Firestore is the Memory Bank. Cloud Run (`bounty-fleet-gateway`, `odin-500008` / `us-central1`) is the gateway. We built the fleet with Antigravity and run Gemini through the Google GenAI SDK.

## Why this track

Fortified Enterprise Fleet asks for Registry, Runtime, Memory Bank, Identity, Gateway, guardrails, and observability. We mapped those onto a real bounty loop instead of a chat UI.

Repo: https://github.com/s6pa1rta3n-lab/universal_bounty_fleet

Console: https://bounty-fleet-gateway-113376683730.us-central1.run.app/console

#AllThingsAgenticHackathon
