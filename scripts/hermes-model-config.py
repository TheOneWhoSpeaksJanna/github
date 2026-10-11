#!/usr/bin/env python3
"""Read the user-editable, public Ollama model list for Hermes Agent.

The first uncommented line is the default. Other uncommented lines are
also downloaded. Keep this file free of tokens and secrets.
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

MODEL_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*"
    r"(?:/[A-Za-z0-9][A-Za-z0-9._-]*)?"
    r"(?::[A-Za-z0-9][A-Za-z0-9._-]*)?$"
)
MAX_MODELS = 4


def model_names(path: Path) -> list[str]:
    if not path.is_file():
        raise ValueError(f"Missing {path.name}: add at least one Ollama model name")
    selected = []
    seen = set()
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        value = raw.partition("#")[0].strip()
        if not value:
            continue
        if not MODEL_RE.fullmatch(value) or ".." in value or len(value) > 180:
            raise ValueError(f"Invalid Ollama model name at line {number}: {value!r}")
        canonical = value if ":" in value else value + ":latest"
        if canonical.lower() in seen:
            raise ValueError(f"Duplicate model at line {number}: {value}")
        seen.add(canonical.lower())
        selected.append(value)
    if not selected:
        raise ValueError("No model names set: add at least one uncommented line")
    if len(selected) > MAX_MODELS:
        raise ValueError(f"At most {MAX_MODELS} models can be installed at once")
    return selected


def canonical(name: str) -> str:
    return name if ":" in name else name + ":latest"


def manifest_path(root: Path, name: str) -> Path:
    namespace_model, tag = canonical(name).rsplit(":", 1)
    parts = namespace_model.split("/")
    if len(parts) == 1:
        parts.insert(0, "library")
    return root / "manifests" / "registry.ollama.ai" / parts[0] / parts[1] / tag


def selftest():
    with TemporaryDirectory() as tmp:
        p = Path(tmp) / "hermes-models.txt"
        p.write_text(
            "# comment only\n"
            "qwen2.5-coder:1.5b\n"
            "# qwen3.5:2b\n"
            "qwen3.5:2b\n",
            encoding="utf-8",
        )
        names = model_names(p)
        assert len(names) == 2
        assert names[0] == "qwen2.5-coder:1.5b"
        assert str(manifest_path(Path("X:/models"), names[0])).replace("\\", "/").endswith(
            "/manifests/registry.ollama.ai/qwen2.5-coder:1.5b/latest"
        )
        assert str(manifest_path(Path("X:/models"), names[1])).replace("\\", "/").endswith(
            "/manifests/registry.ollama.ai/library/qwen2.5-coder/1.5b"
        )
        p.write_text("../unsafe\n", encoding="utf-8")
        try:
            model_names(p)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid path accepted")
        p.write_text("qwen3.5:2b\nqwen3.5:2b\n", encoding="utf-8")
        try:
            model_names(p)
        except ValueError:
            pass
        else:
            raise AssertionError("Duplicate model accepted")
    print("Hermes model file parsing, validation, defaults and cache paths verified.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("list", "default", "manifest", "selftest"))
    parser.add_argument("file", nargs="?", type=Path)
    parser.add_argument("--models-root", type=Path)
    parser.add_argument("--model")
    args = parser.parse_args()
    if args.command == "selftest":
        selftest()
        return
    if args.file is None:
        parser.error("Provide the path to hermes-models.txt")
    names = model_names(args.file)
    if args.command == "list":
        print("\n".join(names))
    elif args.command == "default":
        print(names[0])
    else:
        if args.models_root is None or args.model is None:
            parser.error("manifest requires --models-root and --model")
        if args.model not in names:
            raise ValueError("Requested model is not in hermes-models.txt")
        print(manifest_path(args.models_root, args.model))


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(f"Invalid Hermes model configuration: {exc}", file=sys.stderr)
        sys.exit(1)
