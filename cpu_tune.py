#!/usr/bin/env python3
"""Compare standard Qwen2.5 Coder 1.5B vs 3B on real allocated runner CPUs. Generated code is never executed."""
import ast
import datetime as dt
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import time
import urllib.request

API = 'http://127.0.0.1:11434'
OLLAMA = r'C:\Ollama\ollama.exe'
MODELS = ('qwen2.5-coder:1.5b', 'qwen2.5-coder:3b')
PROMPTS = [
    ('clamp', 'Write only valid Python code defining clamp(value, low, high), which clips value between low and high. No markdown.'),
    ('fibonacci', 'Write only valid Python code defining fibonacci(n), returning the nth Fibonacci number (0,1,1,2,3...). No markdown.'),
]

def request(path, data=None, timeout=130):
    payload = None if data is None else json.dumps(data).encode('utf8')
    req = urllib.request.Request(API + path, data=payload,
        headers={'Content-Type':'application/json'} if payload is not None else {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)

def start_server():
    """Start once, or reuse an already-running Ollama service."""
    try:
        request("/api/tags", timeout=3)
        print("Reusing running Ollama server", flush=True)
        return None
    except Exception:
        pass
    env = os.environ.copy()
    env["OLLAMA_HOST"] = "127.0.0.1:11434"
    env["NO_PROXY"] = "127.0.0.1,localhost"
    with open("ollama-benchmark-server.log", "wb") as log:
        process = subprocess.Popen([OLLAMA, "serve"], env=env, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(75):
        try:
            request("/api/tags", timeout=2)
            print("Server started once", flush=True)
            return process
        except Exception:
            if process.poll() is not None:
                from pathlib import Path
                details = Path("ollama-benchmark-server.log").read_text(encoding="utf8", errors="replace")
                raise RuntimeError("Ollama exited: " + str(process.returncode) + ": " + details[-1200:])
            time.sleep(1)
    process.terminate()
    raise RuntimeError("Ollama server never became ready")

def stop_server(process):
    if process is None:
        return
    try:
        process.terminate()
        process.wait(timeout=10)
    except Exception:
        process.kill()
        process.wait(timeout=5)

def syntax_ok(text, name):
    fenced = re.search(r'\x60\x60\x60(?:python)?\s*(.*?)\x60\x60\x60', text, re.I | re.S)
    source = fenced.group(1) if fenced else text
    try:
        tree = ast.parse(source)
        return int(any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and node.name == name for node in tree.body))
    except SyntaxError:
        return 0

def generate(model, prompt, threads=None, limit=160):
    start = time.perf_counter()
    opts = {"num_ctx": 2048, "num_predict": limit, "temperature": 0.0, "num_gpu": 0}
    if threads is not None:
        opts["num_thread"] = threads
    response = request("/api/generate", {
        "model": model, "prompt": prompt, "stream": False, "think": False,
        "keep_alive": "10m", "options": opts
    }, timeout=150)
    elapsed = time.perf_counter() - start
    count = int(response.get("eval_count") or 0)
    duration = float(response.get("eval_duration") or 0) / 1e9
    if not count or duration <= 0:
        raise ValueError("Missing generation timing counters")
    return {"tps": count/duration, "seconds": elapsed, "text": response.get("response","")}

def main():
    logical = os.cpu_count() or 2
    threads_list = [None] + [n for n in (1,2,3,4,6,8) if n <= logical]
    rows = []
    print("Logical CPU threads available:", logical, flush=True)
    server = start_server()
    try:
        for model in MODELS:
            print("Downloading", model, flush=True)
            subprocess.run([OLLAMA, "pull", model], check=True, timeout=650)
        # All configurations use ONE Ollama server; per-request num_thread avoids
        # the Windows app restarting the server and causing "exit code 1".
        for threads in threads_list:
            for model in MODELS:
                print("Benchmarking", model, "thread setting", threads, flush=True)
                try:
                    generate(model, "Reply OK.", threads=threads, limit=8)
                    values = [generate(model,prompt,threads=threads) for _,prompt in PROMPTS]
                    accuracy = sum(syntax_ok(v["text"], name)
                                   for (name,_),v in zip(PROMPTS,values))
                    row = {"model": model, "threads": threads, "status":"OK",
                           "tps": round(statistics.median(v["tps"] for v in values),2),
                           "seconds": round(statistics.mean(v["seconds"] for v in values),2),
                           "syntax": accuracy}
                except Exception as exc:
                    row = {"model":model,"threads":threads,"status":"FAILED "+str(exc)[:130],
                           "tps":0,"seconds":0,"syntax":0}
                rows.append(row)
                print("RESULT:",json.dumps(row),flush=True)
    finally:
        stop_server(server)

    def best(model):
        valid = [r for r in rows if r["model"] == model and r["status"] == "OK" and r["syntax"] >= 1]
        return max(valid, key=lambda r: (r["syntax"],r["tps"])) if valid else None
    a,b = best(MODELS[0]),best(MODELS[1])
    promote = bool(a and b and b["tps"]>=12 and
                   b["tps"]>=0.70*a["tps"] and b["syntax"]>=a["syntax"])
    report = [
      "# CPU tuning benchmark", "",
      "Completed UTC: "+dt.datetime.now(dt.timezone.utc).isoformat(),
      "Visible logical processors: **"+str(logical)+"**", "",
      "Single Ollama server with per-request options.num_thread settings.",
      "Two code syntax checks only; generated code was not executed.",
      "Model generation tokens/sec and average full-response seconds measured.", "",
      "| Model | CPU threads | Tokens/sec | Average seconds | Syntax checks | Status |",
      "|---|---:|---:|---:|---:|---|"]
    for r in rows:
        t = "auto" if r["threads"] is None else r["threads"]
        report.append(f"| {r['model']} | {t} | {r['tps']} | {r['seconds']} | {r['syntax']}/2 | {r['status'].replace('|','/')} |")
    report += [
      "", "## Decision",
      f"Best 1.5B: {a['tps']} t/s, threads={a['threads']}" if a else "1.5B failed",
      f"Best 3B: {b['tps']} t/s, threads={b['threads']}" if b else "3B failed",
      "**Promote 3B: "+("YES" if promote else "NO")+"**",
      "Requirements: 3B >=12 tokens/s, >=70% of tuned 1.5B, equal or better syntax results.",
      "Two-vCPU GitHub runners are not expected to achieve ChatGPT-class inference speed."]
    from pathlib import Path
    Path("CPU_TUNING.md").write_text("\n".join(report)+"\n",encoding="utf8")
    Path("CPU_TUNING.json").write_text(json.dumps({
      "date":dt.datetime.now(dt.timezone.utc).isoformat(),
      "logical_processors":logical,"best_1_5b":a,"best_3b":b,
      "promote_3b":promote,"rows":rows},indent=2)+"\n",encoding="utf8")
    if promote:
        Path("selected-model.txt").write_text("qwen2.5-coder:3b\n",encoding="utf8")
    if not a or not b:
        raise RuntimeError("Benchmark incomplete: neither model size had a qualifying sample; see CPU_TUNING.md")
    print("AUTO PROMOTION:",promote,flush=True)

if __name__=="__main__":
    main()
