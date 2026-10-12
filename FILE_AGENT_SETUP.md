> **RETIRED — October 12, 2026.** This guide describes an experimental local file agent that did not work reliably for the owner on Android. Its Windows server cannot be started again. The former workflow now provides **only a safe Stop request** for the existing VM. For supported options, read [Codex on Android](CODEX_ANDROID_SETUP.md). Old encrypted backups remain preserved.

# Pocket File Agent: Android + local model + real downloadable files

This replaces both the former Ollama Chat server and the Hermes dashboard
with a **small, dedicated file-creation agent**. It runs a standard local
Ollama model on a temporary GitHub Windows runner, connects your Android
browser privately over Tailscale, and performs bounded filesystem operations.

**[Start or safely stop Pocket File Agent](https://github.com/TheOneWhoSpeaksJanna/github/actions/workflows/file-agent.yml)**

## Start from Android

1. Ensure Tailscale is connected on your Android phone to the same private
   network as your GitHub runner.
2. Open the Pocket File Agent Actions link above. Select **Run workflow**,
   leave **operation=start**, set **session_minutes** to 300 or fewer,
   then press **Run workflow**.
3. In the GitHub run log, wait for **FILE AGENT STARTED**. (The model must
   first be restored or downloaded and the Windows runner must join Tailscale.)
4. Open Tailscale on Android. Find the new device named
   **file-agent-<GitHub run ID>**. Copy its private 100.x.x.x IP.
5. Open **http://100.x.x.x:9120** in Chrome using that IP.
6. Sign in as **owner** with the repository Actions secret
   **HERMES_DASHBOARD_PASSWORD**. This legacy-named secret is reused to
   avoid making you configure another password; it also encrypts new backups.

Port 9120 is the private *file agent dashboard*, not an Ollama Chat API.
Ollama itself is bound to localhost only at 127.0.0.1:11434.

## Make files, edit them, download on your phone

Instead of chatting with the model, give it a concrete task:

- "Create a Python calculator app and a README with instructions."
- "Build a mobile-friendly website with HTML, CSS and JavaScript files."
- "Make a weekly timetable in Markdown and CSV."
- "Update the selected README file with clearer instructions."

Click **Create files**. The application sends the task to Ollama as a
small, structured JSON request, validates the output, and writes real UTF-8
text files into a private workspace. The finished files appear in **My files**,
where you can tap individual filenames to **download** them to Android or
select **Download ZIP** for everything.

For revisions, check up to three existing small files before submitting a
task. The model receives only those selected file contents (up to 12 KB each),
not unrestricted access to your machine.

Supported text extensions include .md, .txt, .py, .html, .css, .js, .ts,
.json, .csv, .xml, .yml, .svg, .sql and similar text/source files.

**Current boundaries:** this is a purpose-built **file agent**, not an
unrestricted desktop assistant. It cannot execute arbitrary shell commands,
browse websites, access other filesystem directories, or email your files.
It creates downloadable workspace files and ZIP archives. This approach
is deliberately simpler, faster and less error-prone for small CPU models
than giving Hermes dozens of tools and a 64K context requirement.

## Change the local model

Edit **[agent-models.txt](agent-models.txt)** on GitHub and commit the file.
The first uncommented Ollama model name is the one the agent uses; additional
lines are downloaded too (up to four total). Restart the workflow normally to
apply a new model. The tested default is standard **qwen2.5-coder:1.5b**.
Your former safety-modified Hermes model remains only in the archived
hermes-models.txt file and is not used by the new file agent.

A Windows integration test confirmed the default standard model created a
real Markdown file and bundled it into a ZIP in **6.92 seconds** after startup.
Small models can still make mistakes; inspect generated files before using them.

## Safely stop the temporary VM

1. Open the Pocket File Agent workflow link above again.
2. Select **Run workflow**, choose **operation=stop**, and submit.
3. The running VM polls for this command approximately every 40 seconds,
   saves an encrypted final checkpoint, shuts down Ollama and the website,
   and allows the GitHub Actions job to end normally.

At startup, every **10 minutes**, and at graceful shutdown, the agent encrypts
the workspace with AES-256-GCM and uploads only ciphertext to a dedicated GitHub
prerelease. The newest eight rolling backups are retained; completed jobs
upload a separate encrypted Actions artifact (90-day maximum). The next agent
run automatically restores the most recent *file agent* backup.

**Do not use Cancel for routine shutdown.** Forced cancellation may discard
changes since the latest successful remote checkpoint. GitHub-hosted runners
are temporary, not a permanent personal computer.

Your **previous Hermes backup release is not deleted or overwritten**.
New File Agent backups use a separate tag:
[file-agent-encrypted-checkpoints](https://github.com/TheOneWhoSpeaksJanna/github/releases/tag/file-agent-encrypted-checkpoints).

**Important privacy limitations:** the GitHub repo is public. The encrypted
checkpoint assets can be downloaded by others, but encrypted content cannot
be read without the strong backup password. Keep your password private and
maintain downloaded copies of important work. No plaintext generated files,
private browser passwords or conversations are checked into Git.

## How this was tested

- Python offline tests on Windows: path traversal, Windows special filenames,
  atomic text writes, overwrite/update, file size limits, Basic authentication,
  CSRF-related same-origin check, mobile asset serving, individual file download
  and ZIP download.
- Actual local model test: Ollama JSON-schema output was validated and produced
  a real downloadable Markdown file, verified inside a ZIP.
- Windows run script: PowerShell syntax preflight checks.
- Full private HTTP dashboard + live model task tests are included in the
  separate temporary verification workflow during the migration.

Technical basis:
[Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs),
[Ollama API](https://docs.ollama.com/api),
[Hugging Face smolagents](https://huggingface.co/docs/smolagents/index).
We considered generic frameworks, but implemented a smaller *bounded file tool*
rather than a full code execution agent, because the prior full Hermes benchmark
timed out at 90-240 seconds on the same four-CPU hosted Windows runner.
