import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react'

const CONTROL_CLASSES =
  'h-10 w-full rounded-lg border border-terminal-navy/20 bg-white px-3 text-sm text-terminal-navy transition-colors placeholder:text-slate-400 focus:border-terminal-navy'

export function Label({ htmlFor, children }: { htmlFor: string; children: ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="mb-1.5 block text-xs font-medium text-slate-600">
      {children}
    </label>
  )
}

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  id: string
}

export function TextField({ label, id, className = '', ...props }: FieldProps) {
  return (
    <div>
      <Label htmlFor={id}>{label}</Label>
      <input id={id} className={`${CONTROL_CLASSES} ${className}`} {...props} />
    </div>
  )
}

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string
  id: string
  children: ReactNode
}

export function SelectField({ label, id, className = '', children, ...props }: SelectFieldProps) {
  return (
    <div>
      <Label htmlFor={id}>{label}</Label>
      <select id={id} className={`${CONTROL_CLASSES} ${className}`} {...props}>
        {children}
      </select>
    </div>
  )
}
