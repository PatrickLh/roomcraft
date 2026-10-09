import * as THREE from 'three'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ViewRig } from '../scene/viewRig'

// Minimal DOM listener harness; camera math and OrbitControls run unmocked.
class CanvasStub {
  style = { touchAction: '' }
  clientWidth = 900
  clientHeight = 600
  root = new EventTarget()
  listeners: Array<{ type: string; fn: EventListener; capture: boolean }> = []
  getRootNode(): EventTarget { return this.root }
  addEventListener(type: string, fn: EventListener, options?: boolean | AddEventListenerOptions): void {
    this.listeners.push({ type, fn, capture: typeof options === 'boolean' ? options : !!options?.capture })
  }
  removeEventListener(type: string, fn: EventListener): void {
    this.listeners = this.listeners.filter(l => l.type !== type || l.fn !== fn)
  }
  wheel(deltaX: number, deltaY: number, ctrlKey = false, deltaMode = 0): void {
    let stopped = false
    const event = { deltaX, deltaY, ctrlKey, deltaMode, preventDefault() {}, stopImmediatePropagation() { stopped = true } }
    const listeners = this.listeners.filter(l => l.type === 'wheel').sort((a, b) => Number(b.capture) - Number(a.capture))
    for (const l of listeners) {
      l.fn(event as unknown as Event)
      if (stopped) break
    }
  }
}

const rigs: ViewRig[] = []
function setup(w = 900, h = 600): { rig: ViewRig; dom: CanvasStub; box: THREE.Box3 } {
  vi.stubGlobal('window', new EventTarget())
  const dom = new CanvasStub()
  const box = new THREE.Box3(new THREE.Vector3(100, 0, 200), new THREE.Vector3(110.2, 2.8, 208.4))
  const rig = new ViewRig(dom as unknown as HTMLElement, box, { pos: new THREE.Vector3(102.4, 1.6, 202), yaw: -Math.PI / 2 })
  rigs.push(rig)
  rig.resize(w, h)
  return { rig, dom, box }
}

function project(point: THREE.Vector3, camera: THREE.Camera): THREE.Vector3 {
  camera.updateMatrixWorld(true)
  return point.clone().project(camera)
}

afterEach(() => {
  rigs.splice(0).forEach(r => r.dispose())
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('ViewRig viewport and interaction regressions', () => {
  it.each([[900, 600], [400, 800], [1600, 500]])('fits all building corners at %sx%s', (w, h) => {
    const { rig, box } = setup(w, h)
    for (const x of [box.min.x, box.max.x]) for (const y of [box.min.y, box.max.y]) for (const z of [box.min.z, box.max.z]) {
      const p = project(new THREE.Vector3(x, y, z), rig.activeCamera)
      expect(Math.abs(p.x)).toBeLessThan(1)
      expect(Math.abs(p.y)).toBeLessThan(1)
      expect(Math.abs(p.z)).toBeLessThan(1)
    }
  })

  it('restores framing after zoom and pan, and ignores zero sized layouts', () => {
    const { rig, dom, box } = setup()
    dom.wheel(0, -80, true)
    dom.wheel(100, 80)
    rig.resize(0, 0)
    rig.resetTopView()
    expect(rig.orthoCamera.zoom).toBe(1)
    const p = project(box.getCenter(new THREE.Vector3()), rig.activeCamera)
    expect(p.x).toBeCloseTo(0)
    expect(p.y).toBeCloseTo(0)
  })

  it('keeps two-finger pan displacement equal to screen pixels at a tilted angle', () => {
    const { rig, dom, box } = setup()
    const point = box.getCenter(new THREE.Vector3())
    const before = project(point, rig.activeCamera)
    dom.wheel(30, 45)
    rig.update(0.016)
    const after = project(point, rig.activeCamera)
    expect((after.x - before.x) * 900 / 2).toBeCloseTo(30)
    expect((after.y - before.y) * -600 / 2).toBeCloseTo(45)
  })

  it('applies gentle bounded pinch zoom without OrbitControls amplification', () => {
    const { rig, dom } = setup()
    dom.wheel(0, -2, true)
    expect(rig.orthoCamera.zoom).toBeCloseTo(Math.exp(0.02))
    dom.wheel(0, -10000, true)
    expect(rig.orthoCamera.zoom).toBe(8)
    dom.wheel(0, 10000, true)
    expect(rig.orthoCamera.zoom).toBe(0.2)
  })

  it('renders the perspective camera throughout transitions and returns to orthographic', async () => {
    const { rig } = setup()
    let now = 1000
    vi.spyOn(performance, 'now').mockImplementation(() => now)
    const enter = rig.enterWalk()
    expect(rig.mode).toBe('transition')
    expect(rig.activeCamera).toBe(rig.perspCamera)
    now += 1000
    rig.update(0.016)
    await enter
    expect(rig.mode).toBe('walk')
    expect(rig.perspCamera.position.y).toBeCloseTo(1.6)
    const exit = rig.exitWalk()
    expect(rig.activeCamera).toBe(rig.perspCamera)
    now += 1000
    rig.update(0.016)
    await exit
    expect(rig.mode).toBe('top')
    expect(rig.activeCamera).toBe(rig.orthoCamera)
  })
})
