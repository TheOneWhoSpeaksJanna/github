# Instructions for Codex / ChatGPT agents

This repository is a **GitHub project workspace for code and files**, not a live server.

## Current user goal
The owner works primarily from ChatGPT on Android and wants a coding agent
that can create, update and deliver real project files. Make changes in this
GitHub repository, show diffs or create a pull request, and provide
downloadable outputs when the host interface supports it.

## Operating rules
- Work directly on requested repository code and docs; do not answer with
  only a plan when a concrete file modification is possible.
- Prefer small, testable changes, readable source, and clear README steps.
- Run relevant lightweight tests before claiming a code change is working.
- Never fabricate a test result or say a device/VM is online without logs.
- Do not start long-running GitHub-hosted servers; Actions runners expire.
- Do not expose local Ollama or the old web dashboard to the public Internet.
- Never read, commit, print, or copy GitHub Actions secrets, auth tokens,
  passwords, encrypted workspace keys, or user private data.
- Do not modify or delete legacy AES-GCM release assets:
  `hermes-encrypted-checkpoints` and
  `file-agent-encrypted-checkpoints`.
- Treat `agent/`, old `scripts/file-agent-*.ps1`, and historical Hermes
  documents as archived experiments. They are not an active product.
- The operational Actions workflow is now Codex Remote using a temporary GitHub Windows VM and local Ollama model. The retired File Agent's stop-only control remains for an earlier session; an archived benchmark workflow exists but is disabled. Do not revive retired local servers.

## Implementation guidance
- For normal code-generation tasks, use the ChatGPT/Codex Cloud working
  environment connected to this GitHub repo (when available to the user).
- The user explicitly wants Codex CLI Remote on a temporary GitHub Windows VM with local Ollama. Its account authorization and pairing page must stay password-protected on Tailscale; never print login/pairing codes or account credentials in public Actions logs or artifacts. The local model is for the Codex host, not the regular ChatGPT Android model picker.
- When asked to create files: create them in the repo, validate their paths,
  and provide the file paths plus tests run. For binary exports, use supported
  artifact outputs rather than committing secrets or generated caches.

## Project history
Earlier experiments used a 4-logical-CPU / 16GB Windows GitHub-hosted
runner. Direct Ollama responses could take 2-7 seconds; full Hermes agent
tool usage timed out after 90-240 seconds. A purpose-built file agent
passed isolated tests but proved unreliable for the owner on Android,
so its live workflow was retired. Do not claim those previous tests
establish reliability for a different Codex integration.
