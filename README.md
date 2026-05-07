# Vulnerability Scanner POC — Google ADK Multi-Agent

A proof-of-concept multi-agent security scanner built with [Google Agent Development Kit (ADK)](https://google.github.io/adk-docs/). It orchestrates four specialized AI agents to plan, review, critique, and report on security vulnerabilities in any codebase.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  SequentialAgent: vuln_scanner               │
│                                                             │
│  ┌───────────┐    ┌─────────────────────────┐    ┌────────┐│
│  │  Planner  │───▶│  LoopAgent: review_loop  │───▶│Reporter││
│  │           │    │  (max 3 iterations)      │    │        ││
│  │ list_files│    │  ┌──────────┐ ┌───────┐  │    │ writes ││
│  │ pick top  │    │  │ Reviewer │→│ Critic │  │    │ final  ││
│  │ 10 files  │    │  │read_file │ │exit_  │  │    │ report ││
│  │           │    │  │          │ │ loop   │  │    │        ││
│  └───────────┘    │  └──────────┘ └───────┘  │    └────────┘│
│                    └─────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘

Data flow:
  Planner ──files_to_review──▶ Reviewer ──findings──▶ Critic
                                  ▲                     │
                                  │   review_feedback   │
                                  └─────────────────────┘
                                        (loop)
  Critic ──exit_loop──▶ Reporter ──final_report──▶ User
```

## Prerequisites

- Python 3.11+
- Google Cloud project with Vertex AI API enabled
- `gcloud` CLI installed and authenticated

## Setup

1. **Install the ADK**

   ```bash
   pip install google-adk
   ```

2. **Configure your project**

   Edit `vuln_scanner/.env` and replace `YOUR_PROJECT_ID` with your real GCP project ID:

   ```
   GOOGLE_GENAI_USE_VERTEXAI=TRUE
   GOOGLE_CLOUD_PROJECT=my-gcp-project-123
   GOOGLE_CLOUD_LOCATION=us-central1
   ```

3. **Authenticate**

   ```bash
   gcloud auth application-default login
   ```

## How to Run

From this directory (the parent of `vuln_scanner/`):

```bash
adk web
```

This starts the ADK web UI on `http://localhost:8000`.

## How to Demo

1. Open **http://localhost:8000** in your browser.
2. Select **vuln_scanner** from the agent dropdown in the top-left.
3. Send a prompt like:

   > Scan the codebase at /path/to/target/project for security vulnerabilities.

4. Watch the agents work through the pipeline in real time.

### Example Prompt

```
Scan the codebase at /Users/yourname/projects/my-web-app for security vulnerabilities.
Focus especially on authentication and API endpoints.
```

## What to Expect

The scanner runs through four stages:

| Stage | Agent | What It Does |
|-------|-------|--------------|
| 1 | **Planner** | Scans the target directory, identifies code files, and picks the top 10 most security-relevant files (auth, routes, DB, config). |
| 2 | **Reviewer** | Reads each prioritized file and identifies specific vulnerabilities with line numbers, severity ratings, and fix suggestions. |
| 3 | **Critic** | Evaluates the review quality. If gaps exist, it sends the reviewer back for another pass (up to 3 iterations). If thorough, it exits the loop. |
| 4 | **Reporter** | Compiles all findings into a polished markdown report with an executive summary, severity stats, detailed findings, and top action items. |

The final output is a structured vulnerability report ready to share with your team.

## Demo Talking Points for Leadership

- **Multi-agent orchestration** — Shows how specialized agents collaborate: planning, execution, quality assurance, and reporting, mirroring how a real security team operates.
- **Self-improving review loop** — The critic agent acts as a quality gate, sending work back if it's not thorough enough. This is a pattern applicable to any review workflow (code review, compliance, auditing).
- **Built on Google ADK** — Uses Google's agent framework with Gemini models on Vertex AI. Production-ready infrastructure with enterprise auth, logging, and scaling built in.
- **Extensible architecture** — Easy to add new agents (e.g., a remediation agent that generates fix PRs) or swap in different models. The pattern generalizes to any multi-step analysis workflow.
- **Practical AI value** — Security review is expensive and slow. This POC demonstrates how AI agents can accelerate the first pass, letting human reviewers focus on the highest-risk findings.
