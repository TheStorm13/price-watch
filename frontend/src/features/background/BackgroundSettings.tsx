import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Field, FieldLabel } from '@/components/ui/field'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover'
import { Alert, AlertDescription } from '@/components/ui/alert'
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
    <Popover>
      <PopoverTrigger asChild><Button variant="ghost" size="sm" aria-label="Настройки" title="Настройки фонового сбора"><Settings2 data-icon="inline-start" aria-hidden="true" />Настройки</Button></PopoverTrigger>
      <PopoverContent align="start" side="right" className="flex w-[340px] flex-col gap-3">
        <strong>Фоновый сбор цен</strong>
        <p>Автоматический полный сбор — каждые 6 часов, пока приложение работает.</p>
        <Field orientation="horizontal" data-disabled={!state || busy}>
          <Checkbox id="background-enabled" checked={state?.enabled ?? false} disabled={!state || busy} onCheckedChange={(checked) => void setEnabled(checked === true)} />
          <FieldLabel htmlFor="background-enabled">Запускать после входа в систему</FieldLabel>
        </Field>
        {state?.enabled ? <p>Закрытие окна оставит сбор работающим. Открыть окно снова можно через ярлык или значок приложения.</p> : null}
        {serviceError ? <Alert variant="destructive"><AlertDescription>Службы: {serviceError}</AlertDescription></Alert> : null}
        {error ? <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert> : null}
        <Button variant="outline" type="button" onClick={() => void quit()}>Полностью выйти</Button>
      </PopoverContent>
    </Popover>
  )
}
