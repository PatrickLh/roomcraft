"""CI fixture 校验：同一组 fixtures 的 Python 侧守门。

- fixtures/valid/*.json  → 必须通过 JSON Schema 且语义校验无 error
- fixtures/invalid/*.json → 必须至少在 JSON Schema 或语义校验之一失败

语义校验复用 apps/server/app/plan/checks.py（单一实现），
因此运行依赖 uv workspace 环境（`pnpm schema:check`）。
浏览器侧的镜像校验见 apps/web/src/scene/semanticChecks.ts（vitest 跑同一组 fixtures）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.plan.checks import check_semantics
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent


def _validate(plan: dict, validator: Draft202012Validator) -> list[str]:
    return [f"schema: {e.message}" for e in sorted(validator.iter_errors(plan), key=str)]


def main() -> int:
    validator = Draft202012Validator(json.loads((ROOT / "floor-plan.schema.json").read_text()))
    failures: list[str] = []

    print("== valid fixtures ==")
    for path in sorted((ROOT / "fixtures" / "valid").glob("*.json")):
        plan = json.loads(path.read_text())
        errors = _validate(plan, validator)
        issues = [i for i in check_semantics(plan) if i.level == "error"]
        errors += [f"semantic: {i.message}" for i in issues]
        ok = not errors
        print(f"  {'PASS' if ok else 'FAIL'}  {path.name}")
        failures += [f"{path.name}: {e}" for e in errors]

    print("== invalid fixtures ==")
    for path in sorted((ROOT / "fixtures" / "invalid").glob("*.json")):
        plan = json.loads(path.read_text())
        errors = _validate(plan, validator)
        issues = [i for i in check_semantics(plan) if i.level == "error"]
        errors += [f"semantic: {i.message}" for i in issues]
        caught_by = "jsonschema" if any(e.startswith("schema:") for e in errors) else ""
        if issues and not caught_by:
            caught_by = "semantic"
        if errors:
            print(f"  PASS  {path.name}  (拒绝于 {caught_by}: {errors[0][:80]})")
        else:
            print(f"  FAIL  {path.name}  (预期被拒绝，但两道校验均通过)")
            failures.append(f"{path.name}: 未被拒绝")

    if failures:
        print(f"\n{len(failures)} 个失败：")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\n全部 fixtures 校验通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
