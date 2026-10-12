# GitHub coding workspace — ChatGPT/Codex on Android

The previous Android Ollama Chat, Hermes Agent and Pocket File Agent
servers are **retired**. They repeatedly failed to provide a reliable
tool-enabled experience on an ephemeral four-CPU GitHub Actions runner.
The repository is now ready for coding tasks through GitHub and Codex.

## Start here

**[Codex on Android setup and local-model options](CODEX_ANDROID_SETUP.md)**

### Recommended: Codex Cloud in ChatGPT Android

Use Codex Cloud to create and edit **real repository files**, run checks,
review diffs and create pull requests. It uses Codex cloud models, **not**
a local Ollama model. Create and publish a cloud environment with this
repository once from ChatGPT on the web or desktop; afterward, open
**Codex** on Android and select the published environment. Availability
depends on your account and workspace.

[Official Codex Cloud quickstart](https://learn.chatgpt.com/docs/cloud)

The [AGENTS.md](AGENTS.md) file gives coding agents safe project-specific
instructions. No custom server, Android Tailscale login or temporary
Windows VM is required for Codex Cloud tasks.

### To use an actual local model from Android

Local Ollama models are supported in **ChatGPT Desktop's Codex mode**,
not in the regular ChatGPT Android model picker. With a compatible,
signed-in Windows or Mac host, you can control that desktop's Codex work
from Android using **Remote**. Remote setup begins on the desktop app;
it cannot be established by merely running Codex CLI on GitHub Actions.

[Official Remote setup](https://learn.chatgpt.com/docs/remote-connections) |
[Ollama/Codex integration](https://docs.ollama.com/integrations/codex)

A hosted GitHub Actions runner is an unreliable and short-lived
replacement for a persistent interactive desktop PC. Running Codex
CLI against a small local model also cannot guarantee it will call
file/terminal tools correctly: tool-heavy Hermes tasks previously
stalled for multiple minutes on the same runner.

## Old server shutdown

The old file-agent run
[#38213702466](https://github.com/TheOneWhoSpeaksJanna/github/actions/runs/38213702466)
was still active when the migration began. **New File Agent starts are disabled**.
A [manual, stop-only workflow](.github/workflows/file-agent.yml)
remains to request its graceful encrypted checkpoint and shutdown.
Select **Run workflow** on that page; the workflow cannot start a new VM.

The GitHub connector does not expose an action to dispatch/cancel this run,
so a final user click is needed to stop the existing Windows job.
After it ends, its Windows VM terminates automatically.

## Repository contents

- [CODEX_ANDROID_SETUP.md](CODEX_ANDROID_SETUP.md): Android Codex Cloud
  and optional local-model Desktop Remote steps, with documented limits.
- [AGENTS.md](AGENTS.md): instruction file for Codex to make code changes.
- `agent/` and old `scripts/`: **archived experiments**, not a running app.
- [Historical File Agent setup](FILE_AGENT_SETUP.md) and
  [Hermes performance report](HERMES_PERFORMANCE.md): old research only.

Previous encrypted checkpoint release assets are **preserved**:
[Hermes](https://github.com/TheOneWhoSpeaksJanna/github/releases/tag/hermes-encrypted-checkpoints)
and
[File Agent](https://github.com/TheOneWhoSpeaksJanna/github/releases/tag/file-agent-encrypted-checkpoints).
They are not decrypted, deleted or reused in Codex Cloud.

## Safety and privacy

This repository is **public**. Do not commit tokens, passwords,
private files or unredacted logs. Old commits may contain compromised
credentials; revoke or rotate any leaked passwords or keys.
Do not publish local Ollama or the retired file-server endpoint.
Review code changes and tests before merging them.
