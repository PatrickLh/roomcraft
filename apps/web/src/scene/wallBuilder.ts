/** 墙体参数化建模：墙段 + 门窗洞分解 + 窗玻璃。

坐标约定（与 Schema 一致）：平面 (x, y) → Three.js 世界 (x, 0, y)，Y 轴向上。
墙以中心线 (p1→p2) 定位，局部 +X 沿墙轴方向。
*/

import * as THREE from 'three'
import type { Opening, Wall } from '@roomcraft/shared-schema'

import { COLORS, SCENE_DEFAULTS } from './config'

export function planToWorld(p: { x: number; y: number }): THREE.Vector3 {
  return new THREE.Vector3(p.x, 0, p.y)
}

const WALL_SIDE_MATERIAL = new THREE.MeshStandardMaterial({ color: COLORS.wall, roughness: 0.95 })
const WALL_TOP_MATERIAL = new THREE.MeshStandardMaterial({ color: COLORS.wallTop, roughness: 0.9 })
// BoxGeometry 面序：+x, -x, +y, -y, +z, -z —— 顶面（+y）用深色，俯视时墙体清晰可读
const WALL_MATERIALS = [
  WALL_SIDE_MATERIAL,
  WALL_SIDE_MATERIAL,
  WALL_TOP_MATERIAL,
  WALL_SIDE_MATERIAL,
  WALL_SIDE_MATERIAL,
  WALL_SIDE_MATERIAL,
]
const GLASS_MATERIAL = new THREE.MeshStandardMaterial({
  color: COLORS.glass,
  roughness: 0.15,
  metalness: 0.1,
  transparent: true,
  opacity: 0.38,
})

function addBox(
  group: THREE.Group,
  x0: number,
  x1: number,
  y0: number,
  y1: number,
  thickness: number,
  kind: 'wall' | 'glass',
): void {
  const geometry = new THREE.BoxGeometry(Math.max(x1 - x0, 1e-4), Math.max(y1 - y0, 1e-4), kind === 'glass' ? thickness * 0.15 : thickness)
  const material = kind === 'glass' ? GLASS_MATERIAL : WALL_MATERIALS
  const mesh = new THREE.Mesh(geometry, material)
  mesh.position.set((x0 + x1) / 2, (y0 + y1) / 2, 0)
  mesh.userData = { kind }
  group.add(mesh)
}

/** 把一面墙（含开口）构建为一个 Group：不透明墙段 + 门洞留空 + 窗玻璃。

Group 定位在墙起点 p1，局部 +X 沿墙轴指向 p2；盒段用 0..L 局部坐标构建。
注意：不能定位在中点——盒段原点在墙起点，中点定位会整体偏移 L/2（已由回归测试守护）。
*/
export function buildWall(wall: Wall, floorHeight: number = SCENE_DEFAULTS.floorHeight): THREE.Group {
  const p1 = planToWorld(wall.p1)
  const p2 = planToWorld(wall.p2)
  const length = p1.distanceTo(p2)

  const group = new THREE.Group()
  group.userData = { wallId: wall.id, length }
  group.position.copy(p1)
  group.rotation.y = -Math.atan2(p2.z - p1.z, p2.x - p1.x)

  const ops: Opening[] = [...wall.openings].sort((a, b) => a.t - b.t)
  let cursor = 0
  for (const op of ops) {
    // 防御性钳制：语义校验已保证开口在墙内，这里避免脏数据导致几何外溢
    const start = Math.min(op.t, length)
    const end = Math.min(op.t + op.width, length)
    if (start > cursor) addBox(group, cursor, start, 0, floorHeight, wall.thickness, 'wall')
    if (op.sill > 0) addBox(group, start, end, 0, op.sill, wall.thickness, 'wall')
    const lintelTop = Math.min(op.sill + op.height, floorHeight)
    if (lintelTop < floorHeight) addBox(group, start, end, lintelTop, floorHeight, wall.thickness, 'wall')
    if (op.type === 'window') addBox(group, start, end, op.sill, op.sill + op.height, wall.thickness, 'glass')
    cursor = end
  }
  if (cursor < length) addBox(group, cursor, length, 0, floorHeight, wall.thickness, 'wall')
  return group
}
