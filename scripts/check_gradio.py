"""Step 1 check: Gemini text + Gemini Transcribe in a Gradio page."""
import time
import gradio as gr
from google import genai
from google.genai import types
from food_assistant.config import (get_gemini_key, GEMINI_TEXT_FALLBACKS,
                                   GEMINI_TRANSCRIBE_MODEL)

client = genai.Client(api_key=get_gemini_key(),
                      http_options=types.HttpOptions(api_version="v1beta"))

TEMPORARY = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED")


def extract_text(r):
    # The transcribe model may put its text outside r.text, so search the response
    if getattr(r, "text", None):
        return r.text
    found = []
    def walk(x, key=""):
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, k)
        elif isinstance(x, list):
            for v in x:
                walk(v, key)
        elif isinstance(x, str) and x.strip() and key in ("text", "transcript", "transcription"):
            found.append(x.strip())
    walk(r.model_dump(exclude_none=True))
    return " ".join(dict.fromkeys(found))


def ask_text(prompt):
    if not prompt.strip():
        return "Type something first.", ""
    errors = []
    for model in GEMINI_TEXT_FALLBACKS:
        for attempt in range(2):
            try:
                r = client.models.generate_content(model=model, contents=prompt)
                return r.text, f"model: {model}"
            except Exception as e:
                msg = str(e)
                if any(k in msg for k in TEMPORARY) and attempt == 0:
                    time.sleep(2)          # busy: one short retry, then next model
                    continue
                errors.append(f"{model}: {msg[:120]}")
                break
    return "❌ All models failed.", "\n".join(errors)


def transcribe(audio_path):
    if not audio_path:
        return "No audio received. Wait a second after stopping, then try again.", ""
    f = client.files.upload(file=audio_path)
    try:
        for attempt in range(3):
            try:
                r = client.models.generate_content(model=GEMINI_TRANSCRIBE_MODEL, contents=[f])
                return extract_text(r) or "(empty transcript)", f"model: {GEMINI_TRANSCRIBE_MODEL}"
            except Exception as e:
                msg = str(e)
                if any(k in msg for k in TEMPORARY) and attempt < 2:
                    time.sleep(3 * (attempt + 1))
                    continue
                return f"❌ {msg[:300]}", ""
    finally:
        client.files.delete(name=f.name)


with gr.Blocks(title="Step 1 check") as demo:
    gr.Markdown("## Step 1 check: Gemini connection")
    with gr.Tab("Text"):
        prompt = gr.Textbox(label="Ask Gemini anything", value="Say hello in Bengali.")
        out = gr.Textbox(label="Answer")
        info = gr.Textbox(label="Info", lines=2)
        gr.Button("Send", variant="primary").click(ask_text, prompt, [out, info])
    with gr.Tab("Voice"):
        audio = gr.Audio(sources=["microphone"], type="filepath", label="Speak, then stop")
        transcript = gr.Textbox(label="Transcript")
        info2 = gr.Textbox(label="Info")
        gr.Button("Transcribe", variant="primary").click(transcribe, audio, [transcript, info2])

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, show_error=True)
