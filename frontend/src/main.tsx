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
  }
  createRoot(root!).render(<StrictMode><App /></StrictMode>)
}
void mount()
