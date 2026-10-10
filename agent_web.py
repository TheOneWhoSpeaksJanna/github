"""Private, limited-tool Ollama chat gateway, exposed only by Tailscale Serve."""
import ast
import datetime
import json
import operator
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = "qwen3:4b"
API = "http://127.0.0.1:11434/api/chat"
PAGE = r"""<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><meta charset="utf-8"><title>My Local AI</title>
<style>body{margin:0;background:#10151d;color:#eef2f8;font:16px system-ui}main{max-width:780px;margin:auto;height:100dvh;display:flex;flex-direction:column}header{padding:16px;border-bottom:1px solid #36404e;font-weight:700}#messages{overflow:auto;flex:1;padding:16px}.m{padding:12px 16px;border-radius:15px;margin:9px 0;white-space:pre-wrap;overflow-wrap:anywhere;background:#283342}.me{background:#174a74;margin-left:12%}.bot{margin-right:12%}form{display:flex;gap:8px;padding:12px}input{flex:1;min-width:0;font:inherit;background:#202b39;color:white;border:1px solid #54637a;border-radius:10px;padding:12px}button{font:inherit;border:0;border-radius:10px;background:#5aa7f4;padding:12px}small{color:#adb9ca}</style>
<main><header>Local AI <small>· Qwen3 4B · private via Tailscale</small></header><section id="messages"><div class="m bot">Ready. I can chat, calculate, and give the current UTC time.</div></section><form id="form"><input id="msg" placeholder="Ask anything…" autocomplete="off" required><button id="send">Send</button></form></main>
<script>let history=[];const m=document.getElementById('messages'),input=document.getElementById('msg'),button=document.getElementById('send');function bubble(text,kind){let d=document.createElement('div');d.className='m '+kind;d.textContent=text;m.appendChild(d);m.scrollTop=m.scrollHeight;return d}
document.getElementById('form').onsubmit=async(e)=>{e.preventDefault();let value=input.value.trim();if(!value)return;input.value='';bubble(value,'me');button.disabled=true;let pending=bubble('Thinking…','bot');try{let r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:value,history:history.slice(-12)})});let data=await r.json();if(!r.ok)throw Error(data.error||r.status);pending.textContent=data.reply;history=data.history.slice(-12)}catch(e){pending.textContent='Error: '+e.message}finally{button.disabled=false;input.focus()}};</script></html>"""
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
       ast.UAdd: operator.pos, ast.USub: operator.neg}

def calculate(expr):
    if len(expr) > 100:
        raise ValueError("Expression too long")
    def walk(node, depth=0):
        if depth > 12: raise ValueError("Expression too complex")
        if isinstance(node, ast.Constant) and type(node.value) in (int,float):
            if abs(node.value)>1e12: raise ValueError("Number too large")
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
            return OPS[type(node.op)](walk(node.operand,depth+1))
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            result=OPS[type(node.op)](walk(node.left,depth+1),walk(node.right,depth+1))
            if abs(result)>1e15: raise ValueError("Result too large")
            return result
        raise ValueError("Only basic arithmetic supported")
    return str(walk(ast.parse(expr,mode="eval").body))

TOOLS = [
    {"type":"function","function":{"name":"calculator","description":"Calculate basic arithmetic.",
     "parameters":{"type":"object","properties":{"expression":{"type":"string"}},"required":["expression"]}}},
    {"type":"function","function":{"name":"utc_time","description":"Return current UTC date and time.",
     "parameters":{"type":"object","properties":{}}}}
]
def model_call(messages):
    payload=json.dumps({"model":MODEL,"messages":messages,"tools":TOOLS,
      "stream":False,"think":False,"options":{"num_ctx":2048,"num_predict":360}}).encode()
    req=urllib.request.Request(API,data=payload,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=240) as response:
        return json.load(response)["message"]

class Handler(BaseHTTPRequestHandler):
    def respond(self,status,content,ctype="application/json"):
        self.send_response(status);self.send_header("Content-Type",ctype)
        self.send_header("Cache-Control","no-store");self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Content-Security-Policy","default-src 'self' 'unsafe-inline'")
        self.end_headers();self.wfile.write(content)
    def do_GET(self):
        if self.path == "/":
            self.respond(200,PAGE.encode(),"text/html; charset=utf-8")
        elif self.path == "/health":
            self.respond(200,b'{"ok":true}')
        else:self.respond(404,b'{"error":"Not found"}')
    def do_POST(self):
        if self.path!="/chat":return self.respond(404,b'{"error":"Not found"}')
        if self.headers.get("Content-Type","").split(";")[0]!="application/json":
            return self.respond(415,b'{"error":"JSON required"}')
        try:
            n=int(self.headers.get("Content-Length","0"))
            if n<=0 or n>32000:raise ValueError("Request size invalid")
            inp=json.loads(self.rfile.read(n))
            user=inp.get("message","")
            if not isinstance(user,str) or not 0<len(user)<=3000:raise ValueError("Message too long")
            prior=inp.get("history",[])
            if not isinstance(prior,list):raise ValueError("Invalid history")
            safe=[]
            for m in prior[-12:]:
                if isinstance(m,dict) and m.get("role") in ("user","assistant") and isinstance(m.get("content"),str):
                    safe.append({"role":m["role"],"content":m["content"][:3000]})
            msgs=[{"role":"system","content":"You are a useful local assistant. You have access to a calculator and UTC clock. Never claim to have executed tools not provided. You cannot access files, terminal commands, email or web pages."}]+safe+[{"role":"user","content":user}]
            for _ in range(3):
                answer=model_call(msgs)
                calls=answer.get("tool_calls") or []
                if not calls:break
                msgs.append(answer)
                for tool in calls[:3]:
                    fn=tool.get("function",{})
                    try:
                        args=fn.get("arguments",{})
                        if isinstance(args,str):args=json.loads(args)
                        if fn.get("name")=="calculator": result=calculate(str(args.get("expression","")))
                        elif fn.get("name")=="utc_time":result=datetime.datetime.now(datetime.timezone.utc).isoformat()
                        else:result="Tool unavailable"
                    except Exception as e:result="Tool error: "+str(e)
                    msgs.append({"role":"tool","tool_name":fn.get("name","unknown"),"content":result})
            reply=answer.get("content") or "I couldn't complete that request."
            history=(safe+[{"role":"user","content":user},{"role":"assistant","content":reply}])[-12:]
            self.respond(200,json.dumps({"reply":reply,"history":history}).encode())
        except Exception as e:
            self.respond(400,json.dumps({"error":str(e)}).encode())

if __name__=="__main__":
    print("Local AI chat on 127.0.0.1:8765",flush=True)
    ThreadingHTTPServer(("127.0.0.1",8765),Handler).serve_forever()
