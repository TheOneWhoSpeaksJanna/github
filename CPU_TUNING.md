# CPU tuning benchmark

Completed UTC: 2026-10-10T17:52:24.066852+00:00
Visible logical processors: **2**

Single Ollama server with per-request options.num_thread settings.
Two code syntax checks only; generated code was not executed.
Model generation tokens/sec and average full-response seconds measured.

| Model | CPU threads | Tokens/sec | Average seconds | Syntax checks | Status |
|---|---:|---:|---:|---:|---|
| qwen2.5-coder:1.5b | 1 | 11.72 | 5.15 | 2/2 | OK |
| qwen2.5-coder:3b | 1 | 5.83 | 10.17 | 2/2 | OK |
| qwen2.5-coder:3b-instruct-q3_K_M | 1 | 0 | 0 | 0/2 | FAILED HTTP Error 500: Internal Server Error |
| qwen2.5-coder:3b-instruct-q2_K | 1 | 6.66 | 26.51 | 0/2 | OK |

## Decision
Best 1.5B: 11.72 t/s, threads=1
Best 3B: qwen2.5-coder:3b at 5.83 t/s, threads=1
**Promote 3B: NO**
Requirements: 3B >=12 tokens/s, >=70% of tuned 1.5B, equal or better syntax results.
Two-vCPU GitHub runners are not expected to achieve ChatGPT-class inference speed.
