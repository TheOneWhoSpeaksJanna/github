#!/usr/bin/env python3
"""Measure actual Ollama model generation throughput and latency on GitHub Actions Windows CPU."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import time
import urllib.request

OLLAMA = r"C:\Ollama\ollama.exe"
API = "http://127.0.0.1:11434"
REFERENCE = "qwen2.5-coder:1.5b"
PROMPTS = [
    ("chat", "In three short sentences explain what GitHub Actions is and when a developer would use it."),
    ("python", "Write only Python code for a function named merge_sorted(a, b) that merges two ascending sorted lists without calling sorted()."),
]
REPEATS = 2

def api(path, data=None, timeout=160):
    payload = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(
        API + path, data=payload,
        headers={"Content-Type": "application/json"} if payload else {}
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)

def ready():
    try:
        api("/api/tags", timeout=3)
        return True
    except Exception:
        return False

def server_start():
    if ready():
        print("Reusing existing Ollama server.", flush=True)
        return None
    env = os.environ.copy()
    env["OLLAMA_HOST"] = "127.0.0.1:11434"
    env["NO_PROXY"] = "127.0.0.1,localhost"
    with open("ollama-selected-benchmark.log", "wb") as log:
        proc = subprocess.Popen([OLLAMA, "serve"], env=env,
                                stdout=log, stderr=subprocess.STDOUT)
    for _ in range(90):
        if ready():
            print("Ollama API ready.", flush=True)
            return proc
        if proc.poll() is not None:
            error = Path("ollama-selected-benchmark.log").read_text(
                encoding="utf8", errors="replace")
            raise RuntimeError(f"Ollama exited {proc.returncode}: {error[-1300:]}")
        time.sleep(1)
    proc.terminate()
    raise RuntimeError("Ollama did not become ready")

def run_once(model, prompt, threads, limit=160):
    options = {"num_ctx": 2048, "num_predict": limit,
               "temperature": 0, "num_gpu": 0}
    if threads is not None:
        options["num_thread"] = threads
    start = time.perf_counter()
    result = api("/api/generate", {
        "model": model, "prompt": prompt, "stream": False, "think": False,
        "keep_alive": "10m", "options": options
    }, timeout=180)
    wall = time.perf_counter() - start
    count = int(result.get("eval_count") or 0)
    generation = float(result.get("eval_duration") or 0) / 1e9
    if not count or generation <= 0:
        raise ValueError("Ollama omitted generation timing counters")
    return {"tokens_per_sec": round(count / generation, 2),
            "total_seconds": round(wall, 2),
            "tokens": count,
            "load_seconds": round(float(result.get("load_duration") or 0)/1e9, 2)}

def main():
    selected = Path("selected-model.txt").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.:/-]+", selected):
        raise RuntimeError("selected-model.txt has no valid Ollama model name")
    models = list(dict.fromkeys([selected, REFERENCE]))
    cores = os.cpu_count() or 2
    configurations = [None] + [n for n in (1,2) if n <= cores]
    results = []
    issues = []
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    service = None
    try:
        service = server_start()
        for model in models:
            print("Pulling exact model:", model, flush=True)
            try:
                subprocess.run([OLLAMA, "pull", model], check=True, timeout=650)
            except Exception as error:
                issues.append(f"Model pull failed for {model}: {error}")
                continue
            for threads in configurations:
                group = []
                status = "OK"
                try:
                    run_once(model, "Reply OK.", threads, limit=12)
                    for label, prompt in PROMPTS:
                        for repetition in range(REPEATS):
                            measurement = run_once(model, prompt, threads)
                            measurement.update(task=label, repetition=repetition+1)
                            group.append(measurement)
                except Exception as error:
                    status = "FAILED: " + str(error)[:160]
                    issues.append(f"{model}, threads={threads}: {error}")
                if group:
                    tps = round(statistics.median(m["tokens_per_sec"] for m in group),2)
                    latency = round(statistics.median(m["total_seconds"] for m in group),2)
                else:
                    tps = latency = 0
                row = {"model":model,"threads":threads,
                       "generation_tps_median":tps,"response_seconds_median":latency,
                       "samples":len(group),"status":status,"measurements":group}
                results.append(row)
                print("RESULT:",json.dumps({k:v for k,v in row.items() if k!="measurements"}),flush=True)
    finally:
        if service is not None:
            service.terminate()
            try:
                service.wait(timeout=10)
            except subprocess.TimeoutExpired:
                service.kill()

    def best(model):
        rows = [r for r in results if r["model"]==model and
                r["status"]=="OK" and r["samples"]==len(PROMPTS)*REPEATS]
        return max(rows,key=lambda r:r["generation_tps_median"]) if rows else None
    exact = best(selected)
    baseline = best(REFERENCE)
    lines = [
        "# Exact selected Ollama model speed benchmark", "",
        f"Run started (UTC): {started}",
        f"Model selected in selected-model.txt: \x60{selected}\x60",
        f"CPU logical processors allocated: **{cores}**",
        "Measured on this specific GitHub Windows-hosted runner, not the Android client.",
        "Includes warm-up per configuration; tokens/sec is Ollama's measured generation throughput and excludes prompt processing and load time.",
        "Median response time includes end-to-end request latency. Model output lengths may differ.", "",
        "| Model | Threads | Generation tokens/sec (median) | Response seconds (median) | Samples | Status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for r in results:
        label = "auto" if r["threads"] is None else str(r["threads"])
        lines.append(f"| \x60{r['model']}\x60 | {label} | {r['generation_tps_median']} | {r['response_seconds_median']} | {r['samples']} | {r['status'].replace('|','/')} |")
    lines += ["", "## Conclusion", ""]
    if exact:
        lines.append(f"**Selected model's best measured generation speed: {exact['generation_tps_median']} tokens/sec**, CPU threads={exact['threads'] if exact['threads'] is not None else 'auto'}.")
    else:
        lines.append("Selected model could not be measured successfully.")
    if baseline:
        lines.append(f"Standard 1.5B reference speed on this same runner: {baseline['generation_tps_median']} tokens/sec.")
    if exact and baseline:
        lines.append(f"Selected/reference speed ratio: {exact['generation_tps_median']/baseline['generation_tps_median']:.2f}x.")
    lines += ["", "These are measured CPU benchmarks, not guaranteed Android latency or ChatGPT-class speeds. No model selection or GitHub workflow configuration was changed."]
    if issues:
        lines += ["", "## Errors"]
        lines += ["- "+issue for issue in issues]
    Path("SELECTED_MODEL_SPEED.md").write_text("\n".join(lines)+"\n",encoding="utf8")
    Path("SELECTED_MODEL_SPEED.json").write_text(json.dumps({
        "date":started, "selected_model":selected, "baseline":REFERENCE,
        "logical_processors":cores, "best_selected":exact,
        "best_reference":baseline, "results":results, "errors":issues,
    },indent=2)+"\n",encoding="utf8")
    if not exact:
        raise RuntimeError("No valid measurements for selected model; see report")
    print(f"MEASURED EXACT MODEL: {exact['generation_tps_median']} tokens/sec",flush=True)

if __name__=="__main__":
    main()
