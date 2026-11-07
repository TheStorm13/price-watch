import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { catalogPreferenceSearch, catalogPreferencesKey, readCatalogPreferences, writeCatalogPreferences } from './catalogPreferences'

beforeEach(() => localStorage.clear())
afterEach(() => vi.restoreAllMocks())

it('round-trips every display option without navigation/test parameters or changes to search text', () => {
  const search = 'q=My+Товар+&markets=ozon&markets=wildberries&tags=Дом&tags=Техника&stock=1&deals=participating&participationFirst=0&sort=minimum-desc&view=grid'
  writeCatalogPreferences({ catalogSearch: catalogPreferenceSearch(new URLSearchParams(`${search}&fixture=large&page=3`)) })
  writeCatalogPreferences({ collapsedGroupIds: [1, 5] })
  const saved = readCatalogPreferences()
  const params = new URLSearchParams(saved.catalogSearch)
  expect(params.get('q')).toBe('My Товар ')
  expect(params.getAll('markets')).toEqual(['ozon', 'wildberries'])
  expect(params.getAll('tags')).toEqual(['Дом', 'Техника'])
  for (const key of ['stock', 'deals', 'participationFirst', 'sort', 'view']) {
    expect(params.get(key)).toBe(new URLSearchParams(search).get(key))
  }
  expect(params.has('fixture')).toBe(false)
  expect(params.has('page')).toBe(false)
  expect(saved.collapsedGroupIds).toEqual([1, 5])
  expect(saved.version).toBe(1)
})

it('distinguishes all tags from no tags and discards invalid options', () => {
  expect(catalogPreferenceSearch(new URLSearchParams('tags='))).toBe('tags=')
  expect(catalogPreferenceSearch(new URLSearchParams('sort=nope&view=nope&stock=0&deals=nope&participationFirst=1&markets=nope'))).toBe('')
  expect(catalogPreferenceSearch(new URLSearchParams())).toBe('')
})

it.each(['broken json', 'null', '[]', '{"version":2,"catalogSearch":"stock=1"}'])(
  'uses defaults for malformed/unsupported stored data: %s', (value) => {
    localStorage.setItem(catalogPreferencesKey, value)
    expect(readCatalogPreferences()).toEqual({ version: 1, catalogSearch: '', collapsedGroupIds: [] })
  },
)

it('validates fields and group IDs independently', () => {
  localStorage.setItem(catalogPreferencesKey, JSON.stringify({ version: 1, catalogSearch: 42, collapsedGroupIds: [1, 1, -1, 0, 2.3, '3', null, {}, Number.MAX_SAFE_INTEGER + 1, 7] }))
  expect(readCatalogPreferences()).toEqual({ version: 1, catalogSearch: '', collapsedGroupIds: [1, 7] })
})

it('survives denied reads and quota errors', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('denied') })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('quota') })
  expect(readCatalogPreferences().catalogSearch).toBe('')
  expect(() => writeCatalogPreferences({ catalogSearch: 'stock=1' })).not.toThrow()
})

it('keeps desktop preferences separate from demo preferences', () => {
  expect(catalogPreferencesKey).toBe('price-watch-catalog-preferences:desktop')
  localStorage.setItem('price-watch-catalog-preferences:demo', JSON.stringify({ version: 1, catalogSearch: 'stock=1', collapsedGroupIds: [42] }))
  expect(readCatalogPreferences().collapsedGroupIds).toEqual([])
  expect(readCatalogPreferences().catalogSearch).toBe('')
})
