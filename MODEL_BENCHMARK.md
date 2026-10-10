# CPU coding model benchmark

**Status: Not run yet.** No measured results are available.

Run [Benchmark 20 coding models](https://github.com/TheOneWhoSpeaksJanna/github/actions/workflows/benchmark.yml) from the Actions tab. The benchmark writes a 20-model comparison table here, including failures and skipped models. A winner is selected only when it passes at least two of three coding checks and reaches 8 generation tokens/sec.

Current baseline: `qwen2.5-coder:1.5b`. To manually change the live model for the next VM run, edit [selected-model.txt](selected-model.txt) to any installed Ollama model tag. These benchmarks are CPU-only and the scoring uses syntax and simple heuristics, not comprehensive app-development correctness.

**Limitations:** A 175-minute hosted job may not finish all 20 downloads, and a model meeting ChatGPT-level latency cannot be guaranteed on an 8 GB CPU-only VM.
