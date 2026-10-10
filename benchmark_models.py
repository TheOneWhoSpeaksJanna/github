#!/usr/bin/env python3
"""CPU Ollama benchmark: coding syntax and latency. No generated code is executed."""
import ast, datetime, json, os, pathlib, re, subprocess, time, urllib.request
API="http://127.0.0.1:11434"
MODELS=[
"qwen2.5-coder:0.5b","qwen2.5-coder:1.5b","qwen2.5-coder:3b",
"qwen2.5-coder:0.5b-instruct-q4_K_S","qwen2.5-coder:0.5b-instruct-q5_1",
"qwen3:0.6b","qwen3:1.7b","qwen3:4b",
"qwen2.5:0.5b","qwen2.5:1.5b","qwen2.5:3b",
"gemma3:1b","gemma3:4b","llama3.2:1b","llama3.2:3b",
"smollm2:360m","smollm2:1.7b","deepseek-coder:1.3b",
"starcoder2:3b","codegemma:2b",
]
TASKS=[
("Python function","Write only Python code for def is_prime(n): returning True for primes including 2 and False for 0,1,negatives and composites. No prose.","python"),
("JavaScript function","Write only JavaScript code implementing function add(a,b) that returns a+b. No prose.","javascript"),
("Python bug fix","Fix this Python function; return only corrected code: def factorial(n):\\n    if n == 0: return 0\\n    return n * factorial(n-1)","python"),
]
def api(path,obj,timeout=100):
 req=urllib.request.Request(API+path,data=json.dumps(obj).encode(),headers={"Content-Type":"application/json"})
 with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
def extract(s):
 match=re.search(r"\x60\x60\x60(?:python|javascript|js)?\s*(.*?)\x60\x60\x60",s,re.S|re.I)
 return match.group(1).strip() if match else s.strip()
def grade(kind,txt):
 txt=extract(txt)
 if kind=="python":
  try: ast.parse(txt)
  except SyntaxError:return 0
  if "is_prime" in txt:return int(all(x in txt for x in ("def is_prime","return"))) 
  return int("def factorial" in txt and "return 1" in txt)
 return int("function add" in txt and "return a + b" in txt.replace("a+b","a + b"))
rows=[]
deadline=time.monotonic()+125*60
for model in MODELS:
 record={"model":model,"status":"not tested","tps":0,"quality":0,"latency":0}
 if time.monotonic()>deadline:
  record["status"]="time budget exceeded";rows.append(record);continue
 print("BENCHMARK:",model,flush=True)
 try:
  # Pull timeout, then delete after tests to keep free disk space bounded.
  subprocess.run(["C:\\Ollama\\ollama.exe","pull",model],timeout=310,check=True)
  total_eval,total_ns,first,points=0,0,[],0
  for title,prompt,kind in TASKS:
   before=time.monotonic()
   result=api("/api/generate",{"model":model,"prompt":prompt.replace("\\n","\n"),
      "stream":False,"think":False,"options":{"num_ctx":1024,"num_predict":170,"temperature":0}},100)
   first.append(time.monotonic()-before)
   total_eval+=result.get("eval_count",0)
   total_ns+=result.get("eval_duration",0)
   points+=grade(kind,result.get("response",""))
  record.update(status="tested",tps=round(total_eval/max(total_ns/1e9,0.001),2),
                quality=points,latency=round(sum(first)/len(first),2))
 except Exception as e:record["status"]="failed: "+str(e)[:100]
 finally:
  try:subprocess.run(["C:\\Ollama\\ollama.exe","rm",model],timeout=35,capture_output=True)
  except Exception:pass
 rows.append(record)
tested=[r for r in rows if r["status"]=="tested"]
# Coding accuracy dominates speed. Fast but wrong code should not win.
eligible=[r for r in tested if r["quality"]>=2 and r["tps"]>=8]
winner=max(eligible,key=lambda r:(r["quality"],r["tps"])) if eligible else None
stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
md=["# CPU-only model benchmark",f"Run: {stamp}","","Tests: 3 short coding tasks. Generated code was **not executed**; scores are conservative syntax/heuristic checks, not proof of correctness.","","Speed measured on this particular GitHub Actions runner. Results are not comparable to ChatGPT cloud latency.","", "| Model | Status | Generation tokens/s | Avg response seconds | Coding checks /3 |","|---|---|---:|---:|---:|"]
for r in rows:
 md.append(f"| \x60{r['model']}\x60 | {r['status'].replace('|','/')} | {r['tps']} | {r['latency']} | {r['quality']} |")
md+=["",f"**Winner:** {winner['model'] if winner else 'No qualifying model; keep previous default'}","",
"Selection criteria: at least 2/3 checks and 8 generation tokens/s; among qualifying models prioritize coding checks, then generation speed.","",
"Some models may fail to download or exceed time limits; these are marked rather than silently excluded."]
pathlib.Path("MODEL_BENCHMARK.md").write_text("\n".join(md)+"\n",encoding="utf8")
if winner:pathlib.Path("selected-model.txt").write_text(winner["model"]+"\n",encoding="utf8")
print("Winner:", winner["model"] if winner else "unchanged",flush=True)
