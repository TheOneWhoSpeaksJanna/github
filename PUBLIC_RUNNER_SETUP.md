# Public runner setup (current status)

The repository is now public. GitHub Actions standard Windows runners for public repositories normally have four allocated logical processors and 16 GB of RAM, subject to verification on each job. No GPU is included.

See [README.md](README.md) for the Android Tailscale connection instructions and historical-secret safety checklist.

The workflow [Public 4-vCPU Model Speed Test](.github/workflows/public-cpu-benchmark.yml) checks the allocated hardware and compares standard coding model throughput. Reports are available in the Actions run summary and downloadable artifact.

**Security:** Old history may contain a hard-coded RDP password. Publicizing a repository exposes commit history and prior Actions logs, not only current files. Revoke or change old exposed credentials. Do not push Tailscale keys or personal access tokens into public files. Keep Ollama reachable only inside the private Tailscale network.

The public runner is temporary and does not provide a 24/7 server.
