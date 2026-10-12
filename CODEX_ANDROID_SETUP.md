# Codex on Android: practical options (October 2026)

The previous Pocket File Agent and Hermes/Ollama Chat service are **retired**.
This repo is now a GitHub coding workspace for tasks through ChatGPT / Codex.

## What is supported?

| Goal | Supported? | Where work actually runs |
| --- | --- | --- |
| Use Codex with a local Ollama model | Yes | Codex CLI or ChatGPT **desktop Codex mode** |
| Choose an Ollama model in ordinary ChatGPT Android chat | **No** | Ordinary ChatGPT uses its supported models |
| Use local Codex work from ChatGPT Android | **Yes, where Remote is available** | Your signed-in, awake Windows/Mac desktop host |
| Run Codex coding tasks directly from ChatGPT Android | **Yes, where Codex Cloud is available** | Codex cloud, **not** your local model |
| Convert a GitHub Actions runner into a permanent ChatGPT Desktop Remote host | **Not supported as an unattended setup** | A temporary CI runner is not a signed-in desktop |

There is no repository code or GitHub secret that can add a custom Ollama
model to the ChatGPT Android **regular model picker**.

## Option A — Recommended for Android-only use: Codex Cloud

This does **not** run a local model, but it does the work you actually want:
change real files, run checks, review diffs, and create pull requests.

1. Open ChatGPT **on the web or desktop**, and open **Codex**. Choose
   **Work in > Cloud > Select environment > Create environment**.
   (Initial environment creation is not currently supported on mobile.)
2. Connect GitHub if needed, select **TheOneWhoSpeaksJanna/github**,
   and let Codex inspect the repository and test the setup. Review and
   **Publish** the environment.
3. On your Android ChatGPT app, open **Codex** and select the newly
   published Cloud environment. If you do not have Codex on mobile,
   update the app and check account/workspace availability.
4. Ask for a concrete task such as:
   "Make a calculator website, add the real HTML/CSS/JS files to this
   repo, run a basic test, and prepare a pull request."
5. Review changed files, request corrections, then commit or open a PR.
   Files are in the GitHub repository when the changes are published.

This repository has [AGENTS.md](AGENTS.md) so coding agents know they should
create real files and test changes while protecting secrets and backup
assets. It does **not** automatically publish or enable a Codex Cloud
environment on your account; you must authorize GitHub and publish one
through the official ChatGPT interface.

Official docs:
- [Codex Cloud overview](https://learn.chatgpt.com/docs/cloud)
- [Cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environments)
- [GitHub connection in ChatGPT](https://help.openai.com/en/articles/11145903-connecting-github-to-chatgpt)

## Option B — A real **local** model accessible from ChatGPT Android Remote

Requires a **persistent, user-controlled Windows or Mac computer** with
adequate CPU/RAM or GPU, not the temporary Actions VM.

1. Install Ollama and a compatible model on that desktop computer.
2. Install ChatGPT Desktop and sign in to the same ChatGPT account you
   use on Android. In Ollama's **Apps** section, enable ChatGPT
   (Desktop), then select compatible local models. Use **Codex mode**
   in the desktop app; Ollama models are not available in regular Chat.
3. On the desktop app, open **Settings > Connections >
   Control this Mac or PC > Set up** and authorize Remote.
4. Scan the QR code in ChatGPT on your Android device and complete pairing.
5. On Android, open **Remote**, select that desktop host, and control
   your Codex task. Keep the host awake, online and signed in.

Remote is account/workspace/rollout dependent and requires the desktop app,
not Codex CLI alone. A 64K context-capable model and more compute are
preferable for full Codex tools. On the previous 4-vCPU GitHub runner,
small-model full-agent tasks stalled, so this is **not** a promise of
interactive speed on that same hardware.

Official docs:
- [ChatGPT Remote connections](https://learn.chatgpt.com/docs/remote-connections)
- [Ollama ChatGPT Desktop integration](https://github.com/ollama/ollama/blob/main/docs/integrations/chatgpt.mdx)
- [Codex CLI with Ollama](https://docs.ollama.com/integrations/codex)

## Option C — Codex CLI + Ollama on your own PC (not Android ChatGPT)

Install a supported Ollama version and Node.js on your Windows/macOS/Linux
machine. Install Codex CLI using its official instructions, then run:

```sh
npm install -g @openai/codex
ollama launch codex
```

Or use an explicitly selected compatible locally installed model:

```sh
codex --oss -m MODEL_NAME
```

For file and tool tasks, Ollama's Codex integration recommends **64K+
context**. A model that can answer a simple question is not necessarily
capable of driving Codex's file/shell tools. Older Qwen2.5 Coder builds
have had tool-call compatibility issues, and 1.5B is not a credible
guarantee of a full interactive code agent.

Using the CLI alone does **not** connect it to ChatGPT Android Remote.
Remote pairing must begin from a supported signed-in ChatGPT desktop app.

## What was changed in the GitHub repository

- **Removed the ability to start another File Agent Windows VM.**
- Kept a single temporary [safe Stop workflow](.github/workflows/file-agent.yml)
  so a previously started run can receive its final encrypted checkpoint
  and shut down without an abrupt Cancel.
- Retired the old mobile server/test workflow. Previous Ollama/Hermes
  experimentation scripts and docs are historical, not an active service.
- Added the repository-level [AGENTS.md](AGENTS.md) instructions for
  Codex Cloud and GitHub coding tasks.
- Left encrypted backup releases and historic files alone.

### Stop the currently running old VM

The active runner at the time this setup was written is
[File agent start run #38213702466](https://github.com/TheOneWhoSpeaksJanna/github/actions/runs/38213702466).

The GitHub connector available in this chat cannot directly dispatch
the workflow's Stop input or cancel a run. To finish stopping it:

1. Open the [Stop retired File Agent VM workflow](https://github.com/TheOneWhoSpeaksJanna/github/actions/workflows/file-agent.yml).
2. Tap **Run workflow**. It now **only** sends a Stop request, not Start.
3. Return to run #38213702466 to confirm the old job ends normally.

A normal exit uploads a final AES-256-GCM encrypted backup. GitHub may
take some time to show the run as complete. Do not delete either release:

- [Previous Hermes encrypted checkpoints](https://github.com/TheOneWhoSpeaksJanna/github/releases/tag/hermes-encrypted-checkpoints)
- [Previous File Agent encrypted checkpoints](https://github.com/TheOneWhoSpeaksJanna/github/releases/tag/file-agent-encrypted-checkpoints)

If you cannot access the Stop workflow, GitHub's **Cancel workflow**
terminates the VM but can discard file changes since its latest successful
off-VM backup. Prefer the safe Stop when available.

**Privacy:** the repository is public, so don't put passwords,
private files, personal information, or signing credentials in prompts
that will become public commits, issue bodies, or Actions logs.
