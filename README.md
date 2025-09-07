# Agentic Tags & Summary (Ollama)

Tiny pipeline (Planner → Reviewer → Finalizer) that returns **strict JSON** with **exactly 3 tags** and a **≤25-word** summary.

## Requirements

* Python 3.11/3.12
* [Ollama](https://ollama.com) running locally
* Model: `phi3:mini`

## Setup

```bash
ollama pull phi3:mini
python -m venv .venv && source .venv/bin/activate
pip install --upgrade pip ollama pydantic
```

## Run

```bash
python agents_demo.py \
  --model phi3:mini \
  --title "Vector Clocks in Distributed Systems" \
  --content "Explain causal ordering with vector clocks vs Lamport clocks."
# or: --content-file blog.txt
```

## Output (final)

```json
{"tags":["t1","t2","t3"],"summary":"<= 25 words"}
```

## Notes

* Enforces JSON, 3 tags, and word limit.
* Swap models via `--model` (e.g., `smollm:1.7b`).
