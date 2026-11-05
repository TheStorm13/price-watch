import { createContext, useContext, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

type SlotName = 'filters' | 'group'

export const SidebarDemoContext = createContext<Partial<Record<SlotName, HTMLElement | null>> | null>(null)

/** Keep catalog state and handlers in CardsPage while comparing control placement. */
export function SidebarDemoSlot({ name, children }: { name: SlotName; children: ReactNode }) {
  const slots = useContext(SidebarDemoContext)
  const target = slots?.[name]
  return target ? createPortal(children, target) : children
}

export function useSidebarDemo() {
  return useContext(SidebarDemoContext) !== null
}
