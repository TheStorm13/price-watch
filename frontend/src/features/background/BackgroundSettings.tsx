import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Field, FieldLabel } from '@/components/ui/field'
import { HelpHint } from '@/components/product/HelpHint'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useEffect, useState } from 'react'
import { invoke } from '@tauri-apps/api/core'
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
    <><section className="settings-block" aria-label="Фоновое обновление">
        <div className="flex items-center gap-1"><h2>Фоновое обновление</h2><HelpHint label="Фоновое обновление">Цены обновляются, пока приложение работает. Снова открыть окно можно через ярлык или значок приложения.</HelpHint></div><p>Каждые 6 часов</p>
        {serviceError ? <Alert variant="destructive"><AlertDescription>Службы: {serviceError}</AlertDescription></Alert> : null}
        {error ? <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert> : null}
        <Field orientation="horizontal" data-disabled={!state || busy}>
          <Checkbox id="background-enabled" checked={state?.enabled ?? false} disabled={!state || busy} onCheckedChange={(checked) => void setEnabled(checked === true)} />
          <FieldLabel htmlFor="background-enabled">Запускать при входе в систему</FieldLabel>
        </Field>
        {state?.enabled ? <p>После закрытия окна обновление продолжится</p> : null}
    </section>
    <section className="settings-block" aria-labelledby="settings-exit"><h2 id="settings-exit">Работа приложения</h2><p>Закрыть приложение и остановить фоновое обновление.</p>
        <Button variant="outline" type="button" onClick={() => void quit()}>Завершить работу</Button>
    </section></>
  )
}
