# AI CPU runner setup

This GitHub repository is public. Workflow source, commit history, job logs, reports, and build artifacts may be visible to anyone.

## Current setup
- Host: standard GitHub-hosted Windows Server 2022 Actions runner. Public repositories ordinarily have 4 logical CPUs and 16 GB RAM; verify in each job's hardware step.
- Runtime: Ollama, CPU-only. This is an ephemeral environment: each run has a 350-minute time limit. It cannot host a truly permanent 24/7 service.
- Android access: through Tailscale only, not a public Ollama endpoint.
- Original Android Ollama model: edit [selected-model.txt](selected-model.txt). Hermes Agent models: edit [hermes-models.txt](hermes-models.txt) (the first uncommented line is the default; additional lines are also downloaded, up to four). Changes take effect on the next manual run. Never put credentials in tracked files.
- API: http://<this-run-Tailscale-IP>:11434 (available only inside the Tailnet). Ollama model alias: local-coder.

## Start Android AI
1. Ensure the repository Actions secret TAILSCALE_AUTHKEY exists. Never paste the key into workflow source or issues.
2. Open Actions > Android Ollama over Tailscale > Run workflow.
3. Wait until Install and authenticate Tailscale and Install Ollama in shared directory finish successfully. The server is available only after Ollama installation and model load.
4. Open the Tailscale app on Android with an account authorized for the same tailnet.
5. In the Tailscale admin/devices dashboard, locate the device named ollama-<GitHub-run-ID> and its 100.x.x.x address. The address is masked in public Actions logs.
6. Use http://<100.x.x.x>:11434 as the Ollama base URL in your Android app. Choose local-coder once the workflow loads the model.

## Optional Hermes Agent (experimental)

Hermes is a separate tool-using agent, not merely another Ollama model alias. Your original Ollama Android chat server stays available as-is. Its default model is selected from [hermes-models.txt](hermes-models.txt), separate from your original chat setup. The default standard model is `qwen2.5-coder:1.5b`, with 8,192-token context to reduce CPU load. See [Hermes Agent Setup](HERMES_AGENT_SETUP.md) for the optional workflow, password-protected browser dashboard and Tailscale connection details.

The optional Hermes workflow caches **only clean, publicly available program files and standard model weights**, before any secrets or conversations are loaded. On a cache hit it can skip the slow Windows, Ollama and Hermes installation. The first run, or one after GitHub evicts the cache, still needs a full setup.

Hermes keeps its dashboard alive in **one long-running job step** and now **encrypts and uploads off-VM recovery checkpoints on GitHub every 10 minutes**, as well as at startup and graceful shutdown. The last eight rolling encrypted snapshots are kept in a dedicated GitHub prerelease; a completed run also uploads a separate encrypted Actions artifact (up to 90-day retention). The next Hermes run automatically restores the latest rolling checkpoint. **To shut down safely**, open [Hermes Agent workflow](.github/workflows/hermes-agent.yml), select **Run workflow**, change the **operation** dropdown from **start** to **stop**, and submit. The running job sees this request, uploads its final checkpoint and exits normally. Avoid the Cancel button, which can lose data since the last successful remote checkpoint. The public repo exposes only AES-256-GCM encrypted state; keep the dashboard password to decrypt it. See [Hermes Agent Setup](HERMES_AGENT_SETUP.md) for exact instructions and excluded file types.

## Clean Actions setup
Only two workflows remain in the current repository:

- [Android Ollama over Tailscale](.github/workflows/main.yml): manually start the existing Ollama server for the Android app; the temporary server stays active while its Actions job runs.
- [Hermes Agent over Tailscale](.github/workflows/hermes-agent.yml): manually start a separate agent dashboard with a password and encrypted state snapshots.

Old CPU/Hermes testing workflows were removed to simplify the Actions list. Their past completed run records remain in GitHub history; removing workflow YAML files does not erase past run logs or artifacts. Historical CPU benchmarks are documented in MODEL_BENCHMARK.md, CPU_TUNING.md and SELECTED_MODEL_SPEED.md.

## Security after switching visibility
- Important: Old commit history may contain a hard-coded RDP password. Treat that password as compromised; change or revoke it everywhere it may still work. Deleting it in a new commit does not erase Git history.
- Review old Actions job logs, artifacts, and commit history before sharing other sensitive information.
- Rotate Tailscale authentication keys or other credentials if they were exposed. Store secrets only using GitHub Actions Secrets and revoke unused Tailscale nodes.
- Do not expose port 11434 to the public internet. Maintain appropriate Tailscale access controls.
- Do not allow untrusted pull-request code to run in workflows with secrets.

More RAM and CPU do not guarantee any specific tokens-per-second rate. Benchmarking does not change the model selection.
