import { parseColumnSort } from './catalogItems'
import { readMarketplaces, readSelection } from './catalogModel'

export const catalogPreferencesKey = `price-watch-catalog-preferences:${import.meta.env.VITE_E2E_TEST_MODE === 'true' ? 'demo' : 'desktop'}`
const searchKeys = ['q', 'markets', 'tags', 'stock', 'deals', 'participationFirst', 'sort', 'view'] as const

interface CatalogPreferences {
  version: 1
  catalogSearch: string
  collapsedGroupIds: number[]
}

export function hasCatalogPreferences(params: URLSearchParams) {
  return searchKeys.some((key) => params.has(key))
}

/** Store display options only, preserving search text and the empty tag selection. */
export function catalogPreferenceSearch(params: URLSearchParams) {
  const next = new URLSearchParams()
  const query = params.get('q')
  if (query) next.set('q', query)
  const markets = readMarketplaces(params)
  if (markets) for (const market of markets) next.append('markets', market)
  const tags = readSelection(params, 'tags')
  if (tags !== null) for (const tag of tags.length ? tags : ['']) next.append('tags', tag)
  if (params.get('stock') === '1') next.set('stock', '1')
  if (params.get('participationFirst') === '0') next.set('participationFirst', '0')
  const deals = params.get('deals')
  if (deals === 'deals' || deals === 'non_deals' || deals === 'participating') next.set('deals', deals)
  const sort = params.get('sort')
  if (parseColumnSort(sort)) next.set('sort', sort!)
  if (params.get('view') === 'grid') next.set('view', 'grid')
  return next.toString()
}

export function readCatalogPreferences(): CatalogPreferences {
  const defaults: CatalogPreferences = { version: 1, catalogSearch: '', collapsedGroupIds: [] }
  try {
    const value: unknown = JSON.parse(localStorage.getItem(catalogPreferencesKey) ?? 'null')
    if (!value || typeof value !== 'object' || !('version' in value) || value.version !== 1) return defaults
    const saved = value as Partial<CatalogPreferences>
    return {
      version: 1,
      catalogSearch: typeof saved.catalogSearch === 'string' ? catalogPreferenceSearch(new URLSearchParams(saved.catalogSearch)) : '',
      collapsedGroupIds: Array.isArray(saved.collapsedGroupIds)
        ? [...new Set(saved.collapsedGroupIds.filter((id) => Number.isSafeInteger(id) && id > 0))] : [],
    }
  } catch {
    return defaults
  }
}

export function writeCatalogPreferences(patch: Partial<Omit<CatalogPreferences, 'version'>>) {
  try {
    localStorage.setItem(catalogPreferencesKey, JSON.stringify({ ...readCatalogPreferences(), ...patch }))
  } catch {
    // Private/restricted storage and quota errors must not prevent using the catalog.
  }
}
