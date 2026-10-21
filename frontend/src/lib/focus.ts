/** Restore overlay focus; a successful deletion may have removed its trigger. */
export function restoreFocus(target: HTMLElement | null) {
  if (target?.isConnected && !target.matches(':disabled')) {
    target.focus({ preventScroll: true })
    return
  }
  const heading = document.querySelector<HTMLElement>('main h1')
  if (heading) {
    heading.tabIndex = -1
    heading.focus({ preventScroll: true })
  }
}
