import * as THREE from 'three'
import { describe, expect, it } from 'vitest'

import demo from '@roomcraft/shared-schema/fixtures/valid/demo-2br.json'
import type { FloorPlan, Wall } from '@roomcraft/shared-schema'

import { buildWall, planToWorld } from '../scene/wallBuilder'

const plan = demo as unknown as FloorPlan
const FLOOR_H = plan.meta.floorHeight ?? 2.8

function wallMeshes(wall: Wall): THREE.Mesh[] {
  return buildWall(wall, FLOOR_H).children.filter(
    (c): c is THREE.Mesh => c instanceof THREE.Mesh,
  )
}

describe('wallBuilder（墙段 + 门窗洞分解）', () => {
  it('所有墙段都在墙长与层高范围内', () => {
    for (const wall of plan.walls) {
      const len = Math.hypot(wall.p2.x - wall.p1.x, wall.p2.y - wall.p1.y)
      for (const mesh of wallMeshes(wall)) {
        const g = mesh.geometry as THREE.BoxGeometry
        expect(g.parameters.width).toBeLessThanOrEqual(len + 1e-6)
        expect(g.parameters.height).toBeLessThanOrEqual(FLOOR_H + 1e-6)
        expect(mesh.position.y - g.parameters.height / 2).toBeGreaterThanOrEqual(-1e-6)
        expect(mesh.position.y + g.parameters.height / 2).toBeLessThanOrEqual(FLOOR_H + 1e-6)
      }
    }
  })

  it('平面坐标 (x, y) 映射到世界 (x, 0, y)', () => {
    const v = planToWorld({ x: 1.5, y: 2.5 })
    expect(v.x).toBeCloseTo(1.5)
    expect(v.y).toBeCloseTo(0)
    expect(v.z).toBeCloseTo(2.5)
  })

  it('门洞生成过梁与两侧墙段，不留玻璃', () => {
    const wall: Wall = {
      id: 'w-t',
      p1: { x: 0, y: 0 },
      p2: { x: 4, y: 0 },
      thickness: 0.2,
      openings: [{ id: 'o-d', type: 'door', t: 1, width: 0.9, height: 2.05, sill: 0 }],
    }
    const meshes = wallMeshes(wall)
    // 两侧墙段 2 + 过梁 1
    expect(meshes).toHaveLength(3)
    const lintel = meshes.find(
      (m) => Math.abs((m.geometry as THREE.BoxGeometry).parameters.height - (FLOOR_H - 2.05)) < 1e-6,
    )
    expect(lintel).toBeDefined()
    expect(meshes.every((m) => m.userData.kind === 'wall')).toBe(true)
  })

  it('窗洞生成玻璃板，全屋玻璃数等于窗数', () => {
    const allMeshes = plan.walls.flatMap(wallMeshes)
    const glass = allMeshes.filter((m) => m.userData.kind === 'glass')
    const windowCount = plan.walls.flatMap((w) => w.openings).filter((o) => o.type === 'window').length
    expect(glass.length).toBe(windowCount)

    // 玻璃高度 = 窗高，中心 = sill + 窗高/2（抽验第一面北墙的窗）
    const north = plan.walls.find((w) => w.id === 'w-north')!
    const northWin = north.openings.find((o) => o.type === 'window')!
    const g = glass[0].geometry as THREE.BoxGeometry
    expect(g.parameters.height).toBeCloseTo(northWin.height)
  })

  it('墙 Group 定位于墙轴中点并朝向墙轴', () => {
    const wall: Wall = {
      id: 'w-rot',
      p1: { x: 0, y: 0 },
      p2: { x: 0, y: 6 },
      thickness: 0.2,
      openings: [],
    }
    const group = buildWall(wall, FLOOR_H)
    expect(group.position.x).toBeCloseTo(0)
    expect(group.position.z).toBeCloseTo(3)
    expect(group.userData.length).toBeCloseTo(6)
  })
})
