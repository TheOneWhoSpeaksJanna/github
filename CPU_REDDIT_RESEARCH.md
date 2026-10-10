# Reddit-only research: CPU inference speed

Reviewed October 10, 2026. **32 Reddit discussions** were screened; not every thread uses CPU-only hardware, and third-party performance claims are not results from our GitHub VM.

## Conclusions for an 8 GB, CPU-only GitHub runner

- **Tune threads, don't assume more is better.** Examples range from 3 threads outperforming 18, to 8 outperforming 32, with a newer test showing an 80% speed change on different hardware. Check the *actual* CPU allocation in the VM.
- **Memory bandwidth is often limiting** in single-user token generation. Quantized small models, short context, and avoiding RAM swapping matter much more than a virtual CPU's advertised 96-core hostname.
- **Q4_K_M is a sound baseline.** Lower precision might gain throughput but risks output quality; reported Q2_0 x86 speedups apply to special kernels and quantizations, not to existing Qwen2.5 Coder Q4 weights.
- **Ollama vs llama.cpp differences are hardware and build dependent.** Reports of 1.8x or higher came from GPU tests; CPU improvement cannot be assumed.
- **Flash Attention and quantized KV cache** may improve memory/prefill on long-context or GPU setups. They are not proven to accelerate a 2K-token CPU chat.
- **Ollama thread controls vary across versions.** A post says `num_thread` was removed from Modelfiles; a newer post mentions `LLAMA_ARG_THREADS` under full GPU offload. Any override must be tested rather than presumed active.
- **The 3B switch is conditional.** The previous benchmark measured 1.5B at 17.77 tokens/s and 3B at 9.10 tokens/s. The new CPU-tuning workflow will only promote 3B if it achieves at least 12 tokens/s, at least 70% of the tuned 1.5B throughput, and at least as many basic coding syntax checks.

## Reddit discussions reviewed

1. [CPU-only LLM performance and t/s](https://www.reddit.com/r/LocalLLaMA/comments/1p90zzi/) — firsthand CPU model speed tables.
2. [Extensive CPU benchmark, cache and RAM](https://www.reddit.com/r/LocalLLaMA/comments/14ilo0t/) — CPU threads, bandwidth, quantization.
3. [llama.cpp vs Ollama coding throughput](https://www.reddit.com/r/LocalLLaMA/comments/1q64f26/) — GPU benchmark, not directly transferable.
4. [llama.cpp 1.8x faster than Ollama](https://www.reddit.com/r/LocalLLaMA/comments/1d05x6v/) — GPU comparison and build effects.
5. [LLAMA_ARG_THREADS with full GPU offload](https://www.reddit.com/r/ollama/comments/1vw65qx/) — thread control observation; not a CPU-only proof.
6. [CPU-only hardware comparisons](https://www.reddit.com/r/LocalLLaMA/comments/1nj4axf/) — memory channels and llama.cpp forks.
7. [Optimizing Ollama CPU only](https://www.reddit.com/r/LocalLLaMA/comments/1csgnbh/) — general CPU optimization discussion.
8. [Threads or cores for Ollama?](https://www.reddit.com/r/ollama/comments/1r7k0mp/) — community bandwidth discussion.
9. [KV-cache precision and quality](https://www.reddit.com/r/LocalLLaMA/comments/1t1t4nw/) — tradeoffs, mainly GPU.
10. [Quantizing KV cache to 2-bit](https://www.reddit.com/r/LocalLLaMA/comments/1ap3bkt/) — memory tradeoffs, not simple speed fix.
11. [Attention layers and KV-cache footprint](https://www.reddit.com/r/LocalLLaMA/comments/1jml2w8/) — architecture matters for context memory.
12. [PSA: test thread count, +80% claim](https://www.reddit.com/r/LocalLLaMA/comments/1u3fo2x/) — hardware-specific tuning.
13. [llama.cpp thread count revisited](https://www.reddit.com/r/LocalLLaMA/comments/14jk108/) — experiments sometimes favor all cores.
14. [llama.cpp CPU optimizing](https://www.reddit.com/r/LocalLLaMA/comments/190v426/) — 8 threads beat 32 on one machine.
15. [Improving CPU-only inference](https://www.reddit.com/r/LocalLLaMA/comments/1sv5jfk/) — large-model throughput bottlenecks.
16. [Increase Ollama CPU-only speed](https://www.reddit.com/r/LocalLLaMA/comments/17ccm9b/) — some tweaks yield little improvement.
17. [CPU inference in 2026](https://www.reddit.com/r/LocalLLaMA/comments/1u1sj9d/) — quantization, context and forks.
18. [Early llama.cpp thread count optimization](https://www.reddit.com/r/LocalLLaMA/comments/14djns5/) — fewer threads can help.
19. [Qwen3 Coder Next usability](https://www.reddit.com/r/LocalLLaMA/comments/1qz5uww/) — reasoning and tool loop performance; much larger hardware.
20. [Why Qwen3 Coder is fast](https://www.reddit.com/r/LocalLLaMA/comments/1p79ziz/) — MoE versus dense comparisons.
21. [Flash Attention and prompt length](https://www.reddit.com/r/LocalLLaMA/comments/1dfvp4y/) — mixed results; mainly GPU.
22. [Flash Attention GPU fork](https://www.reddit.com/r/LocalLLaMA/comments/1nbr45v/) — GPU-specific.
23. [GLM Flash performance in llama.cpp](https://www.reddit.com/r/LocalLLaMA/comments/1qhitrj/) — varying GPU results.
24. [Case against Flash Attention](https://www.reddit.com/r/LocalLLaMA/comments/1l4xiwg/) — context memory benefits.
25. [Experimental Q2_0 x86 speedup](https://www.reddit.com/r/LocalLLaMA/comments/1vhz989/) — EPYC/AVX kernel, requires compatible quant and build.
26. [Speculative prefill](https://www.reddit.com/r/LocalLLaMA/comments/1t0vp3w/) — long-context GPU optimization.
27. [Large-context llama.cpp tuning](https://www.reddit.com/r/LocalLLaMA/comments/1w1riio/) — large GPU setup.
28. [New runtime improved Step 3.5 Flash](https://www.reddit.com/r/LocalLLaMA/comments/1ske15x/) — model/runtime-specific GPU gains.
29. [Improving local model performance](https://www.reddit.com/r/ollama/comments/1rgecxt/) — discussion of context, machine specifications.
30. [Flash Attention on Apple Silicon](https://www.reddit.com/r/LocalLLaMA/comments/1mp92nc/) — context-length performance, not x86 CPU-only.
31. [Ollama num_thread removed?](https://www.reddit.com/r/LocalLLaMA/comments/1nscj3q/) — important compatibility concern.
32. [Qwen2.5 coder community t/s setups](https://www.reddit.com/r/LocalLLaMA/comments/1gxs34g/) — comparative coding throughput.

## Experiment design

The workflow benchmarks the two standard Qwen2.5 Coder sizes with identical tasks and varied server-thread settings. It saves `CPU_TUNING.md` and `CPU_TUNING.json`, then conditionally updates `selected-model.txt` **only if the 3B model crosses measured thresholds**. This is an experiment, not a guarantee of speed improvement.
