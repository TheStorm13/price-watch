import { useSyncExternalStore } from 'react'

const listeners = new Set<() => void>()
let media: MediaQueryList | undefined

function snapshot() {
  return Math.max(0.25, Math.min(8, window.devicePixelRatio || 1))
}

function changed() {
  media?.removeEventListener('change', changed)
  media = window.matchMedia?.(`(resolution: ${window.devicePixelRatio || 1}dppx)`)
  media?.addEventListener('change', changed)
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  if (listeners.size === 1) {
    changed()
    window.addEventListener('resize', changed)
  }
  return () => {
    listeners.delete(listener)
    if (!listeners.size) {
      media?.removeEventListener('change', changed)
      media = undefined
      window.removeEventListener('resize', changed)
    }
  }
}

export function useThumbnailScale() {
  return useSyncExternalStore(subscribe, snapshot)
}
