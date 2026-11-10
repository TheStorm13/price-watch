import { act, cleanup, render } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { useVirtualRows } from './useVirtualRows'

const virtualizer = vi.hoisted(() => ({ measure: vi.fn(), getVirtualItems: () => [] }))
vi.mock('@tanstack/react-virtual', () => ({
  defaultRangeExtractor: () => [],
  useWindowVirtualizer: () => virtualizer,
}))

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

it('avoids scroll layout reads and subpixel churn while tracking controls before the list', () => {
  const frames = new Map<number, FrameRequestCallback>()
  let frameId = 0
  let notify!: ResizeObserverCallback
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { frames.set(++frameId, callback); return frameId })
  vi.stubGlobal('cancelAnimationFrame', (id: number) => frames.delete(id))
  vi.stubGlobal('ResizeObserver', class {
    constructor(callback: ResizeObserverCallback) { notify = callback }
    observe() {}
    disconnect() {}
  })
  let top = 200
  const read = vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(() => ({ top }) as DOMRect)
  const keys = ['one']
  function List({ version, selected = false }: { version: number; selected?: boolean }) {
    const rows = useVirtualRows(keys, 82, undefined, { layoutVersion: selected })
    return <div><aside data-controls /><section><div ref={rows.root} data-version={version}><div data-virtual-start /><output>{rows.margin}</output></div></section></div>
  }
  function flush() {
    act(() => { const pending = [...frames.values()]; frames.clear(); pending.forEach(callback => callback(0)) })
  }
  const result = render(<List version={0} />)
  result.rerender(<List version={1} />)
  result.rerender(<List version={2} />)
  expect(read).not.toHaveBeenCalled()
  expect(frames.size).toBe(1)
  flush()
  expect(read).toHaveBeenCalledTimes(1)
  expect(result.getByRole('status')).toHaveTextContent('200')
  expect(frames.size).toBe(0) // Updating margin must not schedule another read.
  for (let version = 3; version < 100; version++) result.rerender(<List version={version} />)
  expect(frames.size).toBe(0) // Scroll/progress rerenders leave geometry alone.
  const count = read.mock.calls.length
  const target = result.container.querySelector('[data-version]')!
  const resize = (height: number, width = 100) => act(() => notify([
    { target, contentRect: { width, height } } as ResizeObserverEntry,
  ], {} as ResizeObserver))
  resize(1000)
  flush()
  expect(read).toHaveBeenCalledTimes(count + 1)
  resize(5000)
  resize(10000)
  expect(frames.size).toBe(0)
  top = 200.4 // Fractional rect/scroll rounding must not change scrollMargin.
  resize(10000, 110)
  flush()
  expect(result.getByRole('status')).toHaveTextContent('200')
  expect(frames.size).toBe(0)
  top = 260 // Selection controls can move the origin without changing width.
  result.rerender(<List version={100} selected />)
  flush()
  expect(result.getByRole('status')).toHaveTextContent('260')
  top = 340 // Expanding an existing toolbar changes height, not selection.
  act(() => notify([{ target: result.container.querySelector('[data-controls]')!, contentRect: { width: 110, height: 80 } } as ResizeObserverEntry], {} as ResizeObserver))
  flush()
  expect(result.getByRole('status')).toHaveTextContent('340')
  resize(10000, 120)
  expect(frames.size).toBe(1)
  result.unmount()
  expect(frames.size).toBe(0)
})
