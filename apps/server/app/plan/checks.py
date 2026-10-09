"""户型数据的语义校验：JSON Schema 表达不了的跨字段约束。

纯函数、无第三方依赖，被三处共用：
- packages/shared-schema/schema_check.py（CI fixture 校验）
- Spike A（spikes/spike_a，识别结果验收）
- M1 识别管线（服务端入库前校验）

浏览器侧由 apps/web/src/scene/semanticChecks.ts 镜像同一套规则；
M1-01 需收敛双端镜像的统一方案（计划 §2 已登记）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

EPS = 1e-6


@dataclass(frozen=True)
class Issue:
    level: str  # "error" | "warning" | "info"
    code: str
    message: str


def _dist(p1: dict, p2: dict) -> float:
    try:
        return math.hypot(float(p2["x"]) - float(p1["x"]), float(p2["y"]) - float(p1["y"]))
    except (KeyError, TypeError, ValueError):
        return 0.0


def _dupes(ids: list, code: str, label: str) -> list[Issue]:
    seen: set = set()
    duped: set = set()
    for i in ids:
        if i in seen:
            duped.add(i)
        seen.add(i)
    if not duped:
        return []
    return [Issue("error", code, f"{label} ID 重复: {sorted(duped)}")]


def check_semantics(plan: dict) -> list[Issue]:
    """返回语义问题列表；仅含 error 级别时视为结构不可用。"""
    issues: list[Issue] = []
    floor_height = float(plan.get("meta", {}).get("floorHeight", 2.8))
    walls = plan.get("walls", [])

    # 1. ID 唯一性
    issues += _dupes([w.get("id") for w in walls], "duplicate_wall_id", "墙体")
    issues += _dupes([r.get("id") for r in plan.get("rooms", [])], "duplicate_room_id", "房间")
    opening_ids: list = []
    for w in walls:
        opening_ids += [o.get("id") for o in w.get("openings", [])]
    issues += _dupes(opening_ids, "duplicate_opening_id", "门窗洞")
    issues += _dupes(
        [s.get("id") for s in plan.get("scale", {}).get("references", [])],
        "duplicate_scale_id",
        "标定",
    )

    # 2. 墙几何与开口范围
    for w in walls:
        wid = w.get("id", "?")
        length = _dist(w.get("p1", {}), w.get("p2", {}))
        if length <= EPS:
            issues.append(Issue("error", "zero_length_wall", f"墙 {wid} 长度为 0"))
            continue
        ops = sorted(w.get("openings", []), key=lambda o: float(o.get("t", 0)))
        for o in ops:
            oid = o.get("id", "?")
            t, width = float(o.get("t", 0)), float(o.get("width", 0))
            sill, height = float(o.get("sill", 0)), float(o.get("height", 0))
            if t + width > length + EPS:
                issues.append(
                    Issue(
                        "error",
                        "opening_out_of_range",
                        f"开口 {oid}（t={t:.3f}+width={width:.3f}）超出墙 {wid} 长度 {length:.3f}",
                    )
                )
            if sill + height > floor_height + EPS:
                issues.append(
                    Issue(
                        "error",
                        "opening_above_ceiling",
                        f"开口 {oid} 顶高 {sill + height:.3f} 超过层高 {floor_height}",
                    )
                )
            if o.get("type") == "door" and sill > EPS:
                issues.append(Issue("warning", "door_with_sill", f"门洞 {oid} 的 sill 应为 0"))
        for a, b in zip(ops, ops[1:], strict=False):
            if float(a.get("t", 0)) + float(a.get("width", 0)) > float(b.get("t", 0)) + EPS:
                issues.append(
                    Issue(
                        "error",
                        "openings_overlap",
                        f"墙 {wid} 上开口 {a.get('id')} 与 {b.get('id')} 重叠",
                    )
                )

    # 3. 比例标定交叉验证（PRD：标注值与几何距离必须一致，否则结构不可信）
    scale = plan.get("scale", {})
    tol = float(scale.get("deviationToleranceM", 0.15))
    for s in scale.get("references", []):
        sid = s.get("id", "?")
        dist = _dist(s.get("p1", {}), s.get("p2", {}))
        if dist <= EPS:
            issues.append(Issue("error", "degenerate_scale_ref", f"标定 {sid} 线段长度为 0"))
            continue
        value = float(s.get("valueM", 0))
        dev = abs(value - dist)
        if dev > tol:
            issues.append(
                Issue(
                    "error",
                    "scale_inconsistent",
                    f"标定 {sid} 标注 {value:.3f}m 与几何距离 {dist:.3f}m 偏差 {dev:.3f}m 超容差 {tol}",
                )
            )

    # 4. 降级特性提示（info 级，供 UI 提示用，不影响可用性）
    for feat in plan.get("meta", {}).get("unsupportedFeatures", []) or []:
        issues.append(Issue("info", "unsupported_feature", f"包含 V1 不支持的特性: {feat}"))

    return issues


def is_usable(issues: list[Issue]) -> bool:
    """结构可用判定：无 error 级问题。"""
    return not any(i.level == "error" for i in issues)
