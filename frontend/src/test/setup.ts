import '@testing-library/jest-dom/vitest'

// JSDOM has no layout observer; Radix uses it to size hidden form controls.
import { vi } from 'vitest'
vi.stubGlobal('ResizeObserver', class {
  observe() {}
  unobserve() {}
  disconnect() {}
})

// JSDOM omits pointer capture and scrolling used by Radix Select.
HTMLElement.prototype.hasPointerCapture = () => false
HTMLElement.prototype.setPointerCapture = () => {}
HTMLElement.prototype.releasePointerCapture = () => {}
HTMLElement.prototype.scrollIntoView = () => {}
