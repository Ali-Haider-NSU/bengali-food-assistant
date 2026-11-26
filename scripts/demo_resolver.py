"""Try the resolver: suggestions update while you type, Enter resolves the whole sentence."""
import gradio as gr
from food_assistant.input_layer.resolver import Resolver

r = Resolver()
TASK_BN = {"dish": "খাবার", "ingredient": "উপকরণ", "ood": "বাংলা খাবার নয়"}


def on_type(text):
    rows = [[s["name_bn"], s["name_en"], TASK_BN.get(s["task"], s["task"]), s["id"], s["score"]]
            for s in r.suggest(text, k=6)]
    return rows


def on_submit(text):
    m = r.resolve(text)
    if m.zone == "accept":
        head = f"### ✅ {m.name_bn} · {m.name_en}\n`{m.task}` / `{m.id}` · score {m.score} · matched: “{m.span}”"
    elif m.zone == "ask":
        opts = " / ".join(f"{r.info(t, i).get('name_bn', i)}" for t, i, _ in m.candidates)
        head = f"### ❓ আপনি কি বোঝাতে চেয়েছেন: {opts}\nscore {m.score}"
    else:
        head = f"### ✗ কোনো খাবার বা উপকরণ পাওয়া যায়নি\nbest score {m.score}"
    cands = "\n".join(f"- `{t}/{i}`: {s}" for t, i, s in m.candidates)
    return f"{head}\n\n**Candidates**\n{cands}"


with gr.Blocks(title="Resolver") as demo:
    gr.Markdown("## A1: resolver · type Bengali, Banglish or English")
    box = gr.Textbox(label="Dish or ingredient (press Enter to resolve the whole sentence)")
    table = gr.Dataframe(headers=["বাংলা", "English", "ধরন", "id", "score"], label="Suggestions")
    result = gr.Markdown()
    box.input(on_type, box, table, trigger_mode="always_last", show_progress="hidden")
    box.submit(on_submit, box, result)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860)
