import { createContext, useContext } from 'react'

export interface DesktopRuntimeValue {
  serviceError: string | null
  retryServices: () => Promise<void>
}

export const DesktopRuntimeContext = createContext<DesktopRuntimeValue>({
  serviceError: null,
  retryServices: async () => {},
})

export function useDesktopRuntime() {
  return useContext(DesktopRuntimeContext)
}
