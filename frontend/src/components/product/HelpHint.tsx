import type { ReactNode } from 'react'
import { CircleHelp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'

export function HelpHint({ label, children }: { label: string; children: ReactNode }) {
  return <Popover>
    <PopoverTrigger asChild><Button type="button" variant="ghost" size="icon-sm" className="help-hint" aria-label={`Справка: ${label}`}><CircleHelp aria-hidden="true" className="size-4" /></Button></PopoverTrigger>
    <PopoverContent align="start" className="max-h-[70dvh] overflow-y-auto overscroll-contain" aria-label={label}>{children}</PopoverContent>
  </Popover>
}
