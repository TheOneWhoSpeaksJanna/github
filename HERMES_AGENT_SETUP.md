# Hermes Agent (experimental) on GitHub Actions

Our existing Android Ollama chat remains unchanged. Hermes Agent is a **separate tool-using application**; merely installing it will not turn an Ollama-only Android client into an agent. The standalone agent workflow runs a standard tool-capable Qwen3.5 2B model and a password-protected Hermes dashboard.

## First-time setup

1. Open GitHub repository **Settings → Secrets and variables → Actions**.
2. Under **Repository secrets**, create a new secret called **HERMES_DASHBOARD_PASSWORD** with a long, unique password (at least 14 characters). Do not paste the password in an issue, README, commit, or public Action log.
3. Confirm your existing **TAILSCALE_AUTHKEY** secret is configured. The workflow will use it privately to join the Tailnet.
4. Go to **Actions → Hermes Agent over Tailscale (Experimental) → Run workflow**. It starts a **separate** runner from your working Android Ollama server.
5. Once the installation and dashboard startup have succeeded, open the Tailscale device list on Android and locate the node named **hermes-<run ID>**. Its Tailscale address can change between runs.
6. In the Android **browser**, open **http://<that device's Tailscale IP>:9119/**. Log in with username **owner** and the GitHub Actions password secret you set. Do not open this endpoint from the public internet.

Hermes Agent has a browser dashboard, but an Ollama-only Android app still talks to the old model server on port 11434 and won't be able to invoke Hermes tools. The Hermes dashboard is the separate agent interface.

## What it can do

Hermes supplies real tool orchestration, such as inspecting files, working on code in a temporary workspace, and other enabled tools. Terminal command approvals are configured as **manual** and unattended dangerous commands are denied. Actions executed by an agent should still be reviewed. The model might call tools incorrectly; an ordinary 2B model will not perform as reliably as a larger model.

The agent uses an **unmodified standard Qwen3.5 2B** model with **65,536-token context**. Large prompts and tool schemas can make response time much slower than the earlier 30-tokens/second chat experience. Hermes's local model requirements and context size are more demanding than Ollama chat.

## Running time, limitations and security

- GitHub hosted runners are temporary. This workflow ends after a maximum of 350 minutes. Nothing is preserved across sessions unless deliberately saved somewhere else.
- The repository is public. Never commit passwords, model API tokens, or Tailscale credentials. Old Git history and Action logs can be viewed publicly, and past RDP passwords should be rotated.
- The dashboard is bound only to the runner's Tailscale address and requires a separate password, unlike a standard Ollama endpoint. Never publish a tunnel to it.
- The compatibility test runs separately under **Actions → Hermes Agent Windows CPU Compatibility Test**. Native Windows support exists in current Hermes releases, but Windows Server 2022 with 4 vCPU has not been guaranteed or fully validated by us yet.
- Existing selected-model.txt and main.yml are not changed. If Hermes does not start or requires too many resources, your original Android chat continues to work.

Official references: [Hermes Windows installation](https://hermes-agent.nousresearch.com/docs/user-guide/windows-native), [Hermes local Ollama guide](https://hermes-agent.nousresearch.com/docs/guides/local-ollama-setup), and [Hermes dashboard authentication](https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard).
