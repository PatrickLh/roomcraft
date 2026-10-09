"""生成合成冒烟样本 000_synth_smoke_electronic.png（数据源：demo-2br fixture）。

仅用于 Spike 管线冒烟，不代表真实样本。运行：pnpm samples:synth
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "packages" / "shared-schema" / "fixtures" / "valid" / "demo-2br.json"

SCALE = 60  # px / m
MARGIN = 90


CJK_FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",  # macOS
    "/System/Library/Fonts/STHeiti Light.ttc",  # macOS
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Debian/Ubuntu
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",  # Arch
]


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in CJK_FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def main() -> None:
    plan = json.loads(FIXTURE.read_text())
    # 画布按户型范围 + 边距（供尺寸标注用）
    xs = [p["x"] for w in plan["walls"] for p in (w["p1"], w["p2"])]
    ys = [p["y"] for w in plan["walls"] for p in (w["p1"], w["p2"])]
    W = int((max(xs) - min(xs)) * SCALE) + MARGIN * 2
    H = int((max(ys) - min(ys)) * SCALE) + MARGIN * 2
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f = font(22)

    def pt(p: dict) -> tuple[float, float]:
        return (MARGIN + (p["x"] - min(xs)) * SCALE, MARGIN + (p["y"] - min(ys)) * SCALE)

    # 墙（中心线粗线）
    for w in plan["walls"]:
        d.line([pt(w["p1"]), pt(w["p2"])], fill="black", width=max(3, int(w["thickness"] * SCALE)))

    # 门窗洞：白色挖空 + 符号
    for w in plan["walls"]:
        p1, p2 = pt(w["p1"]), pt(w["p2"])
        horizontal = abs(p1[1] - p2[1]) < 1e-6
        for o in w["openings"]:
            a = min(o["t"], o["t"] + o["width"])
            b = max(o["t"], o["t"] + o["width"])
            if horizontal:
                x0 = min(p1[0], p2[0]) + a * SCALE
                x1 = min(p1[0], p2[0]) + b * SCALE
                y_mid = p1[1]
                half = max(4, w["thickness"] * SCALE / 2 + 2)
                d.rectangle([x0, y_mid - half, x1, y_mid + half], fill="white")
                if o["type"] == "window":
                    for off in (-4, 0, 4):
                        d.line([(x0, y_mid + off), (x1, y_mid + off)], fill=(60, 90, 160), width=2)
                else:
                    for xx in (x0, x1):
                        d.line([(xx, y_mid - half), (xx, y_mid + half)], fill="black", width=3)
            else:
                y0 = min(p1[1], p2[1]) + a * SCALE
                y1 = min(p1[1], p2[1]) + b * SCALE
                x_mid = p1[0]
                half = max(4, w["thickness"] * SCALE / 2 + 2)
                d.rectangle([x_mid - half, y0, x_mid + half, y1], fill="white")
                if o["type"] == "window":
                    for off in (-4, 0, 4):
                        d.line([(x_mid + off, y0), (x_mid + off, y1)], fill=(60, 90, 160), width=2)
                else:
                    for yy in (y0, y1):
                        d.line([(x_mid - half, yy), (x_mid + half, yy)], fill="black", width=3)

    # 房间名
    for r in plan["rooms"]:
        pos = r.get("labelPosition")
        if not pos:
            continue
        x, y = pt(pos)
        text = r["name"]
        tw = d.textlength(text, font=f)
        d.text((x - tw / 2, y - 14), text, fill=(180, 40, 40), font=f)

    # 尺寸标注（毫米，如 "10200"）
    for s in plan["scale"]["references"]:
        p1, p2 = pt(s["p1"]), pt(s["p2"])
        mm = f"{int(s['valueM'] * 1000)}"
        horizontal = abs(p1[1] - p2[1]) < 1e-6
        if horizontal:
            mx = (p1[0] + p2[0]) / 2
            y = min(p1[1], p2[1]) - 30
            d.line([p1, p2], fill=(90, 90, 90), width=1)
            tw = d.textlength(mm, font=f)
            d.text((mx - tw / 2, y - 26), mm, fill=(90, 90, 90), font=f)
        else:
            my = (p1[1] + p2[1]) / 2
            x = max(p1[0], p2[0]) + 8
            d.line([p1, p2], fill=(90, 90, 90), width=1)
            d.text((x, my - 12), mm, fill=(90, 90, 90), font=f)

    out = Path(__file__).parent / "000_synth_smoke_electronic.png"
    img.save(out)
    sidecar = Path(__file__).parent / "000_synth_smoke_electronic.yaml"
    sidecar.write_text(
        "source: \"合成样本（make_synthetic.py，不计入真实样本）\"\n"
        f"has_annotation: true\n"
        f"expected_rooms: {len(plan['rooms'])}\n"
        "notes: \"仅用于 mock 冒烟验证脚本链路\"\n",
        encoding="utf-8",
    )
    print(f"已生成 {out.name} + sidecar")


if __name__ == "__main__":
    main()
