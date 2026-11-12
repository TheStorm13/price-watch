import { expect, it, vi } from 'vitest'
const plugin = vi.hoisted(() => ({ isPermissionGranted: vi.fn(), requestPermission: vi.fn(), sendNotification: vi.fn() }))
vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }))
vi.mock('../../api/client', () => ({ isDesktopMode: true }))
vi.mock('@tauri-apps/plugin-notification', () => plugin)
import { ensureNotificationPermission, notifyTarget } from './notificationTransport'
it('requests permission on enable and exposes refusal', async () => {
  plugin.isPermissionGranted.mockResolvedValue(false); plugin.requestPermission.mockResolvedValue('denied')
  expect(await ensureNotificationPermission()).toBe(false)
  await expect(notifyTarget('Цель', '100 ₽')).rejects.toThrow('не разрешила')
  expect(plugin.sendNotification).not.toHaveBeenCalled()
  plugin.requestPermission.mockResolvedValue('granted')
  expect(await ensureNotificationPermission()).toBe(true)
})

it('awaits native transport rejection through the plugin command', async () => {
  const { invoke } = await import('@tauri-apps/api/core')
  plugin.isPermissionGranted.mockResolvedValue(true)
  vi.mocked(invoke).mockRejectedValue(new Error('D-Bus unavailable'))
  await expect(notifyTarget('Цель', '100 ₽')).rejects.toThrow('D-Bus unavailable')
  expect(invoke).toHaveBeenCalledWith('plugin:notification|notify', { options: { title: 'Цель', body: '100 ₽' } })
})
