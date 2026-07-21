import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react'

const CONTROL_CLASSES =
  'h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900 transition-colors placeholder:text-slate-400 focus:border-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:focus:border-slate-400'

export function Label({ htmlFor, children }: { htmlFor: string; children: ReactNode }) {
  return (
    <label
      htmlFor={htmlFor}
      className="mb-1.5 block text-xs font-medium text-slate-600 dark:text-slate-400"
    >
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

/** Bare select for use inside dense table rows, where a label would not fit. */
export function InlineSelect({ className = '', children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={`h-8 w-full rounded-md border border-slate-300 bg-white px-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 ${className}`}
      {...props}
    >
      {children}
    </select>
  )
}
