#!/usr/bin/env python3
"""Compare CPU throughput of standard Qwen2.5 Coder 1.5B and 3B without running generated code."""
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

def start_server(threads):
    env = os.environ.copy()
    env['OLLAMA_HOST'] = '127.0.0.1:11434'
    if threads is None:
        env.pop('LLAMA_ARG_THREADS', None)
    else:
        env['LLAMA_ARG_THREADS'] = str(threads)
    process = subprocess.Popen([OLLAMA, 'serve'], env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):
        try:
            request('/api/tags', timeout=2)
            return process
        except Exception:
            if process.poll() is not None:
                raise RuntimeError('Ollama exited: '+str(process.returncode))
            time.sleep(1)
    process.terminate()
    raise RuntimeError('Ollama server did not become ready')

def stop_server(process):
    try:
        process.terminate()
        process.wait(timeout=10)
    except Exception:
        process.kill()
        process.wait(timeout=5)
    time.sleep(2)

def syntax_ok(text, name):
    fenced = re.search(r'\x60\x60\x60(?:python)?\s*(.*?)\x60\x60\x60', text, re.I | re.S)
    source = fenced.group(1) if fenced else text
    try:
        tree = ast.parse(source)
        return int(any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and node.name == name for node in tree.body))
    except SyntaxError:
        return 0

def generate(model, prompt, limit=160):
    start = time.perf_counter()
    response = request('/api/generate', {
        'model': model, 'prompt': prompt, 'stream': False,
        'keep_alive': '5m',
        'options': {'num_ctx': 2048, 'num_predict': limit, 'temperature': 0.0}
    }, timeout=130)
    elapsed = time.perf_counter() - start
    seconds = max(float(response.get('eval_duration',0)) / 1e9, 0.001)
    tps = int(response.get('eval_count',0)) / seconds
    return {'tps':tps, 'seconds':elapsed, 'text':response.get('response','')}

def main():
    logical = os.cpu_count() or 2
    threads_list = [None] + [n for n in (1,2,3,4,6,8) if n <= logical]
    rows = []
    print('Logical CPUs:', logical, flush=True)
    server = start_server(None)
    try:
        for model in MODELS:
            print('Downloading', model, flush=True)
            subprocess.run([OLLAMA,'pull',model],check=True,timeout=600)
    finally:
        stop_server(server)
    for threads in threads_list:
        print('Benchmarking thread setting:',threads,flush=True)
        try:
            server = start_server(threads)
            try:
                for model in MODELS:
                    try:
                        generate(model,'Say OK.',limit=8)
                        values = [generate(model, prompt) for _,prompt in PROMPTS]
                        accuracy = sum(syntax_ok(v['text'], name)
                                       for (name,_), v in zip(PROMPTS,values))
                        row = {'model':model,'threads':threads,
                               'tps':round(statistics.median(v['tps'] for v in values),2),
                               'seconds':round(statistics.mean(v['seconds'] for v in values),2),
                               'syntax':accuracy,'status':'OK'}
                    except Exception as exc:
                        row = {'model':model,'threads':threads,'tps':0,'seconds':0,
                               'syntax':0,'status':('FAILED '+str(exc))[:80]}
                    rows.append(row)
                    print('RESULT:',json.dumps(row),flush=True)
            finally:
                stop_server(server)
        except Exception as exc:
            for model in MODELS:
                rows.append({'model':model,'threads':threads,'tps':0,'seconds':0,
                             'syntax':0,'status':('FAILED '+str(exc))[:80]})

    def best(model):
        valid = [r for r in rows if r['model']==model and r['status']=='OK' and r['syntax']>=1]
        return max(valid,key=lambda r:(r['syntax'],r['tps'])) if valid else None
    a,b = best(MODELS[0]),best(MODELS[1])
    promote = bool(a and b and b['tps']>=12 and
                   b['tps']>=0.70*a['tps'] and b['syntax']>=a['syntax'])

    report = ['# CPU tuning benchmark', '',
      f"Completed UTC: {dt.datetime.now(dt.timezone.utc).isoformat()}",
      f"Visible logical processors: **{logical}**", '',
      'Compared two standard coding models with identical short prompts and 2048-token context.',
      'Syntax checking verifies named function definitions parse, **not that the generated code works**.',
      'Thread control via LLAMA_ARG_THREADS is version-dependent and may be ignored.',
      '', '| Model | Threads | Tokens/sec | Average seconds | Syntax checks | Status |',
      '|---|---:|---:|---:|---:|---|']
    for r in rows:
        t = 'default' if r['threads'] is None else str(r['threads'])
        report.append(f"| {r['model']} | {t} | {r['tps']} | {r['seconds']} | {r['syntax']}/2 | {r['status'].replace('|','/')} |")
    report.extend(['','## Decision',
      f"Best 1.5B: {a['tps']} t/s, threads={a['threads']}" if a else '1.5B failed',
      f"Best 3B: {b['tps']} t/s, threads={b['threads']}" if b else '3B failed',
      '**Promote to 3B: '+('YES' if promote else 'NO')+'**', '',
      'Rule: 3B must exceed 12 t/s (versus previous 9.10), reach at least 70% of optimized 1.5B throughput, and match or exceed the syntax score.',
      'No claim of ChatGPT-equivalent speed. Benchmarks on different GitHub-hosted VMs may vary.'])
    Path('CPU_TUNING.md').write_text('\n'.join(report)+'\n',encoding='utf8')
    Path('CPU_TUNING.json').write_text(json.dumps({
      'date':dt.datetime.now(dt.timezone.utc).isoformat(),
      'logical_processors':logical,'best_1_5b':a,'best_3b':b,
      'promote_3b':promote,'rows':rows},indent=2)+'\n',encoding='utf8')
    if promote:
        Path('selected-model.txt').write_text('qwen2.5-coder:3b\n',encoding='utf8')
    print('AUTO PROMOTION:',promote,flush=True)

if __name__=='__main__':
    main()
