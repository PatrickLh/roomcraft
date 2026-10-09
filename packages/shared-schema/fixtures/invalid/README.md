# invalid fixtures 预期

fixtures 必须保持纯净（根级不允许额外字段，否则违反 `additionalProperties: false`），
每个文件的拒绝预期记录在此：

| 文件 | 预期在哪一道校验被拒绝 | 原因 |
|---|---|---|
| `missing-scale.json` | JSON Schema | 缺 `scale`（PRD：无标注则解析失败，不允许估算） |
| `unsupported-version.json` | JSON Schema | `schemaVersion: "0.2"` 不在允许值内 |
| `opening-out-of-range.json` | **语义校验** | 门窗洞超出墙长（跨字段约束，Schema 表达不了） |
| `duplicate-wall-id.json` | **语义校验** | 墙体 ID 重复（数组内唯一性，Schema 表达不了） |

双端（Python `schema_check.py` / TS vitest）使用同一组文件，任何一端行为不一致即契约漂移。
