import { useEffect, useState } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { Settings2 } from 'lucide-react'
import { useDesktopRuntime } from '../../app/desktopRuntime'

interface BackgroundState {
  enabled: boolean
  serviceError: string | null
}

export function BackgroundSettings() {
  const { serviceError } = useDesktopRuntime()
  const [state, setState] = useState<BackgroundState | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    void invoke<BackgroundState>('get_background_state')
      .then((value) => { if (active) setState(value) })
      .catch((reason: unknown) => { if (active) setError(String(reason)) })
    return () => { active = false }
  }, [])

  async function setEnabled(enabled: boolean) {
    setBusy(true)
    setError(null)
    try {
      setState(await invoke<BackgroundState>('set_background_enabled', { enabled }))
    } catch (reason) {
      setError(String(reason))
    } finally {
      setBusy(false)
    }
  }

  async function quit() {
    try {
      await invoke('quit_app')
    } catch (reason) {
      setError(String(reason))
    }
  }

  return (
    <details className="background-settings">
      <summary aria-label="Настройки фонового сбора" title="Настройки фонового сбора"><Settings2 aria-hidden="true" /></summary>
      <div className="background-settings__panel">
        <strong>Фоновый сбор цен</strong>
        <p>Автоматический полный сбор — каждые 6 часов, пока приложение работает.</p>
        <label className="background-settings__toggle">
          <input
            type="checkbox"
            checked={state?.enabled ?? false}
            disabled={!state || busy}
            onChange={(event) => void setEnabled(event.currentTarget.checked)}
          />
          <span>Запускать после входа в систему</span>
        </label>
        {state?.enabled ? <p>Закрытие окна оставит сбор работающим. Открыть окно снова можно через ярлык или значок приложения.</p> : null}
        {serviceError ? <p className="background-settings__error" role="alert">Службы: {serviceError}</p> : null}
        {error ? <p className="background-settings__error" role="alert">{error}</p> : null}
        <button type="button" className="background-settings__quit" onClick={() => void quit()}>Полностью выйти</button>
      </div>
    </details>
  )
}
