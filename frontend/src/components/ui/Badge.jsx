import clsx from 'clsx'

const variants = {
  default: 'bg-white/10 text-white/70',
  accent:  'bg-accent/20 text-accent',
  success: 'bg-success/20 text-success',
  warning: 'bg-warning/20 text-warning',
  danger:  'bg-danger/20  text-danger',
  muted:   'bg-editor-border text-white/40',
}

export default function Badge({ children, variant = 'default', className }) {
  return (
    <span className={clsx(
      'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-2xs font-medium',
      variants[variant],
      className,
    )}>
      {children}
    </span>
  )
}
