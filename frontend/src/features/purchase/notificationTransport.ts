import { invoke } from '@tauri-apps/api/core'
import { isDesktopMode } from '../../api/client'

export async function ensureNotificationPermission() {
  if (!isDesktopMode) return true
  const plugin = await import('@tauri-apps/plugin-notification')
  return await plugin.isPermissionGranted() || await plugin.requestPermission() === 'granted'
}

export async function notifyTarget(title: string, body: string) {
  if (!isDesktopMode) return // Demo transport never asks for browser permission.
  const plugin = await import('@tauri-apps/plugin-notification')
  if (!await plugin.isPermissionGranted()) throw new Error('ОС не разрешила уведомления о целевой цене')
  // The plugin's sendNotification wrapper returns void and drops notify rejection.
  // Await its registered command so failed OS delivery is visible to the observer.
  await invoke('plugin:notification|notify', { options: { title, body } })
}
