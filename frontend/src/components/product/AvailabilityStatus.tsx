import type { Availability } from '../../types/domain'
import { availabilityLabel } from '../../utils/format'
import { Badge } from '../ui/badge'

export function AvailabilityStatus({ value }: { value: Availability | null }) {
  return <Badge variant={value === 'in_stock' ? 'success' : value === 'out_of_stock' ? 'warning' : 'muted'}>{value === null ? 'Нет данных' : availabilityLabel[value]}</Badge>
}
