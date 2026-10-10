# CPU-only model benchmark
Run: 2026-10-10T13:41:50.672969+00:00

Tests: 3 short coding tasks. Generated code was **not executed**; scores are conservative syntax/heuristic checks, not proof of correctness.

Speed measured on this particular GitHub Actions runner. Results are not comparable to ChatGPT cloud latency.

| Model | Status | Generation tokens/s | Avg response seconds | Coding checks /3 |
|---|---|---:|---:|---:|
| `qwen2.5-coder:0.5b` | tested | 27.98 | 4.99 | 2 |
| `qwen2.5-coder:1.5b` | tested | 17.77 | 4.22 | 3 |
| `qwen2.5-coder:3b` | tested | 9.1 | 10.78 | 3 |
| `qwen2.5-coder:0.5b-instruct-q4_K_S` | tested | 28.58 | 4.15 | 2 |
| `qwen2.5-coder:0.5b-instruct-q5_1` | tested | 24.67 | 4.45 | 2 |
| `qwen3:0.6b` | tested | 35.65 | 2.96 | 2 |
| `qwen3:1.7b` | tested | 14.45 | 8.3 | 3 |
| `qwen3:4b` | tested | 6.35 | 30.53 | 1 |
| `qwen2.5:0.5b` | tested | 27.6 | 4.39 | 2 |
| `qwen2.5:1.5b` | tested | 16.68 | 5.71 | 3 |
| `qwen2.5:3b` | tested | 8.89 | 11.16 | 3 |
| `gemma3:1b` | tested | 15.02 | 4.51 | 2 |
| `gemma3:4b` | tested | 6.95 | 12.07 | 3 |
| `llama3.2:1b` | tested | 15.48 | 6.99 | 3 |
| `llama3.2:3b` | tested | 8.59 | 7.06 | 3 |
| `smollm2:360m` | tested | 34.11 | 1.68 | 3 |
| `smollm2:1.7b` | tested | 10.52 | 6.55 | 3 |
| `deepseek-coder:1.3b` | tested | 19.11 | 9.13 | 3 |
| `starcoder2:3b` | tested | 8.74 | 13.11 | 0 |
| `codegemma:2b` | failed: HTTP Error 500: Internal Server Error | 0 | 0 | 0 |

**Winner:** smollm2:360m

Selection criteria: at least 2/3 checks and 8 generation tokens/s; among qualifying models prioritize coding checks, then generation speed.

Some models may fail to download or exceed time limits; these are marked rather than silently excluded.
