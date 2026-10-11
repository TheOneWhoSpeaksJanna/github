# AI CPU runner setup

This GitHub repository is public. Workflow source, commit history, job logs, reports, and build artifacts may be visible to anyone.

## Current setup
- Host: standard GitHub-hosted Windows Server 2022 Actions runner. Public repositories ordinarily have 4 logical CPUs and 16 GB RAM; verify in each job's hardware step.
- Runtime: Ollama, CPU-only. This is an ephemeral environment: each run has a 350-minute time limit. It cannot host a truly permanent 24/7 service.
- Android access: through Tailscale only, not a public Ollama endpoint.
- Model selection: configured in selected-model.txt; never put credentials in tracked files.
- API: http://<this-run-Tailscale-IP>:11434 (available only inside the Tailnet). Ollama model alias: local-coder.

## Start Android AI
1. Ensure the repository Actions secret TAILSCALE_AUTHKEY exists. Never paste the key into workflow source or issues.
2. Open Actions > Android Ollama over Tailscale > Run workflow.
3. Wait until Install and authenticate Tailscale and Install Ollama in shared directory finish successfully. The server is available only after Ollama installation and model load.
4. Open the Tailscale app on Android with an account authorized for the same tailnet.
5. In the Tailscale admin/devices dashboard, locate the device named ollama-<GitHub-run-ID> and its 100.x.x.x address. The address is masked in public Actions logs.
6. Use http://<100.x.x.x>:11434 as the Ollama base URL in your Android app. Choose local-coder once the workflow loads the model.

## Optional Hermes Agent (experimental)

Hermes is a separate tool-using agent, not merely another Ollama model alias. Your original Ollama Android chat server stays available as-is. See [Hermes Agent Setup](HERMES_AGENT_SETUP.md) for the optional workflow, private password-protected browser dashboard, and Tailscale connection details. It requires the additional HERMES_DASHBOARD_PASSWORD Actions secret and runs a standard tool-capable model in a separate GitHub job. Its compatibility test is tracked under the Actions tab.

## Benchmarks
Open Actions > Public 4-vCPU Model Speed Test > Run workflow. It compares official Qwen2.5 Coder 1.5B and 3B across auto/1/2/4 CPU thread configurations. The Actions run has a summary and a downloadable public-runner-cpu-results artifact. Actual performance varies among runners.

## Security after switching visibility
- Important: Old commit history may contain a hard-coded RDP password. Treat that password as compromised; change or revoke it everywhere it may still work. Deleting it in a new commit does not erase Git history.
- Review old Actions job logs, artifacts, and commit history before sharing other sensitive information.
- Rotate Tailscale authentication keys or other credentials if they were exposed. Store secrets only using GitHub Actions Secrets and revoke unused Tailscale nodes.
- Do not expose port 11434 to the public internet. Maintain appropriate Tailscale access controls.
- Do not allow untrusted pull-request code to run in workflows with secrets.

More RAM and CPU do not guarantee any specific tokens-per-second rate. Benchmarking does not change the model selection.
