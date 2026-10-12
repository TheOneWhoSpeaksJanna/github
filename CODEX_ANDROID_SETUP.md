# Codex Remote from Android using a GitHub Windows VM

This setup uses **Codex CLI Remote Control on a GitHub Actions VM**,
not your own computer. Codex connects to a locally running Ollama
model in that VM. The official Codex CLI now supports headless
manual pairing codes without the desktop app.

[Start the Codex Remote VM](https://github.com/TheOneWhoSpeaksJanna/github/actions/workflows/codex-remote.yml)

## 1. Start the GitHub Windows VM

1. Open the Codex Remote workflow link above and press **Run workflow**.
2. Choose **operation = start**, with the desired session length
   (the default is 300 minutes).
3. Open its active run in GitHub Actions. Look for
   **CODEX REMOTE PAIRING PORTAL ONLINE**.
4. On Android, open Tailscale and find the new machine named
   **codex-remote-RUNID**. Copy its private 100.x.x.x IP.
5. Open the address **http://100.x.x.x:9130** in Android Chrome,
   replacing the example IP with the real Tailscale IP.
6. Sign in with username **owner** and the existing GitHub Actions
   password secret **HERMES_DASHBOARD_PASSWORD**.

The portal is only reachable on the private Tailscale network. The
GitHub Actions logs do not contain your login or Remote pairing codes.

## 2. Sign in from Android

The private portal displays a one-time ChatGPT device-login code and
a link to **https://auth.openai.com/codex/device**. Follow the link,
sign into your ChatGPT account and enter the one-time code shown in
the private portal. Use the same account as in your ChatGPT Android app.

Headless Codex requires explicit ChatGPT account authorization. Device
login may need to be enabled under your ChatGPT security settings, and
your account may require MFA or other authorized verification.
No one can skip these requirements using a GitHub workflow.

Never paste your ChatGPT password or tokens into GitHub files, Actions
logs, issues or this chat.

## 3. Pair Codex Remote in the Android app

When authorization succeeds, the VM executes the official commands:

    codex remote-control start --json
    codex remote-control pair --json

The private Tailscale page displays the **short-lived manual pairing
code** returned by Codex. Open ChatGPT on Android, enter
**Codex / Remote**, choose to add a host, and enter the manual code.
Select the resulting GitHub-hosted Codex environment.

If a code expires, press **Create a fresh pairing code** in the
private page. The mobile Remote feature must be enabled for your
ChatGPT account/workspace.

The code cannot be generated for your account before you complete
the official device login. It is never published to the public
repository or public Actions job logs.

## Local Ollama model

The VM hosts Ollama privately at **127.0.0.1:11434**.
Codex points to the local model using the Ollama-compatible
Responses API at **http://127.0.0.1:11434/v1**.
The first uncommented model in [agent-models.txt](agent-models.txt)
is selected (currently standard **qwen2.5-coder:1.5b**).

The configuration gives Codex a 65,536-token context allocation,
because official Ollama Codex documentation recommends at least
64K. The selected 1.5B model is limited and can be slow or fail
complex file/terminal tool calls on the 4-CPU VM. A successful
Remote pairing would prove connectivity, not guaranteed agent speed.

ChatGPT sign-in is needed for **Remote host authorization**, while
the Codex host's configured inference provider is local Ollama.
The regular ChatGPT model picker remains separate.

## Stop and save

Use the same [Codex Remote Actions workflow](https://github.com/TheOneWhoSpeaksJanna/github/actions/workflows/codex-remote.yml)
with **operation = stop** to request a safe shutdown. Otherwise
the temporary Windows VM exits at its session deadline.

GitHub-hosted runners are temporary. The workflow deliberately
does not publish ChatGPT tokens, authentication files, pairing codes
or private project files into the public GitHub repository or Actions
artifacts. Account authentication is **not** persisted between runs.
Each new temporary VM requires another login and pairing. Save
valuable project work to your GitHub repository before the VM ends.

The older File Agent runner is separate; its stop-only workflow
can be used to terminate the old machine normally. Previous
Hermes and File Agent encrypted backup assets are preserved.

## Verification and requirements

Verified on GitHub Windows:
- The official npm Codex CLI installed and supported the Remote
  start/pair and device-code login commands.
- The private authentication page passed Windows security and
  Python/PowerShell syntax tests.
- The selected local Ollama model is available from its existing
  cached installation.

A separate private Tailscale smoke test checks the actual VM
startup, but signed-in Remote enrollment cannot be fully verified
until the owner authorizes the GitHub VM and pairs Android.

Official sources:
- [Codex CLI manual pairing](https://learn.chatgpt.com/docs/cli/reference)
- [Codex headless device login](https://learn.chatgpt.com/docs/auth)
- [Codex mobile Remote guide](https://learn.chatgpt.com/docs/remote-connections)
- [Ollama Codex integration](https://docs.ollama.com/integrations/codex)
