# Pocket File Agent: local model that makes downloadable files

This repository now runs a **file-creating local AI agent**, not an Ollama
chat server or Hermes dashboard. It is meant for use from **Android through
Tailscale** and runs on a temporary Windows Server 2022 GitHub Actions VM.

## Get started

1. On Android, open **[Pocket Local File Agent — Actions](https://github.com/TheOneWhoSpeaksJanna/github/actions/workflows/file-agent.yml)**.
2. Select **Run workflow**, leave **operation=start**, and choose the session
   length (default 300 minutes).
3. Wait for the run log message **FILE AGENT STARTED**.
4. Open Tailscale on Android. Find **file-agent-<run ID>** and copy its private
   **100.x.x.x** address.
5. In Android Chrome, visit **http://100.x.x.x:9120** (with that real address).
6. Sign in as **owner** with the existing GitHub Actions repository secret
   **HERMES_DASHBOARD_PASSWORD**. That password is reused for the new agent
   and for encrypted file backups.

Describe a task, such as **“Create a Python calculator and a README”**.
The agent uses a local model to produce real text/source files. Tap a file to
download it to Android, or use **Download ZIP** for all workspace files.
Select an existing file in the dashboard when asking the agent to revise it.

**[Full Android setup, downloads, encrypted backups and troubleshooting](FILE_AGENT_SETUP.md)**

## New agent vs. the retired chat systems

- The **old Ollama Chat workflow is removed**. Ollama remains installed
  internally as the local text-generation engine, but its port 11434 is
  **restricted to 127.0.0.1 on the VM**, not exposed to Android.
- The **Hermes workflow is retired**, because its large system/tool prompt
  caused 90–240-second timeouts on the four-CPU Windows runner.
- The new file agent requests a much smaller structured JSON response,
  validates paths and writes only allowed UTF-8 text/source files in its own
  workspace. It provides individual and ZIP downloads over the private
  password-protected Android dashboard.
- The tested local model is **standard qwen2.5-coder:1.5b**, configured in
  [agent-models.txt](agent-models.txt). The archived Hermes model setting is
  not used by the new agent.
- This is a **bounded file-task agent**, not a full remote computer or an
  unrestricted terminal. It does not run arbitrary model-generated commands,
  send emails, browse the open internet or edit files outside the workspace.

## Actions workflows

Only two active YAML workflows remain:

| Workflow | What it does |
| --- | --- |
| [Pocket Local File Agent](.github/workflows/file-agent.yml) | Start/stop a private Windows VM with an agent dashboard, model, downloadable workspace and 10-minute encrypted backups |
| [Pocket File Agent tests and CPU speed](.github/workflows/agent-verify.yml) | Manually verify sandbox security, actual model file creation, ZIP output and CPU hardware without accessing private secrets |

Both are **manual-only**; commits do not start long-running model servers.

## Speed and testing

Tests on the actual GitHub Windows runner completed successfully:

- [Real Ollama structured output → file → ZIP](https://github.com/TheOneWhoSpeaksJanna/github/actions/runs/38158954754):
  **6.92 seconds** for a short Markdown task after startup.
- [Full password-protected HTTP dashboard → task → Android-style download](https://github.com/TheOneWhoSpeaksJanna/github/actions/runs/38159306487):
  **6.05 seconds**, including real local-model generation and ZIP download.
- Security tests include password requirements, same-origin checks,
  blocked filesystem traversal, Windows path normalization and file size
  limits.

Times vary by prompt length and output file size. The tests used a
loopback-only Windows VM with no private secrets; they do not by themselves
verify a future Tailscale connection or every possible file-generation task.

## Save work and shut down safely

To stop, select **Run workflow > operation=stop**. The live agent receives
the control signal and saves a final encrypted backup before GitHub tears
down its temporary VM. Workspace checkpoints are AES-256-GCM encrypted and
uploaded to a dedicated release **at startup, every 10 minutes and at normal
shutdown**. The last eight rolling checkpoints are retained, and a separate
Actions backup artifact is uploaded after a normal run.

The old Hermes encrypted backup release is **kept separately**, so
switching agents doesn't delete old saved history. The original model
configuration files and legacy performance documentation also remain for
reference; those retired services do not run.

## Security and privacy

This repository is **public**. Repo files, commit history, Actions logs and
unencrypted artifacts are potentially public. New agent outputs live inside
the ephemeral runner and the private Tailscale dashboard; **only encrypted
workspace backups** are uploaded to GitHub. Keep the decryption password
private and download important outputs to your own storage.

Do not expose the web dashboard or internal Ollama port directly on the
internet. Maintain Tailscale access restrictions. Historic repository
revisions may contain exposed credentials; rotate any credentials that were
ever committed or logged. Never run untrusted pull-request code with Actions
secrets.

GitHub-hosted Windows VMs are temporary, not an always-on personal server.
Session length is limited, and Actions minutes/cache/storage quotas apply.

Documentation: [File Agent guide](FILE_AGENT_SETUP.md) |
[Archived Hermes performance findings](HERMES_PERFORMANCE.md) |
[Historical CPU tuning](CPU_TUNING.md).
