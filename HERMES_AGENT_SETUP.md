# Hermes Agent (experimental) on GitHub Actions

Our existing Android Ollama chat remains unchanged. Hermes Agent is a **separate tool-using application**; merely installing it will not turn an Ollama-only Android client into an agent. The standalone agent workflow starts the model chosen in the editable [hermes-models.txt](hermes-models.txt) file and a password-protected Hermes dashboard.

## First-time setup

1. Open GitHub repository **Settings → Secrets and variables → Actions**.
2. Under **Repository secrets**, create a new secret called **HERMES_DASHBOARD_PASSWORD** with a long, unique **password of at least 14 characters (not 14 words)**. Prefer a password manager-generated random password of 24+ characters. **Save it in your password manager**: it also decrypts your future Hermes backups, so changing or forgetting it means old backups cannot be restored without the original. Do not paste the password in an issue, README, commit, or public Action log.
3. Confirm your existing **TAILSCALE_AUTHKEY** secret is configured. The workflow will use it privately to join the Tailnet.
4. Go to **Actions → Hermes Agent over Tailscale (Experimental) → Run workflow**. It starts a **separate** runner from your working Android Ollama server.
5. Once the installation and dashboard startup have succeeded, open the Tailscale device list on Android and locate the node named **hermes-<run ID>**. Its Tailscale address can change between runs.
6. In the Android **browser**, open **http://<that device's Tailscale IP>:9119/**. Log in with username **owner** and the GitHub Actions password secret you set. Do not open this endpoint from the public internet.

Hermes Agent has a browser dashboard, but an Ollama-only Android app still talks to the old model server on port 11434 and won't be able to invoke Hermes tools. The Hermes dashboard is the separate agent interface.

## Change Hermes Ollama models without editing code

The **only file you need to edit is [hermes-models.txt](hermes-models.txt)** (this is separate from `selected-model.txt`, which controls the original Android Ollama server). From your phone, open the file on GitHub, select the pencil icon, edit, and **Commit changes** to the `main` branch.

- Put **one Ollama model name per uncommented line**. The first model is the Hermes default; any additional model names are downloaded too, up to four total.
- Lines starting with `#` are comments and not installed.
- By default, the file chooses standard `qwen2.5-coder:1.5b` for lower CPU usage. For example, you can switch the default to `qwen3.5:2b` by making it the first uncommented line.
- Changes apply **only on the next manual Hermes workflow run**. Do not cancel a working session just to change model files; abrupt cancellation can lose the current session's local history before upload.
- A changed list gets a separate reusable cache. Already downloaded models are reused when possible; new models may require extra download time and disk/RAM. The workflow refuses more than four models to avoid unbounded downloads.
- The default Hermes/Ollama context has been reduced to **8,192 tokens** for lower CPU overhead. A small coding model might struggle with complex multi-tool agent tasks; the workflow can select a model but cannot guarantee it will handle all Hermes tools reliably.

## Android keyboard support

Hermes's built-in terminal relies on xterm.js, which sometimes ignores mobile keyboard input even when text paste works. The Windows GitHub workflow now builds a small **native Android message composer** into the dashboard Chat tab. After starting a **new** Hermes run with the updated code, you should see **Type a message here...** and **Send** beneath the terminal on your phone. Type in that box and press Send. The message is forwarded via the original authenticated xterm paste/PTY connection, followed by Enter; no public API, second port, or separate password is introduced.

**Already-running Hermes VMs cannot pick up a new web build automatically**. Your current session can use copy/paste without restarting. When you next start Hermes, the cache should supply the patched mobile dashboard. A newer cache is built independently of the running session. If a new dashboard tab shows an old interface, reload the page after the new VM is running.


## What it can do

Hermes supplies real tool orchestration, such as inspecting files, working on code in a temporary workspace, and other enabled tools. Terminal command approvals are configured as **manual** and unattended dangerous commands are denied. Actions executed by an agent should still be reviewed. The model might call tools incorrectly; an ordinary 2B model will not perform as reliably as a larger model.

Hermes now reads its model from `hermes-models.txt` and uses an **8,192-token default context**. Tool schemas and larger conversations can still slow down CPU inference, even when the same model is fast in a plain Ollama chat.

## Faster startup and secure software caching

The workflow uses a **clean software-only cache** for the official Hermes runtime, Ollama program files and models listed in `hermes-models.txt`. The cache key changes when the model list changes. On a cache hit it skips the Windows Ollama installer, model download, and Hermes dependency/frontend build. The first successful cache-building run still needs the full installation. GitHub caches can be evicted or expire, making a later installation slower again.

