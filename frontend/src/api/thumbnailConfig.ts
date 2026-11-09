// Revision keeps old session responses out of a newly configured desktop API.
let revision = 0
const listeners = new Set<() => void>()
export const thumbnailConfig = {
  snapshot: () => revision,
  subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener) } },
  changed: () => { revision += 1; listeners.forEach((listener) => listener()) },
}
