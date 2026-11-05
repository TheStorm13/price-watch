import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './app/App'
import './styles/global.css'

const root = document.getElementById('root')
if (!root) throw new Error('Не найден корневой элемент #root')

async function mount() {
  if (import.meta.env.VITE_E2E_TEST_MODE === 'true') {
    const { installPerformanceFixture } = await import('./test/performanceFixture')
    installPerformanceFixture()
    if (import.meta.env.DEV && import.meta.env.VITE_DESKTOP_MODE !== 'true' && (
      import.meta.env.VITE_SIDEBAR_DEMO === 'true' || new URLSearchParams(location.search).get('sidebar') === '2'
    ) && !new URLSearchParams(location.search).has('perf')) {
      const { installPreviewFixture } = await import('./features/sidebar-demo/previewFixture')
      await installPreviewFixture()
    }
  }
  createRoot(root!).render(<StrictMode><App /></StrictMode>)
}
void mount()
