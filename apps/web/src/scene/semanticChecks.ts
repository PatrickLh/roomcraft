/** 语义校验的浏览器侧镜像（规则同 apps/server/app/plan/checks.py）。 */

import type { FloorPlan } from '@roomcraft/shared-schema'

export interface Issue {
  level: 'error' | 'warning' | 'info'
  code: string
  message: string
}

const EPS = 1e-6

function dist(p1: { x: number; y: number }, p2: { x: number; y: number }): number {
  return Math.hypot(p2.x - p1.x, p2.y - p1.y)
}

function dupes(ids: (string | undefined)[], code: string, label: string): Issue[] {
  const seen = new Set<string>()
  const duped = new Set<string>()
  for (const id of ids) {
    if (id === undefined) continue
    if (seen.has(id)) duped.add(id)
    seen.add(id)
  }
  if (duped.size === 0) return []
  return [{ level: 'error', code, message: `${label} ID 重复: ${[...duped].sort().join(', ')}` }]
}

export function checkSemantics(plan: FloorPlan): Issue[] {
  const issues: Issue[] = []
  const floorHeight = plan.meta.floorHeight ?? 2.8
  const walls = plan.walls

  issues.push(...dupes(walls.map((w) => w.id), 'duplicate_wall_id', '墙体'))
  issues.push(...dupes(plan.rooms.map((r) => r.id), 'duplicate_room_id', '房间'))
  issues.push(
    ...dupes(walls.flatMap((w) => w.openings.map((o) => o.id)), 'duplicate_opening_id', '门窗洞'),
  )
  issues.push(
    ...dupes((plan.scale.references ?? []).map((s) => s.id), 'duplicate_scale_id', '标定'),
  )

  for (const wall of walls) {
    const length = dist(wall.p1, wall.p2)
    if (length <= EPS) {
      issues.push({ level: 'error', code: 'zero_length_wall', message: `墙 ${wall.id} 长度为 0` })
      continue
    }
    const ops = [...wall.openings].sort((a, b) => a.t - b.t)
    for (const o of ops) {
      if (o.t + o.width > length + EPS) {
        issues.push({
          level: 'error',
          code: 'opening_out_of_range',
          message: `开口 ${o.id}（t=${o.t.toFixed(3)}+width=${o.width.toFixed(3)}）超出墙 ${wall.id} 长度 ${length.toFixed(3)}`,
        })
      }
      if (o.sill + o.height > floorHeight + EPS) {
        issues.push({
          level: 'error',
          code: 'opening_above_ceiling',
          message: `开口 ${o.id} 顶高 ${(o.sill + o.height).toFixed(3)} 超过层高 ${floorHeight}`,
        })
      }
      if (o.type === 'door' && o.sill > EPS) {
        issues.push({ level: 'warning', code: 'door_with_sill', message: `门洞 ${o.id} 的 sill 应为 0` })
      }
    }
    for (let i = 1; i < ops.length; i++) {
      if (ops[i - 1].t + ops[i - 1].width > ops[i].t + EPS) {
        issues.push({
          level: 'error',
          code: 'openings_overlap',
          message: `墙 ${wall.id} 上开口 ${ops[i - 1].id} 与 ${ops[i].id} 重叠`,
        })
      }
    }
  }

  const tol = plan.scale.deviationToleranceM ?? 0.15
  for (const s of plan.scale.references ?? []) {
    const d = dist(s.p1, s.p2)
    if (d <= EPS) {
      issues.push({ level: 'error', code: 'degenerate_scale_ref', message: `标定 ${s.id} 线段长度为 0` })
      continue
    }
    const dev = Math.abs(s.valueM - d)
    if (dev > tol) {
      issues.push({
        level: 'error',
        code: 'scale_inconsistent',
        message: `标定 ${s.id} 标注 ${s.valueM.toFixed(3)}m 与几何距离 ${d.toFixed(3)}m 偏差 ${dev.toFixed(3)}m 超容差 ${tol}`,
      })
    }
  }

  for (const feat of plan.meta.unsupportedFeatures ?? []) {
    issues.push({ level: 'info', code: 'unsupported_feature', message: `包含 V1 不支持的特性: ${feat}` })
  }

  return issues
}

export function isUsable(issues: Issue[]): boolean {
  return !issues.some((i) => i.level === 'error')
}
