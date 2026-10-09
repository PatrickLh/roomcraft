/** 场景渲染参数集中配置（plans/v1.0.md M1-07 要求；M0 先集中、M1 收敛到设计稿）。 */

export const SCENE_DEFAULTS = {
  /** 层高（米）。Schema 里 meta.floorHeight 缺省时的兜底值。 */
  floorHeight: 2.8,
  /** 第一人称视高（米） */
  walkEyeHeight: 1.6,
  /** 行走视场角（度）。室内空间感需要广角，窄 fov 会显得贴墙、物体过大 */
  walkFov: 68,
  /** 进入行走时的初始俯仰（度，略微向下看地面/家具） */
  walkInitialPitchDeg: -8,
  /** 行走速度（米/秒） */
  walkSpeed: 2.4,
  /** 俯视（轨道）相机默认参数 */
  /** 默认俯角（度）：从上往下 45°，用户可自行转动 */
  topDefaultPolarDeg: 45,
  /** 轨道半径（正交相机远置，避免裁切） */
  topRadius: 60,
  /** 极角范围（弧度）：允许从近俯视扫到近水平 */
  topMinPolarAngle: 0.1,
  topMaxPolarAngle: 1.45,
  /** 轨道距离范围 */
  topMinDistance: 6,
  topMaxDistance: 150,
  /** 视锥适配边距（投影包围盒后预留） */
  topFitMargin: 1.2,
  /** 视角切换动画时长（毫秒） */
  transitionMs: 900,
  /** 行走时与墙体的最小间距（米，M0 简单钳制，无碰撞检测） */
  walkMargin: 0.3,
} as const

export const COLORS = {
  /** 墙侧边（行走视角看到的内墙面） */
  wall: 0xe9e4da,
  /** 墙顶（俯视时的墙体截面，建筑图纸惯例用深色保证可读性） */
  wallTop: 0x566068,
  glass: 0x9fc7e8,
  ground: 0xd9dee3,
  grid: 0xc3cad1,
  label: 0x2f3a45,
} as const

/** 房间地面分色（低饱和、相互可区分） */
export const ROOM_FLOOR_PALETTE = [0xd7e3d0, 0xe8dcc8, 0xd3d9e6, 0xe6d3d3, 0xd9e6e2, 0xe3e0cf] as const
