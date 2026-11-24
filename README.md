# Bengali Food Assistant

A multimodal assistant for Bengali cooking: understands food photos, voice and text in
Bengali, Banglish or English, and answers in Bengali.

## Status

| Part | Component | Status |
|---|---|---|
| 1. Input layer | Gemini Transcribe for voice | ✅ |
| | Canonicalizer: any input → standard Bengali query + intent | ✅ |
| | Dish data, resolver, autosuggest | in progress |
| 2. Perception + chat | Fine-tuned VLM (Qwen3-VL-4B, QLoRA) | planned |
| 3. App | Gradio demo | planned |

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # then put your Gemini API key in .env
python -m scripts.check_setup
```

## Try the input layer

```bash
python -m scripts.demo_canonicalize    # http://localhost:7860
python -m scripts.eval_canonicalize    # consistency across Bengali / Banglish / English
```
