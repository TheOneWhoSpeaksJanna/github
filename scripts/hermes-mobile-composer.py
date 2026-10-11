#!/usr/bin/env python3
"""Add a standard mobile text composer to the pinned Hermes ChatPage.

Hermes embeds its terminal using xterm.js. Android Gboard/IME events are
unreliable in xterm's invisible input. A real HTML textarea receives the
message, and the built-in term.paste sends it through the existing authenticated
PTY, followed by Return. No new network/API port, secrets, or server is needed.

Strict anchors avoid silently patching an incompatible upstream version.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

START_MARKER = "HERME_ANDROID_COMPOSER_V1"
STATE_ANCHOR = "  const wsRef = useRef<WebSocket | null>(null);\n"
UI_ANCHOR = "      <PluginSlot name=\"chat:bottom\" />"

STATE_ADD = """  // HERME_ANDROID_COMPOSER_V1: real mobile textarea for Gboard/IME.
  const [mobileDraft, setMobileDraft] = useState("");
"""

UI_ADD = """      {/* HERME_ANDROID_COMPOSER_V1: xterm's invisible textarea drops some
          Android keyboard events; use a native form and xterm's paste path. */}
      <form
        role="form"
        aria-label="Mobile Hermes message composer"
        className="flex shrink-0 items-end gap-2 rounded-lg border border-current/20 p-2 lg:hidden"
        onSubmit={(event) => {
          event.preventDefault();
          const message = mobileDraft.trim();
          const socket = wsRef.current;
          const terminal = termRef.current;
          if (!message || !terminal || !socket || socket.readyState !== WebSocket.OPEN) return;
          // Paste already works in Hermes on Android, unlike IME composition.
          // xterm.paste uses the existing PTY onData and bracketed-paste handling.
          terminal.paste(message);
          // Allow the PTY to process the paste before sending Return.
          window.setTimeout(() => {
            const active = wsRef.current;
            if (active && active.readyState === WebSocket.OPEN) active.send("\\r");
          }, 250);
          setMobileDraft("");
        }}
      >
        <textarea
          aria-label="Write a message using your Android keyboard"
          placeholder="Type a message here..."
          value={mobileDraft}
          onChange={(event) => setMobileDraft(event.currentTarget.value)}
          rows={2}
          autoComplete="off"
          className="min-h-12 min-w-0 flex-1 resize-none rounded-md border border-current/30 bg-transparent px-3 py-2 text-base"
          onKeyDown={(event) => {
            if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
              event.preventDefault();
              event.currentTarget.form?.requestSubmit();
            }
          }}
        />
        <button
          type="submit"
          aria-label="Send message to Hermes"
          disabled={ptyState !== "open" || !mobileDraft.trim()}
          className="min-h-12 shrink-0 rounded-md border border-current/40 px-4 py-2 text-sm disabled:opacity-40"
        >
          Send
        </button>
      </form>
"""

def patch(path: Path):
    data = path.read_text(encoding="utf-8")
    if START_MARKER in data:
        # Already patched; never duplicate the form.
        assert 'aria-label="Send message to Hermes"' in data, "Partial/modified patch detected"
        print("Hermes mobile composer already applied.")
        return
    if data.count(STATE_ANCHOR) != 1 or data.count(UI_ANCHOR) != 1:
        raise ValueError("Hermes ChatPage changed: safe patch anchors missing or ambiguous")
    if "term.paste(" not in data:
        raise ValueError("Hermes ChatPage no longer supports built-in paste")
    if 'PtyConnectionState = "connecting"' not in data and 'useState<PtyConnectionState>("connecting")' not in data:
        raise ValueError("Unknown Hermes ChatPage connection state")
    data = data.replace(STATE_ANCHOR, STATE_ANCHOR + STATE_ADD, 1)
    data = data.replace(UI_ANCHOR, UI_ADD + UI_ANCHOR, 1)
    path.write_text(data, encoding="utf-8")
    print("Hermes ChatPage mobile textarea + Send button patched.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path, help="path to upstream ChatPage.tsx")
    args = ap.parse_args()
    if not args.source.is_file():
        raise FileNotFoundError(args.source)
    patch(args.source)

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Mobile patch failed safely: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
