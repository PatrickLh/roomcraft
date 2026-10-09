import schema from './floor-plan.schema.json'

export type {
  FloorPlan,
  Opening,
  Point2,
  Room,
  Scale,
  ScaleReference,
  Wall,
} from './generated/floor-plan'

export { schema }

export const SCHEMA_VERSION = '0.1' as const
