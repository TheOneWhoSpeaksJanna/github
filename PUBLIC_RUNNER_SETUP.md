# Safe public-runner test (4 vCPUs)

**Do not make this existing repository public.** It previously included a hardcoded RDP password in version history, and previous Actions logs may disclose access credentials. GitHub exposes history and Actions logs when a repository becomes public.

## Set up a new clean public repository

1. Use GitHub **New repository** to create an **empty public repository** such as `public-cpu-ai-benchmark`. Do not fork or import the existing private repository; doing so could carry history.
2. In the new repository, create `.github/workflows/public-cpu-benchmark.yml`.
3. Copy the contents of [the prepared workflow](.github/workflows/public-cpu-benchmark.yml) into that file.
4. Commit it. Open **Actions** > **Public 4-vCPU Model Speed Test** > **Run workflow**.
5. Inspect the job's **Show actual runner hardware** and **Install and benchmark CPU coding models** steps and download the `public-runner-cpu-results` artifact.

The prepared workflow uses **no secrets**, no Tailscale, and no RDP; it benchmarks two standard coding models with short prompts. GitHub's public Windows standard runner is documented as 4 vCPUs and 16 GB RAM, but measure the actual resources shown in your run.

Results do **not** automatically change the model in the original private repository. If the public benchmark is better, separately plan a secure serving arrangement instead of reusing a short-lived Actions job as a permanent remote server.
