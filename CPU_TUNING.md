# CPU tuning benchmark

Completed UTC: 2026-10-10T17:44:52.268638+00:00
Visible logical processors: **2**

Single Ollama server with per-request options.num_thread settings.
Two code syntax checks only; generated code was not executed.
Model generation tokens/sec and average full-response seconds measured.

| Model | CPU threads | Tokens/sec | Average seconds | Syntax checks | Status |
|---|---:|---:|---:|---:|---|
| qwen2.5-coder:1.5b | auto | 21.55 | 2.86 | 2/2 | OK |
| qwen2.5-coder:3b | auto | 11.59 | 5.35 | 2/2 | OK |
| qwen2.5-coder:1.5b | 1 | 24.84 | 2.55 | 2/2 | OK |
| qwen2.5-coder:3b | 1 | 12.29 | 5.18 | 2/2 | OK |
| qwen2.5-coder:1.5b | 2 | 22.79 | 2.73 | 2/2 | OK |
| qwen2.5-coder:3b | 2 | 11.65 | 5.33 | 2/2 | OK |

## Decision
Best 1.5B: 24.84 t/s, threads=1
Best 3B: 12.29 t/s, threads=1
**Promote 3B: NO**
Requirements: 3B >=12 tokens/s, >=70% of tuned 1.5B, equal or better syntax results.
Two-vCPU GitHub runners are not expected to achieve ChatGPT-class inference speed.
