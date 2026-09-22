import type { Availability } from '../../types/domain'
import { availabilityLabel } from '../../utils/format'

export function AvailabilityStatus({ value }: { value: Availability | null }) {
  if (value === null) return <span className="status status--muted"><span className="status__dot" />Нет данных</span>
  return <span className={`status status--${value}`}><span className="status__dot" />{availabilityLabel[value]}</span>
}
