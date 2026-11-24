"""Type or speak a request -> see the canonical English query."""
import time
import gradio as gr
from food_assistant.gemini import transcribe
from food_assistant.input_layer.canonicalize import canonicalize


def run(text):
    t0 = time.perf_counter()
    q, model = canonicalize(text)
    return q.model_dump(), f"model: {model} · {time.perf_counter() - t0:.1f} s"


def from_text(text):
    if not text.strip():
        return None, "Type something first."
    try:
        return run(text)
    except Exception as e:
        return None, f"❌ {e}"


def from_voice(path):
    if not path:
        return "", None, "No audio received. Wait a second after stopping, then try again."
    try:
        heard = transcribe(path)
        q, info = run(heard)
        return heard, q, info
    except Exception as e:
        return "", None, f"❌ {e}"


with gr.Blocks(title="Canonical query") as demo:
    gr.Markdown("## Step 6: any language → one standard query")
    with gr.Tab("Text"):
        text = gr.Textbox(label="Your request (Bengali, Banglish or English)")
        btn = gr.Button("Canonicalize", variant="primary")
        out = gr.JSON(label="Canonical query (what the VLM will receive)")
        info = gr.Markdown()
        btn.click(from_text, text, [out, info])
        text.submit(from_text, text, [out, info])
    with gr.Tab("Voice"):
        audio = gr.Audio(sources=["microphone"], type="filepath", label="Speak, then stop")
        btn2 = gr.Button("Transcribe + canonicalize", variant="primary")
        heard = gr.Textbox(label="What Gemini heard (shown to the user)")
        out2 = gr.JSON(label="Canonical query")
        info2 = gr.Markdown()
        btn2.click(from_voice, audio, [heard, out2, info2])

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, show_error=True)
