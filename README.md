# Codex Remote on Android — local AI on a GitHub VM

This repository can start an **ephemeral Windows GitHub Actions VM** with:
- Official OpenAI **Codex CLI Remote Control** (not the desktop app)
- A **local Ollama model** selected from [agent-models.txt](agent-models.txt)
- A **private Tailscale pairing page**, so you can authorize the VM from
  your Android phone and retrieve a short-lived Codex pairing code
- A **Stop** option that safely ends the temporary VM

**[Start Codex Remote on GitHub Actions](https://github.com/TheOneWhoSpeaksJanna/github/actions/workflows/codex-remote.yml)**

**[Complete Android setup and pairing guide](CODEX_ANDROID_SETUP.md)**

## How it works

1. Open the Codex Remote Actions workflow; choose **operation=start**.
2. Once the log says **CODEX REMOTE PAIRING PORTAL ONLINE**, find
   the Tailscale machine named codex-remote-RUNID.
3. Open its private 100.x.x.x IP on port **9130** in Chrome on Android.
   Sign in as owner with your existing private dashboard password.
4. Enter the device authorization code on the official ChatGPT login site.
5. When the portal displays the manual pairing code, enter it in
   **ChatGPT Android → Codex / Remote** to pair the temporary VM.
6. Work in Codex with the VM's local model. Use operation=stop
   when finished, and save important files before the VM shuts down.

The Codes are never printed into public GitHub Actions logs. Your
ChatGPT account has to authorize the VM before pairing works.
Account authentication is not saved across VM runs.

The regular ChatGPT chat model picker is not changed; the local model
is the inference backend of the remote Codex host only. Remote is a
supported Codex CLI feature, but full end-to-end pairing and tool use
cannot be guaranteed until the owner signs in and tests it.

## Legacy experiments

Ollama Chat, Hermes Agent, and the custom Pocket File Agent dashboard
were retired after unreliable Android behavior. Their source files
are archived and their encrypted backup releases remain preserved.
The old File Agent workflow is **stop-only**, so it cannot launch a
new local model server.

This GitHub repo is public; do not commit account tokens, passwords or
personal files. The paired Windows VM is temporary, not a 24/7 computer.
