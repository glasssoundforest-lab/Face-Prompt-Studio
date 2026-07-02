"""
fps-adapters/gradio/app.py — FPS Gradio アダプター ★v3.0
Gradio UI を提供し A1111 Extension タブとしても動作する。

スタンドアロン起動:
    python fps-adapters/gradio/app.py  → http://localhost:7861

A1111 Extension:
    extensions/ 内にシンボリックリンクを置いて再起動 → "FPS" タブが出現
"""
from __future__ import annotations
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
for _p in (str(_REPO/"fps-core"), str(_REPO/"fps-adapters")):
    if _p not in sys.path: sys.path.insert(0, _p)


def _ctx():
    try:
        from cli.context import CliContext  # type: ignore
        return CliContext(data_root=_REPO / "fps-data")
    except Exception: return None


def compile_fn(pos, neg, apply_pf, max_wt):
    ctx = _ctx()
    if not ctx: return pos, neg, "Context 未初期化"
    try:
        r = ctx.pipeline_manager.compile(pos)
        return r.prompt, r.negative or neg, f"タグ数:{r.tag_count}"
    except Exception as e: return pos, neg, f"Error:{e}"


def translate_fn(text):
    ctx = _ctx()
    if not ctx: return ""
    try: return ctx.translate_engine.translate(text).to_prompt()
    except Exception as e: return f"Error:{e}"


def wildcard_fn(template, n, seed):
    ctx = _ctx()
    if not ctx: return template
    try:
        from wildcard.engine import WildcardEngine  # type: ignore
        e = WildcardEngine(wildcard_manager=ctx.wildcard_manager,
                           seed=None if seed < 0 else int(seed))
        return "\n---\n".join(e.preview_expand(template, n=int(n),
                                                   seed=None if seed < 0 else int(seed)))
    except Exception as e2: return f"Error:{e2}"


def create_gradio_app():
    import gradio as gr
    with gr.Blocks(title="Face Prompt Studio v3.0", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 🎭 Face Prompt Studio v3.0")
        with gr.Tab("🔧 コンパイル"):
            with gr.Row():
                with gr.Column():
                    pos_i = gr.Textbox(label="Positive", lines=4,
                                       placeholder="masterpiece, 1girl, ...")
                    neg_i = gr.Textbox(label="Negative", lines=2)
                    with gr.Row():
                        apf = gr.Checkbox(label="Profile 適用", value=False)
                        mwt = gr.Slider(1.0, 3.0, value=2.0, label="Max Weight")
                    gr.Button("▶ コンパイル", variant="primary").click(
                        compile_fn, [pos_i, neg_i, apf, mwt],
                        [gr.Textbox(label="Pos 結果", lines=4),
                         gr.Textbox(label="Neg 結果", lines=2),
                         gr.Textbox(label="情報", lines=1)])
        with gr.Tab("🇯🇵 日本語→タグ"):
            with gr.Row():
                jp_i = gr.Textbox(label="日本語テキスト", lines=3,
                                   placeholder="青い目の金髪の少女、笑顔")
                jp_o = gr.Textbox(label="変換後タグ", lines=3)
            gr.Button("変換", variant="primary").click(translate_fn, [jp_i], [jp_o])
        with gr.Tab("🎲 Wildcard"):
            wc_i   = gr.Textbox(label="テンプレート", lines=3,
                                  value="__style__, [[blue|red|green]] eyes")
            with gr.Row():
                wc_n = gr.Slider(1, 10, value=5, label="件数", step=1)
                wc_s = gr.Number(label="Seed (-1=random)", value=-1)
            wc_o = gr.Textbox(label="展開結果", lines=10)
            gr.Button("展開", variant="primary").click(wildcard_fn, [wc_i, wc_n, wc_s], [wc_o])
    return demo


# A1111 Extension エントリポイント
def on_ui_tabs():
    return [(create_gradio_app(), "FPS", "fps_promptstudio")]


if __name__ == "__main__":
    create_gradio_app().launch(server_name="0.0.0.0", server_port=7861)
