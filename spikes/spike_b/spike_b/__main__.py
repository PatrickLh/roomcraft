"""Spike B 入口：场景截图 + 风格参考图 → 参考图生图 → AI 标识 → 报告。

用法：
    pnpm spike:b -- --scene <场景截图.png> --style <风格图1.jpg> [--style <风格图2.jpg> ...]
                    [--count 3] [--out spikes/reports/spike-b] [--provider openai_compatible]

所有产物经过 app/media/ai_label.label_generated_image（显式水印 + 隐式元数据）——
按计划 M0-03 要求，从首次生成就带 AI 标识。
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings
from app.media.ai_label import label_generated_image, read_metadata
from app.providers import make_image_provider
from app.providers.base import ImageRef, ProviderError

from spike_b import PROMPT_VERSION

REPO = Path(__file__).resolve().parents[3]
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}

DEFAULT_PROMPT = """第一张图是一个室内户型的三维渲染（布局与结构参考）。
请保持第一张图完全一致的房间布局、墙体位置、门窗位置与家具摆放，
仅将材质、色彩、灯光与家具样式替换为第二张图所示的整体装修风格，
输出一张写实照片级的室内效果图。视角与第一张图保持一致。不要改变任何结构。"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Spike B：参考图生图验证")
    parser.add_argument("--scene", required=True, help="场景截图路径（可用原型页『导出截图』获得）")
    parser.add_argument("--style", required=True, action="append", help="风格参考图，可多次提供")
    parser.add_argument("--prompt-override", default=None)
    parser.add_argument("--count", type=int, default=3, help="每个风格生成几张变体")
    parser.add_argument("--size", default="1440x720")
    parser.add_argument("--out", default=str(REPO / "spikes" / "reports" / "spike-b"))
    parser.add_argument("--provider", default=None)
    # 兼容 pnpm 透传时的首个 `--`（pnpm spike:b -- --scene ...）
    args = parser.parse_args([a for a in sys.argv[1:] if a != "--"])

    scene_path = Path(args.scene)
    style_paths = [Path(p) for p in args.style]
    for p in [scene_path, *style_paths]:
        if not p.exists() or p.suffix.lower() not in IMAGE_EXTS:
            print(f"图片不存在或格式不支持: {p}")
            return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    provider = make_image_provider(get_settings(), args.provider)
    prompt = args.prompt_override or DEFAULT_PROMPT

    refs = [
        ImageRef(data=scene_path.read_bytes(), mime=MIME[scene_path.suffix.lower()]),
        *[ImageRef(data=p.read_bytes(), mime=MIME[p.suffix.lower()]) for p in style_paths],
    ]

    print(f"provider={provider.name} model={provider.model} prompt={PROMPT_VERSION} count={args.count}")
    records: list[dict] = []
    for style in style_paths:
        for i in range(1, args.count + 1):
            name = f"{style.stem}-v{i}"
            print(f"  → {name} ...", flush=True)
            t0 = time.monotonic()
            try:
                img = asyncio.run(provider.generate(prompt, refs, args.size))
            except ProviderError as e:
                print(f"    FAIL {e}")
                records.append({"name": name, "ok": False, "failure": str(e)[:200],
                                "timeS": round(time.monotonic() - t0, 2)})
                continue
            elapsed = round(time.monotonic() - t0, 2)
            labeled = label_generated_image(img.data, {"model": img.model, "task": f"spike-b/{PROMPT_VERSION}"})
            target = out_dir / f"{name}.png"
            target.write_bytes(labeled)

            meta = read_metadata(labeled)
            ok_flag = meta.get("AI-Generated") == "true"
            records.append({
                "name": name, "ok": True, "timeS": elapsed,
                "bytes": len(labeled), "model": img.model,
                "labeled": ok_flag,
                "file": str(target.relative_to(REPO)) if target.is_relative_to(REPO) else str(target),
            })
            print(f"    OK  {elapsed}s 标识={'√' if ok_flag else '×'} → {target.name}")

    cols = ["name", "ok", "failure", "timeS", "bytes", "model", "labeled", "file"]
    with (out_dir / "results.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(records)

    ok_count = sum(1 for r in records if r["ok"])
    (out_dir / "report.md").write_text(
        f"# Spike B 报告\n\n"
        f"- 时间：{datetime.now(UTC).isoformat()}\n"
        f"- provider：{provider.name} / {provider.model} / prompt {PROMPT_VERSION}\n"
        f"- 成功：{ok_count}/{len(records)}（AI 标识全部强制写入）\n"
        f"- 场景图：{scene_path.name}；风格图：{', '.join(p.name for p in style_paths)}\n\n"
        f"> 布局保持 / 风格还原的『主观可用率 ≥ 60%』必须按 spikes/eval/scoring-rubric.md 人工评分；\n"
        f"> 本报告只记录机器可测的执行事实（成功、耗时、标识完整性）。\n",
        encoding="utf-8",
    )
    print(f"\n成功 {ok_count}/{len(records)}；产物：{out_dir}")
    return 0 if ok_count > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
