import '@testing-library/jest-dom/vitest'

// JSDOM has no layout observer; Radix uses it to size hidden form controls.
import { vi } from 'vitest'
vi.stubGlobal('ResizeObserver', class {
  observe() {}
  unobserve() {}
  disconnect() {}
})
