# Hermes Agent local model performance and PC diagnostics

This is the reproducible performance guide for the Windows GitHub Actions
Hermes installation. It does not modify the original Android Ollama workflow.

## Diagnosis

On the GitHub-hosted Windows Server 2022 runner (4 logical CPU cores, ~16 GB RAM),
Hermes was much slower than plain Ollama, despite using the same local model.

| Synthetic test | Elapsed | Outcome |
| --- | ---: | --- |
| Direct Ollama chat, 2,048 context | 1.95 seconds | Success |
| Direct Ollama chat, 65,536 context | 2.62 seconds | Success |
| Hermes with only file tools | 29.62 seconds | Success |
| Hermes with full default tools | Over 90 seconds | Timeout |
| Earlier full-tool Hermes test | Over 240 seconds | Timeout |

Hermes includes system instructions, tool schemas, skills and session history
in addition to the message text. A single-word question is not a small input
when the full tool bundle is enabled. CPU reached 100% in the agent benchmark;
more than 10 GB of physical RAM remained available, making CPU prompt processing
the primary observed bottleneck rather than low memory.

Hermes requires a context configuration of at least 64,000 tokens for agent
tools. Ollama context, Hermes model.context_length and Hermes model.ollama_num_ctx
are set to 65,536. This is a configured allocation; a model with a smaller native
window does not necessarily handle that amount accurately. Larger allocated
context can increase memory use and processing time.

## Start profiles: choose at workflow launch

Go to Actions > Hermes Agent over Tailscale > Run workflow.

- **light (default):** only the file toolset, with four file operations.
  Measured around 30 seconds for a very small Hermes question; suitable for
  basic file work but not guaranteed instant.
- **chat:** no agent tools at all. Optimized for simple text conversations.
  Cannot access files or run browser/terminal tools; use light or full for actions.
- **full:** all standard Hermes CLI tools, with substantial prompt overhead.
  The small CPU-hosted model has timed out repeatedly in this mode.

The tool profile is distinct from hermes-models.txt, which still controls the
selected Ollama model. Toolset selection is restored according to the launch
profile whenever a new Hermes session starts; never abruptly cancel to switch.
Use operation=stop, then start again with the chosen agent_mode.

## A reproducible, credential-free PC diagnostic workflow

Go to Actions > Hermes performance and PC diagnostics > Run workflow.
The job runs on a *separate* GitHub Windows VM and has no access to the
dashboard password, Tailscale secret or encrypted user history.

It:
1. Reports Windows CPU count, available RAM, drive capacity, and process RAM.
2. Restores cached clean binaries and the selected public Ollama model.
3. Calls Ollama at 2K and 65K context, reporting prompt tokens/sec and
   generated tokens/sec using Ollama's own API timing fields.
4. Runs Hermes with file tools, full tools, and zero-tool chat, measuring
   elapsed time, timeout status, peak CPU load and available physical RAM.
5. Reads the loaded context from the local Ollama process API.
6. Uploads only a safe benchmark.json metric report (14-day retention).

The benchmark is deliberately synthetic: it asks for only a short OK answer.
It never copies user messages, agent responses, access tokens, private files
or saved sessions to the public GitHub Actions logs or artifacts. Actual model
stdout/stderr are not uploaded.

Read the benchmark workflow's job logs for the summary. Download the artifact
named hermes-cpu-diagnostics-<run ID> from the run's Artifacts section to
inspect structured performance metrics.

## PC and backend monitoring during a real Hermes session

While your private Hermes dashboard is running over Tailscale:
- The GitHub step "Run authenticated Hermes dashboard and encrypted backups"
  logs HERMES PC HEALTH every two minutes: free RAM, worker memory, whether
  Ollama responds and the model's loaded context. No chat contents are logged.
- On a normal stop, a separate hermes-pc-health-<run ID> artifact contains
  health samples in JSONL format (14-day retention).
- Use the password-protected Hermes dashboard's **Logs** page to review its
  private error messages. Do not publish those logs without removing secrets
  and personal or conversation content.
- The 10-minute AES-256-GCM encrypted checkpoints are separate from these
  privacy-safe health and performance records.

## Troubleshooting from results

| Result | Explanation or next check |
| --- | --- |
| Direct Ollama fast, full Hermes slow | Too many tools / prompt processing |
| Both direct and Hermes slow | CPU inference speed, model size, runtime |
| CPU saturated, RAM free | CPU-bound, not memory starvation |
| Free RAM near zero | Possible swapping; use smaller model/profile |
| Loaded context below 64K in tool mode | Hermes context requirement error |
| File profile answers, full times out | Full agent tool/prompt overhead |
| Chat works, tool modes fail | Model may not reliably call tools |

Model correctness and reliable agent tool use cannot be guaranteed by one
successful short test. Avoid making Hermes publicly accessible; preserve its
Tailscale-only binding and password authentication.

## Primary technical references

- Nous Research [Local Ollama setup](https://hermes-agent.nousresearch.com/docs/guides/local-ollama-setup)
- Nous Research [Toolsets reference](https://hermes-agent.nousresearch.com/docs/reference/toolsets-reference)
- Nous Research [Hermes configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration/)
- Ollama [Context length and inference memory](https://docs.ollama.com/context-length)
