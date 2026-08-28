# Original User Request

## Initial Request — 2026-08-27T19:03:45-04:00

Build "The Universal Bounty Fleet", an automated swarm of agents for bounty hunting that bridges the Taskmaster and Fortified Enterprise Fleet hackathon tracks. The system must use Gemini 3.5 via Vertex AI, the Antigravity SDK, and deploy to Google Cloud (Cloud Run, Firestore) to demonstrate a live, production-grade GEAP architecture executing autonomous GitHub PR workflows.

Working directory: ~/teamwork_projects/universal_bounty_fleet
Integrity mode: development

## Requirements

### R1. The Intake Taskmaster
The system must monitor target bounty platforms and GitHub issues to identify eligible bounties. It must semantically verify escrow funding and automatically post a claim on valid targets.

### R2. The Victory Audit Fleet
The system must intercept newly opened Draft PRs via GitHub webhooks and execute an independent security audit. It must natively submit a GitHub PR Review (Approve or Request Changes) based on the presence of authorization checks and the absence of cryptographic mocks.

### R3. GEAP Infrastructure Deployment
The team must physically deploy the backend services to the user's Google Cloud account using the provided local credentials. The architecture must utilize Cloud Run as the event-driven execution runtime and Firestore as the cross-session Memory Bank.

### R4. Native GitHub Stigmergy
The agents must coordinate entirely through native GitHub features rather than internal logging. All state transitions and agent handoffs must be triggered by GitHub Webhooks, PR status changes, and PR comments.

### R5. Controlled Infrastructure
You must use the local `gcloud` CLI, which is already authenticated with the user's credentials, to deploy the Cloud Run services and provision Firestore. You write the deployment scripts and logic; the execution environment is the user's authenticated terminal.

## Acceptance Criteria

### Intake & Audit Verification
- [ ] A programmatic test script successfully triggers the Intake service with a mock funded issue, and the service outputs a valid GitHub API request to post a `/try` comment.
- [ ] A programmatic test script triggers the Audit webhook with a mock PR containing an authentication bypass, and the service outputs a valid GitHub PR Review requesting changes.

### Infrastructure & Deployment Verification
- [ ] A validation script using the `gcloud` CLI confirms that the Cloud Run services are successfully deployed and active in the user's GCP project.
- [ ] A validation script confirms that the Firestore database is provisioned and accessible.

### Stigmergy Verification
- [ ] The Cloud Run service correctly parses an incoming mock GitHub webhook payload and routes it to the appropriate Antigravity subagent (Intake vs. Auditor) without requiring a local database for routing.
