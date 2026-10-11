"""Isolated live benchmark: Ollama -> structured local task -> real files -> ZIP."""
import argparse
from pathlib import Path
import os
import subprocess
import time
from urllib.request import urlopen
from file_agent import FileAgent, OllamaModel, workspace_files, make_zip
import zipfile
import io


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ollama", type=Path, required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--workspace", type=Path, required=True)
    args = p.parse_args()
    os.environ["OLLAMA_HOST"] = "127.0.0.1:11434"
    os.environ["OLLAMA_CONTEXT_LENGTH"] = "4096"
    os.environ["OLLAMA_NUM_PARALLEL"] = "1"
    os.environ["OLLAMA_MAX_LOADED_MODELS"] = "1"
    os.environ["NO_PROXY"] = "127.0.0.1,localhost"
    with open(args.workspace.parent / "agent-smoke-ollama.stdout.txt", "w") as out, \
         open(args.workspace.parent / "agent-smoke-ollama.stderr.txt", "w") as err:
        proc = subprocess.Popen([str(args.ollama), "serve"], stdout=out, stderr=err,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            for i in range(55):
                try:
                    with urlopen("http://127.0.0.1:11434/api/tags", timeout=3):
                        break
                except Exception:
                    if i == 54:
                        raise RuntimeError("Ollama backend unavailable")
                    time.sleep(2)
            agent = FileAgent(args.workspace, OllamaModel(args.model))
            t = time.monotonic()
            result = agent.run(
                "Create a file named hello.md with a Markdown heading "
                "Local Agent and a sentence explaining that the user can "
                "download files to Android. Output the file, not merely an explanation.")
            elapsed = round(time.monotonic() - t, 2)
            files = workspace_files(args.workspace)
            if not files or not (args.workspace / "hello.md").is_file():
                raise RuntimeError("Agent did not create the requested hello.md file")
            content = (args.workspace / "hello.md").read_text(encoding="utf-8")
            if "Local Agent" not in content or len(content.strip()) < 20:
                raise RuntimeError("Generated Markdown file content was incorrect")
            packed = make_zip(args.workspace)
            with zipfile.ZipFile(io.BytesIO(packed)) as z:
                if "hello.md" not in z.namelist() or z.read("hello.md").decode() != content:
                    raise RuntimeError("ZIP download did not contain the generated file")
            print("PASSED: Ollama generated structured file actions, the sandbox wrote a real file, and ZIP export preserved the content.")
            print("MODEL:", args.model)
            print("TASK ELAPSED SECONDS:", elapsed)
            print("FILE COUNT:", len(files))
            print("OUTPUT SIZE BYTES:", len(content.encode()))
            print("OLLAMA GENERATION SECONDS:", result["metrics"].get("generation_seconds"))
            print("PROMPT TOKENS:", result["metrics"].get("prompt_tokens"))
            print("OUTPUT TOKENS:", result["metrics"].get("generated_tokens"))
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
