import { createContext, useContext } from 'react'

export const CatalogActionsContext = createContext<{ openAdd: () => void } | null>(null)

export function useCatalogActions() {
  const actions = useContext(CatalogActionsContext)
  if (!actions) throw new Error('CatalogActionsContext is required')
  return actions
}
