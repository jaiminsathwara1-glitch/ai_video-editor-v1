import clsx from 'clsx'

export default function ProgressBar({ value = 0, max = 100, className, showLabel = false, color = 'accent' }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  const colorClass = {
    accent:  'bg-accent progress-shimmer',
    success: 'bg-success',
    warning: 'bg-warning',
    danger:  'bg-danger',
  }[color] ?? 'bg-accent'

  return (
    <div className={clsx('flex items-center gap-2', className)}>
      <div className="flex-1 h-1.5 bg-editor-border rounded-full overflow-hidden">
        <div
          className={clsx('h-full rounded-full transition-[width] duration-300', colorClass)}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showLabel && (
        <span className="text-2xs text-white/40 font-mono w-8 text-right">
          {Math.round(pct)}%
        </span>
      )}
    </div>
  )
}
