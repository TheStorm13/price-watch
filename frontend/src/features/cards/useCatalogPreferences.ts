import { useCallback, useLayoutEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { catalogPreferenceSearch, hasCatalogPreferences, readCatalogPreferences, writeCatalogPreferences } from './catalogPreferences'

/** Restore once on first catalog entry; subsequent blank URLs represent an intentional reset. */
export function useCatalogPreferences() {
  const location = useLocation()
  const visitedCatalog = useRef(false)
  const [savedSearch] = useState(() => readCatalogPreferences().catalogSearch)
  const params = new URLSearchParams(location.search)
  let restoreTo: string | null = null
  if (location.pathname === '/cards' && !visitedCatalog.current && !hasCatalogPreferences(params) && savedSearch) {
    for (const [key, value] of new URLSearchParams(savedSearch)) params.append(key, value)
    restoreTo = `${location.pathname}?${params}${location.hash}`
  }

  useLayoutEffect(() => {
    if (location.pathname !== '/cards') return
    visitedCatalog.current = true
    if (!restoreTo) writeCatalogPreferences({ catalogSearch: catalogPreferenceSearch(new URLSearchParams(location.search)) })
  }, [location.pathname, location.search, restoreTo])

  const rememberSearch = useCallback((next: URLSearchParams) => {
    visitedCatalog.current = true
    writeCatalogPreferences({ catalogSearch: catalogPreferenceSearch(next) })
  }, [])

  return { restoreTo, savedSearch, rememberSearch }
}
