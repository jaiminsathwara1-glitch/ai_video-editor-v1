import clsx from 'clsx'
import { Loader2 } from 'lucide-react'

const variants = {
  primary:  'bg-accent hover:bg-accent-hover text-white',
  ghost:    'bg-transparent hover:bg-editor-hover text-white/70 hover:text-white',
  danger:   'bg-danger/20 hover:bg-danger/30 text-danger border border-danger/30',
  success:  'bg-success/20 hover:bg-success/30 text-success border border-success/30',
  outline:  'border border-editor-border hover:bg-editor-hover text-white/70 hover:text-white',
}

const sizes = {
  xs: 'px-2 py-1 text-xs gap-1',
  sm: 'px-3 py-1.5 text-xs gap-1.5',
  md: 'px-4 py-2 text-sm gap-2',
  lg: 'px-5 py-2.5 text-sm gap-2',
}

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  icon: Icon,
  className,
  disabled,
  ...props
}) {
  return (
    <button
      disabled={disabled || loading}
      className={clsx(
        'inline-flex items-center justify-center rounded-md font-medium transition-all',
        'focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none',
        'disabled:opacity-40 disabled:cursor-not-allowed',
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    >
      {loading ? (
        <Loader2 size={13} className="animate-spin" />
      ) : Icon ? (
        <Icon size={13} />
      ) : null}
      {children}
    </button>
  )
}
