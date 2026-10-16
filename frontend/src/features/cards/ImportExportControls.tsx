import { useState } from 'react'
import { Download, Upload, X } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { invoke } from '@tauri-apps/api/core'
import { api, isDesktopMode } from '../../api/client'
import { Button } from '../../components/ui/Button'
import type { ImportSummary, TransferDocument } from '../../types/domain'

function summaryText(summary: ImportSummary) {
  return `Добавлено карточек: ${summary.cardsAdded}, объединено: ${summary.cardsMerged}, ` +
    `добавлено записей истории: ${summary.observationsAdded}, новых групп: ${summary.groupsAdded ?? 0}.`
}

interface Props {
  onStatus: (message: string, kind: 'success' | 'error') => void
}

export function ImportExportControls({ onStatus }: Props) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [exportBusy, setExportBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fileName, setFileName] = useState('')
  const [document, setDocument] = useState<TransferDocument | null>(null)
  const [preview, setPreview] = useState<ImportSummary | null>(null)

  async function exportCards() {
    setError(null)
    setExportBusy(true)
    try {
      const data = await api.exportCards()
      const contents = JSON.stringify(data, null, 2)
      const fileName = `price-watch-export-${new Date().toISOString().slice(0, 10)}.json`
      if (isDesktopMode) {
        const saved = await invoke<boolean>('save_export_file', { contents, fileName })
        if (!saved) return
      } else {
        const blob = new Blob([contents], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const link = window.document.createElement('a')
        link.href = url
        link.download = fileName
        window.document.body.append(link)
        link.click()
        link.remove()
        window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      }
      onStatus(`Экспортировано карточек: ${data.cards.length}, групп: ${data.groups?.length ?? 0}.`, 'success')
    } catch (caught) {
      onStatus(caught instanceof Error ? caught.message : 'Не удалось экспортировать данные', 'error')
    } finally {
      setExportBusy(false)
    }
  }

  async function chooseFile(file: File | undefined) {
    setDocument(null)
    setPreview(null)
    setError(null)
    setFileName(file?.name ?? '')
    if (!file) return
    setBusy(true)
    try {
      const data = JSON.parse(await file.text()) as TransferDocument
      const result = await api.previewImportCards(data)
      setDocument(data)
      setPreview(result)
    } catch (caught) {
      setError(caught instanceof SyntaxError ? 'Файл не содержит корректный JSON' :
        caught instanceof Error ? caught.message : 'Не удалось проверить файл')
    } finally {
      setBusy(false)
    }
  }

  async function importCards() {
    if (!document) return
    setBusy(true)
    setError(null)
    try {
      const result = await api.importCards(document)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['cards'] }),
        queryClient.invalidateQueries({ queryKey: ['groups'] }),
        queryClient.invalidateQueries({ queryKey: ['deals'] }),
      ])
      setOpen(false)
      onStatus(`Импорт завершён. ${summaryText(result)}`, 'success')
      setDocument(null)
      setPreview(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Не удалось импортировать данные')
    } finally {
      setBusy(false)
    }
  }

  function close() {
    if (busy) return
    setOpen(false)
    setError(null)
    setDocument(null)
    setPreview(null)
    setFileName('')
  }

  return (
    <>
      <Button icon={<Download />} onClick={() => void exportCards()} disabled={exportBusy}>
        {exportBusy ? 'Экспорт…' : 'Экспорт'}
      </Button>
      <Button icon={<Upload />} onClick={() => { setError(null); setOpen(true) }}>Импорт</Button>
      {open ? (
        <div className="confirm-dialog-layer" role="presentation">
          <button className="confirm-dialog-backdrop" type="button" onClick={close} aria-label="Закрыть импорт" />
          <div className="confirm-dialog transfer-dialog" role="dialog" aria-modal="true" aria-labelledby="transfer-title">
            <button className="transfer-dialog__close" type="button" onClick={close} disabled={busy} aria-label="Закрыть"><X /></button>
            <h2 id="transfer-title">Импорт карточек и истории</h2>
            <p>Выберите файл, сохранённый через «Экспорт». Существующие карточки и их история будут объединены.</p>
            <label className="transfer-dialog__file">
              <span>Файл экспорта</span>
              <input type="file" accept=".json,application/json" disabled={busy}
                onChange={(event) => {
                  const file = event.currentTarget.files?.[0]
                  event.currentTarget.value = ''
                  void chooseFile(file)
                }} />
            </label>
            {busy && !preview ? <p role="status">Проверяем файл…</p> : null}
            {fileName && preview ? (
              <div className="transfer-dialog__preview" role="status">
                <strong>{fileName}</strong>
                <p>{summaryText(preview)}</p>
                <p>Пропущено повторов: {preview.observationsSkipped}; удалено одинаковых соседних цен: {preview.observationsRemoved}.</p>
                <p>Настройки уже существующих карточек сохранятся.</p>
              </div>
            ) : null}
            {error ? <p className="action-error" role="alert">{error}</p> : null}
            <div className="confirm-dialog__actions">
              <Button onClick={close} disabled={busy}>Отмена</Button>
              <Button variant="primary" onClick={() => void importCards()} disabled={!preview || busy}>
                {busy ? 'Импортируем…' : 'Импортировать'}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
