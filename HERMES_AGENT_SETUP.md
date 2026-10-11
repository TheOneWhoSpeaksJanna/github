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

## Running time, limitations and security

- GitHub-hosted runners are temporary. Hermes checks the running service and creates **AES-256-GCM encrypted snapshots locally approximately every 15 minutes**. On a normal end, it uploads the latest encrypted snapshot as a GitHub Actions artifact and restores that snapshot at the start of the next run. Application binaries and the Ollama model are restored from a separate clean software cache, not from the private backup.
- **Snapshots are GitHub Actions artifacts with up to 90 days retention and are readable/downloadable by others because this repository is public. Only AES-256-GCM encrypted ciphertext is uploaded**, never plaintext files. Do not use this as your only important backup. If you need long-term storage, download the encrypted artifact to a trusted private location before it expires.
- **Backup limitation:** Snapshots are uploaded only **when the workflow step finishes**, not while it is still serving requests. If GitHub abruptly kills the VM or the job is cancelled, the entire current run's changes may be lost. Earlier uploaded backups remain available. Do not rely on this setup as your only copy of important information. Changing the dashboard password makes old backups unreadable without the original password.
- The repository is public. Never commit passwords, model API tokens, or Tailscale credentials. Old Git history and Action logs can be viewed publicly, and past RDP passwords should be rotated.
- The dashboard is bound only to the runner's Tailscale address and requires a separate password, unlike a standard Ollama endpoint. Never publish a tunnel to it.
- Historical dedicated smoke-test workflows were removed to simplify the repository. The main Hermes workflow still runs an encryption self-test before loading private data. The recent two-minute runs verified dashboard startup and encrypted artifact uploads; they did not prove all agent tools work on CPU.
- Existing selected-model.txt and main.yml are not changed. If Hermes does not start or requires too many resources, your original Android chat continues to work.

Official references: [Hermes Windows installation](https://hermes-agent.nousresearch.com/docs/user-guide/windows-native), [Hermes local Ollama guide](https://hermes-agent.nousresearch.com/docs/guides/local-ollama-setup), and [Hermes dashboard authentication](https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard).
