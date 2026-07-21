import { formatUSD, formatUSDSigned, signColor } from '../../utils/money'

interface AmountProps {
  value: number
  /** Show an explicit +/- and colour by sign. Use for deltas and net figures. */
  signed?: boolean
  /** Colour by sign without forcing a leading `+`. */
  colored?: boolean
  className?: string
}

/**
 * Renders a USD figure with tabular numerals so columns line up.
 * All money in the app should go through this or `formatUSD`.
 */
export function Amount({ value, signed = false, colored = signed, className = '' }: AmountProps) {
  const color = colored ? signColor(value) : ''
  return (
    <span className={`tnum ${color} ${className}`}>
      {signed ? formatUSDSigned(value) : formatUSD(value)}
    </span>
  )
}
