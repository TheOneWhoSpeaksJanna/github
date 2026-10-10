# Exact selected Ollama model speed benchmark

Run started (UTC): 2026-10-10T18:04:36.524067+00:00
Model selected in selected-model.txt: `dagbs/qwen2.5-coder-1.5b-instruct-abliterated`
CPU logical processors allocated: **2**
Measured on this specific GitHub Windows-hosted runner, not the Android client.
Includes warm-up per configuration; tokens/sec is Ollama's measured generation throughput and excludes prompt processing and load time.
Median response time includes end-to-end request latency. Model output lengths may differ.

| Model | Threads | Generation tokens/sec (median) | Response seconds (median) | Samples | Status |
|---|---:|---:|---:|---:|---|
| `dagbs/qwen2.5-coder-1.5b-instruct-abliterated` | auto | 16.97 | 7.22 | 4 | OK |
| `dagbs/qwen2.5-coder-1.5b-instruct-abliterated` | 1 | 12.55 | 9.62 | 4 | OK |
| `dagbs/qwen2.5-coder-1.5b-instruct-abliterated` | 2 | 16.52 | 7.37 | 4 | OK |
| `qwen2.5-coder:1.5b` | auto | 16.4 | 9.71 | 4 | OK |
| `qwen2.5-coder:1.5b` | 1 | 11.98 | 13.09 | 4 | OK |
| `qwen2.5-coder:1.5b` | 2 | 15.69 | 10.03 | 4 | OK |

## Conclusion

**Selected model's best measured generation speed: 16.97 tokens/sec**, CPU threads=auto.
Standard 1.5B reference speed on this same runner: 16.4 tokens/sec.
Selected/reference speed ratio: 1.03x.

These are measured CPU benchmarks, not guaranteed Android latency or ChatGPT-class speeds. No model selection or GitHub workflow configuration was changed.