**Important:** The cache is saved before loading Tailscale credentials, dashboard passwords, or restored user conversations. Only public application binaries and model files are stored there. Private memory and chat history are restored separately from an encrypted backup, after the software cache has been saved.

The dashboard and local Ollama backend now run inside **one continuous GitHub Actions step**, preventing step transitions from terminating the app.

Hermes starts **only when you manually run the workflow**; code commits no longer launch additional experimental servers. The Run workflow dialog defaults to a 300-minute session, and you can choose 1-310 minutes. Two short successful October 11 tests verified dashboard startup and encrypted artifact upload.

## Save automatically every 10 minutes and shut down safely

The GitHub runner cannot stay running after a workflow stops, but Hermes now **saves and uploads an AES-256-GCM encrypted backup off the VM at startup, every 10 minutes, and during graceful shutdown**. These rolling checkpoint files are placed in a dedicated [GitHub prerelease](https://github.com/TheOneWhoSpeaksJanna/github/releases/tag/hermes-encrypted-checkpoints). The latest eight checkpoints are retained. On a new run, Hermes restores the newest rolling checkpoint automatically, falling back to a completed-run Actions artifact when no rolling release exists.

**To turn Hermes off without losing the latest conversation:**

1. Open [Hermes Agent Actions](https://github.com/TheOneWhoSpeaksJanna/github/actions/workflows/hermes-agent.yml).
2. Tap **Run workflow** (this sends a separate command; it does not start a second VM when Stop is selected).
3. Under **operation**, choose **stop** rather than **start**. Leave the session length alone, and press **Run workflow**.
4. The live Hermes job checks for this Stop signal roughly every 45 seconds, uploads a **final encrypted backup**, closes Hermes and Ollama, and then lets the normal 90-day encrypted Actions artifact upload step finish.
5. Wait until the original **Hermes start** run ends normally. Once the job ends, the Windows VM is automatically removed by GitHub.

**Do not press the Cancel workflow button for an ordinary shutdown.** Cancel kills the process abruptly; the latest *remote* 10-minute checkpoint should survive, but changes since that upload may be lost. A network/upload failure may also delay a checkpoint. The running VM's local snapshots are not permanent, so verify the GitHub backup uploads succeed in the job log.

**Backup scope:** Hermes sessions, memory, configuration, skills, and user workspace files in the curated state snapshot (up to 65 MB total, with individual file limits). It **does not** back up the Windows operating system, installed binaries, Ollama model files, hidden credentials, or all temporary directories. Those programs/models are downloaded or restored from a separate clean public software cache.

**Privacy:** This repository is public, so anyone may download the release assets and completed-run artifacts. The backup files are encrypted before uploading. Use a unique, strong dashboard password and keep it saved; that same password is needed to decrypt old checkpoints.

## Running time, limitations and security

- GitHub-hosted Windows runners are temporary, so Hermes is not an always-on permanent VM. Run length is at most 310 minutes plus initialization time.
- Rolling encrypted checkpoints are uploaded at startup and every 10 minutes, plus final graceful shutdown. This uses a separate GitHub prerelease so files exist outside the VM **during** the run. The most recent eight rolling snapshots are kept.
- The normal completed-run **Actions artifact** is still uploaded after Hermes exits, with up to 90-day retention. If the job is force-cancelled, that final artifact may not upload, but prior off-VM rolling checkpoints should still exist.
- A failed network operation, disk capacity issue, or oversized user data can prevent a backup. Do not use public GitHub Actions as your only store for important files.
- You must keep the original `HERMES_DASHBOARD_PASSWORD` to restore old encrypted checkpoints. Rotating the secret makes previous backups unreadable without the old password.
- Never put GitHub tokens, passwords or Tailscale keys into repository files or Hermes prompts. Credentials are excluded from the curated snapshot, and the public repository's old commit history can be viewed.
- The Hermes dashboard is bound only to its private Tailscale IP and requires a password. Do not publish port 9119 to the internet.
- Existing `selected-model.txt` and `main.yml` for your Android Ollama setup are unchanged.

Official references: [Hermes Windows installation](https://hermes-agent.nousresearch.com/docs/user-guide/windows-native), [Hermes local Ollama guide](https://hermes-agent.nousresearch.com/docs/guides/local-ollama-setup), and [Hermes dashboard authentication](https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard).
