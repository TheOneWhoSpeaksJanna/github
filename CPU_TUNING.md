# CPU tuning benchmark

Completed UTC: 2026-10-10T17:35:25.574021+00:00
Visible logical processors: **2**

Compared two standard coding models with identical short prompts and 2048-token context.
Syntax checking verifies named function definitions parse, **not that the generated code works**.
Thread control via LLAMA_ARG_THREADS is version-dependent and may be ignored.

| Model | Threads | Tokens/sec | Average seconds | Syntax checks | Status |
|---|---:|---:|---:|---:|---|
| qwen2.5-coder:1.5b | default | 0 | 0 | 0/2 | FAILED Ollama exited: 1 |
| qwen2.5-coder:3b | default | 0 | 0 | 0/2 | FAILED Ollama exited: 1 |
| qwen2.5-coder:1.5b | 1 | 0 | 0 | 0/2 | FAILED Ollama exited: 1 |
| qwen2.5-coder:3b | 1 | 0 | 0 | 0/2 | FAILED Ollama exited: 1 |
| qwen2.5-coder:1.5b | 2 | 0 | 0 | 0/2 | FAILED Ollama exited: 1 |
| qwen2.5-coder:3b | 2 | 0 | 0 | 0/2 | FAILED Ollama exited: 1 |

## Decision
1.5B failed
3B failed
**Promote to 3B: NO**

Rule: 3B must exceed 12 t/s (versus previous 9.10), reach at least 70% of optimized 1.5B throughput, and match or exceed the syntax score.
No claim of ChatGPT-equivalent speed. Benchmarks on different GitHub-hosted VMs may vary.
