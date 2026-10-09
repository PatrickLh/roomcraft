# RoomCraft

上传户型图 → AI 结构化解析 → 确定性生成可编辑 3D 户型 → 俯视编辑家具 / 3D 实时观察 → 风格参考图生成效果图。

- 需求与决策：[`docs/v1.0.md`](docs/v1.0.md)
- 执行计划：[`plans/v1.0.md`](plans/v1.0.md)（当前阶段：**M0 验证关键不确定性**）

## 仓库结构

```
apps/web               Vue 3 + TS + Vite + Pinia + Three.js（M0：假户型双视角原型）
apps/server            FastAPI + Pydantic（AI Provider 适配层 / AI 标识模块 / 语义校验）
packages/shared-schema 户型 JSON Schema（唯一事实源）+ fixtures + 双端校验
spikes/spike_a         视觉大模型户型识别验证脚本
spikes/spike_b         参考图生图验证脚本（产物强制带 AI 标识）
spikes/samples         样本规范 + 合成冒烟样本（真实样本见其 README）
spikes/eval            人工评分规程
```

## 快速开始

依赖：Node ≥ 22、pnpm ≥ 10、Python ≥ 3.12、[uv](https://docs.astral.sh/uv/)。

```bash
pnpm install                # 前端依赖
uv sync --all-packages      # Python workspace（根目录单一 .venv）
cp .env.example .env        # 配置 AI Provider（密钥仅存后端）
pnpm samples:synth          # 生成合成冒烟样本（可选）
```

## 常用命令

| 命令 | 说明 |
|---|---|
| `pnpm dev:web` | 启动前端原型（俯视/行走双视角） |
| `pnpm build:web` / `pnpm typecheck:web` / `pnpm test:web` | 构建 / 类型检查 / vitest |
| `pnpm server:dev` | 启动后端（:8787，/api/health、/api/providers） |
| `pnpm server:test` / `pnpm server:lint` | pytest / ruff |
| `pnpm schema:check` | Python 侧校验全部 fixtures |
| `pnpm schema:codegen` | Schema → TS 类型（提交产物，CI 校验无漂移） |
| `pnpm schema:codegen:py` | Schema → Pydantic 模型（M1 接入） |
| `pnpm spike:a` / `pnpm spike:b` / `pnpm spike:smoke` | Spike 验证 / mock 冒烟 |

## Spike 真实验证（M0 核心）

1. 按 `spikes/samples/README.md` 收集 ≥ 10 张获授权真实户型图；
2. `.env` 配置视觉大模型与生图 API（见 `.env.example`）；
3. `pnpm spike:a` → 按 `spikes/eval/scoring-rubric.md` 人工评分（电子图可用率目标 ≥ 80%）；
4. `pnpm dev:web` → 「导出截图」得到场景图 → `pnpm spike:b -- --scene <截图> --style <风格图>`
   → 人工评分（主观可用率目标 ≥ 60%）；
5. 全部结果与成本记录进 `spikes/reports/`，按 plans/v1.0.md M0-06 评审后决定推进或调整。

## 环境约束（PRD 已定，开发时遵守）

- 密钥只存在于后端环境变量，绝不进浏览器与仓库；
- 户型 JSON Schema 是唯一事实源，双端类型均由它生成；
- AI 生成的所有对外产物必须带显式水印 + 隐式元数据标识；
- 家具真实尺寸不开放自由缩放；mock provider 只能验证管线，不能替代真实 API 验证。
