"""Spike A 入口：批量跑样本 → 机器校验 → 产物落盘 → 汇总报告。

用法：
    pnpm spike:a -- [--samples-dir spikes/samples] [--out spikes/reports/spike-a]
                    [--provider openai_compatible] [--limit N]

注意：本脚本的 ok = 「JSON 可解析 + Schema 通过 + 语义通过」的机器校验前置门槛；
「结构可用率 ≥ 80%」必须按 spikes/eval/scoring-rubric.md 人工评分，机器指标不能替代。
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings
from app.plan.checks import check_semantics, is_usable
from app.providers import make_vision_provider
from app.providers.base import ImageRef, ProviderError
from jsonschema import Draft202012Validator

from spike_a.prompt import PROMPT_VERSION

REPO = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO / "packages" / "shared-schema" / "floor-plan.schema.json"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def strip_fences(text: str) -> str:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    return m.group(1) if m else text


def parse_model_output(text: str) -> dict:
    """模型输出 → dict；不是合法 JSON 则抛 ValueError。"""
    return json.loads(strip_fences(text))


def max_scale_deviation(plan: dict) -> float | None:
    devs = []
    for s in plan.get("scale", {}).get("references", []):
        p1, p2, v = s.get("p1", {}), s.get("p2", {}), float(s.get("valueM", 0))
        d = ((p2.get("x", 0) - p1.get("x", 0)) ** 2 + (p2.get("y", 0) - p1.get("y", 0)) ** 2) ** 0.5
        devs.append(abs(v - d))
    return max(devs) if devs else None


async def run_one(provider, validator: Draft202012Validator, system: str, prompt: str, image: Path) -> dict:
    record: dict = {
        "sample": image.name,
        "provider": provider.name,
        "model": provider.model,
        "promptVersion": PROMPT_VERSION,
    }
    ref = ImageRef(data=image.read_bytes(), mime=MIME.get(image.suffix.lower(), "image/png"))
    t0 = time.monotonic()
    try:
        resp = await provider.complete(system, prompt, ref)
    except ProviderError as e:
        record.update(ok=False, stage="provider", failure=str(e)[:200], timeS=round(time.monotonic() - t0, 2))
        return record
    record["timeS"] = round(time.monotonic() - t0, 2)
    record["usage"] = resp.usage

    try:
        data = parse_model_output(resp.text)
    except (ValueError, TypeError) as e:
        record.update(ok=False, stage="parse", failure=f"模型输出不是合法 JSON: {e}; 前200字: {resp.text[:200]}")
        return record
    record["raw"] = data

    if "failure" in data:
        f = data.get("failure", {})
        record.update(ok=False, stage="model_failure",
                      failureCategory=f.get("category", "unclassified"),
                      failure=str(f.get("reason", ""))[:200])
        return record

    errors = [str(e.message) for e in validator.iter_errors(data)]
    if errors:
        record.update(ok=False, stage="schema", failure="; ".join(errors)[:300])
        return record
    issues = check_semantics(data)
    if not is_usable(issues):
        record.update(ok=False, stage="semantic",
                      failure="; ".join(i.message for i in issues if i.level == "error")[:300])
        return record

    record.update(
        ok=True,
        stage="ok",
        wallCount=len(data.get("walls", [])),
        doorCount=sum(1 for w in data.get("walls", []) for o in w.get("openings", []) if o["type"] == "door"),
        windowCount=sum(1 for w in data.get("walls", []) for o in w.get("openings", []) if o["type"] == "window"),
        roomCount=len(data.get("rooms", [])),
        scaleRefs=len(data.get("scale", {}).get("references", [])),
        maxScaleDeviationM=max_scale_deviation(data),
        unsupported=data.get("meta", {}).get("unsupportedFeatures", []),
    )
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Spike A：户型图识别验证")
    parser.add_argument("--samples-dir", default=str(REPO / "spikes" / "samples"))
    parser.add_argument("--out", default=str(REPO / "spikes" / "reports" / "spike-a"))
    parser.add_argument("--provider", default=None, help="覆盖配置的 provider（mock | openai_compatible）")
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 张")
    # 兼容 pnpm 透传时的首个 `--`（pnpm spike:a -- --provider mock）
    args = parser.parse_args([a for a in sys.argv[1:] if a != "--"])

    from spike_a.prompt import SYSTEM, build_user_prompt

    samples_dir = Path(args.samples_dir)
    images = sorted(p for p in samples_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if args.limit:
        images = images[: args.limit]
    if not images:
        print(f"未找到样本图片：{samples_dir}（见 spikes/samples/README.md）")
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    validator = Draft202012Validator(json.loads(SCHEMA_PATH.read_text()))
    prompt = build_user_prompt(SCHEMA_PATH.read_text())
    provider = make_vision_provider(get_settings(), args.provider)

    print(f"provider={provider.name} model={provider.model} prompt={PROMPT_VERSION} 样本数={len(images)}")
    records: list[dict] = []
    for img in images:
        print(f"  → {img.name} ...", flush=True)
        rec = asyncio.run(run_one(provider, validator, SYSTEM, prompt, img))
        records.append(rec)
        print(f"    {'OK ' if rec['ok'] else 'FAIL'} [{rec['stage']}] {rec.get('failure', '')[:100]}")
        (out_dir / f"{img.stem}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )

    # CSV 汇总
    cols = ["sample", "provider", "model", "ok", "stage", "failureCategory", "failure",
            "wallCount", "doorCount", "windowCount", "roomCount", "scaleRefs",
            "maxScaleDeviationM", "timeS"]
    with (out_dir / "results.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(records)

    ok_count = sum(1 for r in records if r["ok"])
    electronic = [r for r in records if "_electronic" in r["sample"]]
    ok_electronic = sum(1 for r in electronic if r["ok"])
    (out_dir / "report.md").write_text(
        f"# Spike A 报告\n\n"
        f"- 时间：{datetime.now(UTC).isoformat()}\n"
        f"- provider：{provider.name} / {provider.model} / prompt {PROMPT_VERSION}\n"
        f"- 机器校验通过：{ok_count}/{len(records)}\n"
        f"- 电子图（文件名含 _electronic）机器通过：{ok_electronic}/{len(electronic)}\n\n"
        f"> 机器通过 ≠ 结构可用率。结构可用率必须按 spikes/eval/scoring-rubric.md 人工评分。\n"
        f"> 每张样本的原始输出见同目录 <sample>.json（含 raw 字段，可直接导入评审工具）。\n",
        encoding="utf-8",
    )

    print(f"\n机器校验通过 {ok_count}/{len(records)}；产物：{out_dir}")
    return 0 if ok_count > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
