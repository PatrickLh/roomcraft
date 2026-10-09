import { defineStore } from 'pinia'

export type ViewMode = 'top' | 'walk' | 'transition'

interface AppState {
  viewMode: ViewMode
  planError: string | null
  planName: string
}

export const useAppStore = defineStore('app', {
  state: (): AppState => ({
    viewMode: 'top',
    planError: null,
    planName: '',
  }),
})
