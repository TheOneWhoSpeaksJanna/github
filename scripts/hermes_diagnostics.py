#!/usr/bin/env python3
"""Public, credential-free Hermes/Ollama benchmark on ephemeral Windows CI.

Uses synthetic 'OK' prompts only. Records timing and system performance, not
model responses, private sessions, prompts or API credentials. Real private
user data must never enter diagnostics artifacts.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError


def get_json(url: str, timeout=5):
    with urlopen(url, timeout=timeout) as r:
        return json.load(r)


def post_json(url: str, body: dict, timeout: int):
    data = json.dumps(body).encode("utf-8")
    with urlopen(Request(url, data=data, headers={"Content-Type": "application/json"}), timeout=timeout) as r:
        return json.load(r)


def read_metrics():
    try:
        import psutil
    except ImportError:
        return {"psutil": False}
    mem = psutil.virtual_memory()
    target_names = {"ollama.exe", "llama-server.exe", "python.exe", "hermes.exe"}
    processes = []
    for p in psutil.process_iter(["name", "memory_info", "cpu_percent"]):
        try:
            if (p.info["name"] or "").lower() in target_names:
                processes.append({
                    "name": p.info["name"],
                    "ram_mb": round(p.info["memory_info"].rss / 1048576, 1),
                    "cpu_percent": p.info["cpu_percent"],
                })
        except (psutil.AccessDenied, psutil.NoSuchProcess, TypeError):
            pass
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.2),
        "cpu_logical_count": psutil.cpu_count(),
        "ram_total_gb": round(mem.total / 1073741824, 2),
        "ram_available_gb": round(mem.available / 1073741824, 2),
        "processes": processes,
    }


def direct_test(model: str, context: int, timeout: int, base_url: str):
    before = read_metrics()
    started = time.perf_counter()
    try:
        body = post_json(
            base_url + "/api/chat",
            {
                "model": model, "stream": False,
                "messages": [{"role": "user", "content": "Respond with OK only."}],
                "options": {"num_ctx": context, "num_predict": 16, "temperature": 0},
                "keep_alive": "30m",
            }, timeout,
        )
        elapsed = round(time.perf_counter() - started, 2)
        prompt_tokens = body.get("prompt_eval_count", 0) or 0
        output_tokens = body.get("eval_count", 0) or 0
        prompt_s = body.get("prompt_eval_duration", 0) / 1e9
        generation_s = body.get("eval_duration", 0) / 1e9
        return {
            "status": "ok" if body.get("message", {}).get("content") else "empty",
            "elapsed_seconds": elapsed,
            "context": context,
            "prompt_tokens": prompt_tokens,
            "output_tokens": output_tokens,
            "prefill_tokens_per_sec": round(prompt_tokens / prompt_s, 2) if prompt_s else None,
            "generation_tokens_per_sec": round(output_tokens / generation_s, 2) if generation_s else None,
            "load_seconds": round((body.get("load_duration", 0) or 0)/1e9, 2),
            "memory_before": before,
            "memory_after": read_metrics(),
        }
    except Exception as e:
        return {"status": "failure", "elapsed_seconds": round(time.perf_counter()-started, 2),
                "context": context, "error_type": type(e).__name__}


def hermes_test(exe: Path, toolsets: str | None, seconds: int, env: dict, outdir: Path, label: str | None = None):
    variant = label or ("default" if toolsets is None else toolsets.replace(",", "_"))
    cmd = [str(exe), "--oneshot", "Respond with OK only. Do not use any tools."]
    if toolsets is not None:
        cmd += ["--toolsets", toolsets]
    proc_start = time.perf_counter()
    outpath = outdir / ("hermes-" + variant + ".stdout.txt")
    errpath = outdir / ("hermes-" + variant + ".stderr.txt")
    # DO NOT upload stdout/stderr. They can include unsafe model content.
    samples = []
    try:
        with outpath.open("w", encoding="utf-8") as stdout, errpath.open("w", encoding="utf-8") as stderr:
            proc = subprocess.Popen(cmd, cwd=str(outdir), env=env, stdout=stdout, stderr=stderr,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            while proc.poll() is None and time.perf_counter() - proc_start < seconds:
                samples.append(read_metrics())
                time.sleep(3)
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)
                state = "timeout"
            else:
                state = "finished" if proc.returncode == 0 else "failed"
        elapsed = round(time.perf_counter() - proc_start, 2)
        response_bytes = outpath.stat().st_size if outpath.exists() else 0
        # Error tags only: never export the actual error text or contents.
        error_text = errpath.read_text(encoding="utf-8", errors="replace") if errpath.exists() else ""
        error_tags = [name for name, term in [
            ("context", "context window"), ("timeout", "timeout"),
            ("connection", "connection refused"), ("traceback", "traceback"),
            ("tool", "tool_call"), ("provider", "provider")
        ] if term in error_text.lower()]
        return {
            "status": "ok" if state == "finished" and response_bytes > 0 else state,
            "elapsed_seconds": elapsed,
            "exit_code": proc.returncode,
            "response_bytes": response_bytes,
            "toolsets": variant,
            "error_categories": error_tags,
            "min_free_ram_gb": min((m["ram_available_gb"] for m in samples if "ram_available_gb" in m), default=None),
            "peak_cpu_percent": max((m["cpu_percent"] for m in samples if "cpu_percent" in m), default=None),
            "max_worker_ram_mb": max(
                (sum(x["ram_mb"] for x in m["processes"]) for m in samples if "processes" in m), default=None),
        }
    except Exception as e:
        return {"status": "test_error", "error_type": type(e).__name__, "toolsets": variant}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--ollama", required=True, type=Path)
    parser.add_argument("--hermes", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--hermes-timeout", type=int, default=90)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["OLLAMA_CONTEXT_LENGTH"] = "65536"
    env["OLLAMA_KEEP_ALIVE"] = "30m"
    env["OLLAMA_HOST"] = "127.0.0.1:11434"
    env["NO_PROXY"] = "127.0.0.1,localhost"
    start = time.time()
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "context_required_by_hermes": 65536,
        "system": read_metrics(),
        "tests": {},
    }
    stdout_log = args.out / "_ollama.stdout.txt"
    stderr_log = args.out / "_ollama.stderr.txt"
    with stdout_log.open("w", encoding="utf-8") as stdout, stderr_log.open("w", encoding="utf-8") as stderr:
        server = subprocess.Popen([str(args.ollama), "serve"], env=env, stdout=stdout, stderr=stderr,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            ready = False
            for i in range(60):
                if server.poll() is not None:
                    break
                try:
                    report["installed_models"] = [x.get("name", "") for x in
                                                   get_json(args.base_url+"/api/tags").get("models", [])]
                    ready = True
                    break
                except Exception:
                    time.sleep(2)
            if not ready:
                raise RuntimeError("Local Ollama server did not become ready")
            report["tests"]["ollama_2048"] = direct_test(args.model, 2048, 90, args.base_url)
            report["tests"]["ollama_65536"] = direct_test(args.model, 65536, 180, args.base_url)
            try:
                loaded = get_json(args.base_url+"/api/ps")
                report["loaded_models"] = [
                    {"name": x.get("name"), "context_length": x.get("context_length"),
                     "size_vram": x.get("size_vram")} for x in loaded.get("models", [])
                ]
            except Exception:
                report["loaded_models"] = []
            # No credentials, no restored memory or user conversations in test home.
            hermes_home = Path(env["HERMES_HOME"])
            for key, val in [
                ("model.default", args.model), ("model.provider", "custom"),
                ("model.base_url", args.base_url+"/v1"),
                ("model.context_length", "65536"), ("model.ollama_num_ctx", "65536"),
                ("approvals.mode", "manual"), ("approvals.unattended_mode", "deny")
            ]:
                p = subprocess.run([str(args.hermes), "config", "set", key, val],
                                   env=env, capture_output=True, text=True, timeout=40)
                if p.returncode:
                    raise RuntimeError("Hermes configuration rejected " + key)
            report["tests"]["hermes_file"] = hermes_test(
                args.hermes, "file", args.hermes_timeout, env, args.out)
            report["tests"]["hermes_default"] = hermes_test(
                args.hermes, None, args.hermes_timeout, env, args.out)
            # Verify an explicit zero-tool selection for near-chat-only use.
            p = subprocess.run([str(args.hermes), "config", "set",
                                "platform_toolsets.cli", "[]"],
                               env=env, capture_output=True, text=True, timeout=40)
            if p.returncode:
                report["tests"]["hermes_chat_only"] = {"status": "config_error"}
            else:
                report["tests"]["hermes_chat_only"] = hermes_test(
                    args.hermes, None, args.hermes_timeout, env, args.out,
                    label="chat_only")
        finally:
            server.terminate()
            try:
                server.wait(timeout=12)
            except subprocess.TimeoutExpired:
                server.kill()
            report["total_wall_seconds"] = round(time.time() - start, 1)
            report_file = args.out / "benchmark.json"
            report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print("DIAGNOSTIC RESULTS (no model messages):")
            for name, value in report["tests"].items():
                print(f"{name}: status={value.get('status')}; seconds={value.get('elapsed_seconds')}; "
                      f"prompt_tokens={value.get('prompt_tokens')}; "
                      f"prefill_tps={value.get('prefill_tokens_per_sec')}; "
                      f"generation_tps={value.get('generation_tokens_per_sec')}; "
                      f"peak_cpu={value.get('peak_cpu_percent')}; "
                      f"min_free_gb={value.get('min_free_ram_gb')}")
            print("Hardware:", report["system"])
            print("Report:", report_file)
            # Windows may keep a logfile open briefly after terminating a
            # worker process. JSON is the only uploaded artifact; cleanup
            # must never mark an otherwise successful benchmark as failed.
            for p in args.out.glob("*txt"):
                try:
                    p.unlink(missing_ok=True)
                except (PermissionError, OSError):
                    pass


if __name__ == "__main__":
    main()
