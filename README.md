
# ⚕️ Hermes Agent Framework

> **Autonomous, Multi-Modal AI Agent Pipeline** powered by custom model routing, persistent memory isolation, and dynamic tool orchestration.

Hermes Agent is a headless, production-ready AI agent backend integrated with GitHub Actions CI/CD workflows. Built for high-performance agentic execution, it supports dynamic model routing, real-time command execution, skill expansion, and multi-user context isolation—making it ideal for powering public web apps, developer toolkits, and autonomous workflows.

---

## 🌟 Key Features

* **⚡ Autonomous Tool & Skill Execution:** Dynamically loads specialized skills (research, DevOps, ML operations, automation) and executes terminal commands in isolated environments.
* **🧠 Persistent User Memory Isolation:** Multi-user context sandboxing under `.hermes/users/{user_id}/` ensures isolated memory, skills, and file storage for every session.
* **🔀 Smart Model Routing & Fallback:** Queries dynamic endpoint health to route requests to optimal Flash/LLM models, with automatic retry handling.
* **🌐 Web API & Public Integration:** Exposes `repository_dispatch` and `workflow_dispatch` triggers for external websites (e.g., SteveAI) to run agents and stream real-time logs.
* **📁 File Ingestion & Workspace Syncing:** Ingests user attachments (PDFs, images, code files) and automatically commits updated session artifacts back to the workspace.

---

## 📁 Repository Structure

```text
.
├── .github/
│   └── workflows/
│       ├── hermes-ask.yml      # On-demand Agent Execution API & Issue Comment trigger
│       └── hermes-master.yml   # Master Autonomous Agent DAG orchestrator
├── .hermes/
│   ├── skills/                 # Global & custom skill modules
│   │   ├── autonomous-ai-agents/
│   │   ├── devops/sdlc-review/
│   │   ├── research/
│   │   └── software-development/
│   └── users/                  # Per-user isolated memory, skills, and downloads
│       └── {user_id}/
├── workspace/                  # Working directory for agent-generated files & downloads
└── README.md                   # Project documentation
```

## 🚀 Public API & TypeScript Web Integration
Hermes Agent is designed as a headless backend for web applications. You can trigger agent runs, track status, stream execution steps, and retrieve generated files using native TypeScript/JavaScript clients.

1. Triggering an Agent Run (POST)
Trigger a workflow run from your web server or edge function using @octokit/rest or fetch:

```python
import { Octokit } from "@octokit/rest";

const octokit = new Octokit({ auth: process.env.GITHUB_PAT });

interface TriggerParams {
  question: string;
  userId: string;
  model?: string;
  fileUrl?: string;
}

export async function triggerHermesAgent({ question, userId, model = "gemini-3.1-flash-lite", fileUrl }: TriggerParams) {
  const response = await octokit.rest.repos.createDispatchEvent({
    owner: "saad-pie",
    repo: "Hermes-agent",
    event_type: "hermes_request",
    client_payload: {
      question,
      user_id: userId,
      model,
      file_url: fileUrl ?? ""
    }
  });

  return response.status === 204;
}
```

2. Live Agent Streaming & Artifact Retrieval
Stream tool usage, terminal output, and final agent answers in real-time on your frontend console component:

```js
/**
 * Polls GitHub Actions workflow artifacts and fetches the live ask_execution.log output stream.
 */
export async function streamAgentExecutionLog(runId: number, githubToken: string): Promise<string | null> {
  // 1. Get artifact metadata list
  const listRes = await fetch(`[https://api.github.com/repos/saad-pie/Hermes-agent/actions/runs/$](https://api.github.com/repos/saad-pie/Hermes-agent/actions/runs/$){runId}/artifacts`, {
    headers: { Authorization: `Bearer ${githubToken}`, Accept: "application/vnd.github.v3+json" }
  });
  const data = await listRes.json();
  const artifact = data.artifacts?.find((a: { name: string }) => a.name === "hermes-execution-log");

  if (!artifact) return null;

  // 2. Download ZIP archive
  const zipRes = await fetch(artifact.archive_download_url, {
    headers: { Authorization: `Bearer ${githubToken}` }
  });

  return await zipRes.text(); 
}
```

3. Real-Time Webhook Integration (Event-Driven)
Instead of polling, configure a GitHub Webhook on your repo pointing to your website API endpoint (e.g., /api/webhooks/hermes).

Handle workflow events in your Next.js / Express API route:

```js
import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const event = req.headers["x-github-event"];

  if (event === "workflow_run") {
    const { action, workflow_run } = req.body;

    if (action === "completed" && workflow_run.name === "Hermes Ask Agent") {
      const runId = workflow_run.id;
      const status = workflow_run.conclusion; // "success" | "failure"

      // Broadcast completion or update database record for user session
      console.log(`Hermes Run #${runId} finished with status: ${status}`);
    }
  }

  res.status(200).json({ received: true });
}
```

4. Direct Terminal Log Extraction via GitHub Jobs API
Extract execution steps line-by-line using job log endpoints:

export async function fetchJobLogs(runId: number, githubToken: string): Promise<string> {
  // Get job ID from workflow run
  const jobsRes = await fetch(`[https://api.github.com/repos/saad-pie/Hermes-agent/actions/runs/$](https://api.github.com/repos/saad-pie/Hermes-agent/actions/runs/$){runId}/jobs`, {
    headers: { Authorization: `Bearer ${githubToken}` }
  });
  const { jobs } = await jobsRes.json();
  const executeJob = jobs.find((j: { name: string }) => j.name === "hermes-ask");

  if (!executeJob) throw new Error("Job not found");

  // Fetch raw log stream
  const logRes = await fetch(`[https://api.github.com/repos/saad-pie/Hermes-agent/actions/jobs/$](https://api.github.com/repos/saad-pie/Hermes-agent/actions/jobs/$){executeJob.id}/logs`, {
    headers: { Authorization: `Bearer ${githubToken}` }
  });

  const rawLogs = await logRes.text();

  // Clean GitHub Runner timestamp prefixes
  return rawLogs.replace(/^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]+Z /gm, "");
}
🛠️ CLI Usage (GitHub Comments)
Trigger the agent directly on pull requests or issues by commenting with /ask:

/ask --model gemini-3.1-flash-lite Perform code review on the latest commit and check for security vulnerabilities.
⚙️ CI/CD & GitHub Actions Workflows
Hermes Agent leverages two primary GitHub Actions workflows to power headless execution and automated agent DAG orchestrations:

hermes-ask.yml
Handles on-demand trigger events coming from HTTP dispatch events or issue comments.

Triggers: repository_dispatch (type: hermes_request), issue_comment (/ask).
Artifact Output: Produces hermes-execution-log containing raw terminal output and execution metadata.
hermes-master.yml
Orchestrates complex, multi-step agent autonomous execution directed by skill DAGs.

Triggers: Scheduled cron triggers or manually via workflow_dispatch.
State Management: Pulls latest state from .hermes/users/{user_id}/ and commits updated memory graphs post-run.
🔒 Security & Policy
Environment Isolation: All terminal execution runs within ephemeral Ubuntu runners.
Secret Masking: Automatic log sanitization masks GitHub PATs and API keys before output generation.
Rate Limits: Automatic endpoint probing prevents quota exhaustion during high token-density loops.
📜 License
Distributed under the MIT License. Developed by Saadpie.

