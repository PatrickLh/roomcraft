/** 场景渲染参数集中配置（plans/v1.0.md M1-07 要求；M0 先集中、M1 收敛到设计稿）。 */

export const SCENE_DEFAULTS = {
  /** 层高（米）。Schema 里 meta.floorHeight 缺省时的兜底值。 */
  floorHeight: 2.8,
  /** 第一人称视高（米） */
  walkEyeHeight: 1.6,
  /** 行走速度（米/秒） */
  walkSpeed: 2.4,
  /** 俯视相机距地面的安全范围 */
  topMinDistance: 4,
  topMaxDistance: 60,
  /** 俯视模式的极角上限（弧度）——允许绕竖轴旋转但保持近俯视 */
  topMaxPolarAngle: 0.15,
  /** 视角切换动画时长（毫秒） */
  transitionMs: 900,
  /** 行走时与墙体的最小间距（米，M0 简单钳制，无碰撞检测） */
  walkMargin: 0.3,
} as const

export const COLORS = {
  wall: 0xe9e4da,
  glass: 0x9fc7e8,
  ground: 0xd9dee3,
  grid: 0xc3cad1,
  label: 0x2f3a45,
} as const

/** 房间地面分色（低饱和、相互可区分） */
export const ROOM_FLOOR_PALETTE = [0xd7e3d0, 0xe8dcc8, 0xd3d9e6, 0xe6d3d3, 0xd9e6e2, 0xe3e0cf] as const
