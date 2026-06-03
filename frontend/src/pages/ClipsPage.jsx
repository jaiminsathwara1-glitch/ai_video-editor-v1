import { useState, useCallback, useRef, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Filter, SortAsc, Scissors, Search, X,
  Grid3X3, List, ChevronRight, BarChart2, Tag, Trash2
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { clipsApi } from '@/api/clips'
import { useProjectScores } from '@/hooks/useAnalysis'
import { useProjectSocket } from '@/hooks/useSocket'
import ClipCard from '@/components/clips/ClipCard'
import ClipDetail from '@/components/clips/ClipDetail'
import Button from '@/components/ui/Button'
import clsx from 'clsx'

const SORT_OPTIONS = [
  { value: 'score_desc',    label: 'Score ↓' },
  { value: 'score_asc',     label: 'Score ↑' },
  { value: 'name_asc',      label: 'Name A→Z' },
  { value: 'duration_desc', label: 'Duration ↓' },
]

const FILTER_TABS = [
  { value: 'all',       label: 'All',        color: '' },
  { value: 'good',      label: '✓ Good',     color: 'data-[active=true]:text-success' },
  { value: 'issues',    label: '⚠ Issues',   color: 'data-[active=true]:text-warning' },
  { value: 'duplicate', label: '⊕ Dupes',    color: 'data-[active=true]:text-danger'  },
]

export default function ClipsPage() {
  const { projectId } = useParams()
  const navigate = useNavigate()

  const { data: clips = [], refetch } = useQuery({
    queryKey: ['clips', projectId],
    queryFn: () => clipsApi.list(projectId),
    enabled: !!projectId,
    refetchInterval: 10_000,
  })

  const { data: scores = [] } = useProjectScores(projectId)
  const scoreMap = Object.fromEntries(scores.map(s => [s.clip_id, s]))

  useProjectSocket(projectId, { onAnalysisUpdate: refetch, onClipUpdate: refetch })

  const [selectedClip, setSelectedClip] = useState(null)
  const [sort, setSort]     = useState('score_desc')
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [viewMode, setViewMode] = useState('grid') // 'grid' | 'list'
  const [confirmDeleteId, setConfirmDeleteId] = useState(null)
  const confirmTimeoutRef = useRef(null)

  useEffect(() => {
    return () => {
      if (confirmTimeoutRef.current) clearTimeout(confirmTimeoutRef.current)
    }
  }, [])

  const analysedClips = clips.filter(c => c.status === 'analysed')

  // Filter
  let filtered = [...analysedClips]
  if (search) {
    const q = search.toLowerCase()
    filtered = filtered.filter(c => c.original_filename.toLowerCase().includes(q))
  }
  if (filter === 'good')      filtered = filtered.filter(c => (scoreMap[c.id]?.overall_score ?? scoreMap[c.id]?.score ?? 0) >= 7)
  if (filter === 'issues')    filtered = filtered.filter(c => {
    const s = scoreMap[c.id]
    return s?.is_blurry || s?.is_shaky || s?.is_overexposed || s?.is_underexposed
  })
  if (filter === 'duplicate') filtered = filtered.filter(c => scoreMap[c.id]?.has_duplicate)

  // Sort
  filtered.sort((a, b) => {
    const sa = scoreMap[a.id]?.overall_score ?? scoreMap[a.id]?.score ?? 0
    const sb = scoreMap[b.id]?.overall_score ?? scoreMap[b.id]?.score ?? 0
    if (sort === 'score_desc')    return sb - sa
    if (sort === 'score_asc')     return sa - sb
    if (sort === 'name_asc')      return a.original_filename.localeCompare(b.original_filename)
    if (sort === 'duration_desc') return (b.duration ?? 0) - (a.duration ?? 0)
    return 0
  })

  const avgScore = analysedClips.length > 0
    ? (scores.reduce((s, x) => s + (x.overall_score ?? x.score ?? 0), 0) / scores.length).toFixed(1)
    : null

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── Main panel ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="flex-shrink-0 border-b border-editor-border bg-editor-surface">
          {/* Top row */}
          <div className="flex items-center gap-3 px-5 py-2.5">
            <h1 className="text-sm font-bold text-white flex items-center gap-2">
              Clip Review
              <span className="text-white/35 font-normal text-xs">
                {filtered.length} / {analysedClips.length}
              </span>
            </h1>

            {/* Search */}
            <div className="relative ml-2">
              <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-white/30" />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search clips…"
                className="bg-editor-active border border-editor-border rounded-md pl-7 pr-3 py-1.5 text-xs text-white placeholder-white/25 focus:outline-none focus:border-accent w-44 transition-all"
              />
              {search && (
                <button onClick={() => setSearch('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-white/30 hover:text-white">
                  <X size={11} />
                </button>
              )}
            </div>

            {/* Stats pills */}
            {avgScore && (
              <div className="hidden md:flex items-center gap-2 ml-1">
                <span className="text-2xs text-white/30 flex items-center gap-1">
                  <BarChart2 size={10} /> Avg score: <span className="text-accent font-mono">{avgScore}</span>
                </span>
              </div>
            )}

            <div className="ml-auto flex items-center gap-2">
              {/* View toggle */}
              <div className="flex bg-editor-active rounded border border-editor-border overflow-hidden">
                <button
                  onClick={() => setViewMode('grid')}
                  className={clsx('p-1.5 transition-colors', viewMode === 'grid' ? 'bg-accent/20 text-accent' : 'text-white/40 hover:text-white/70')}
                >
                  <Grid3X3 size={12} />
                </button>
                <button
                  onClick={() => setViewMode('list')}
                  className={clsx('p-1.5 transition-colors', viewMode === 'list' ? 'bg-accent/20 text-accent' : 'text-white/40 hover:text-white/70')}
                >
                  <List size={12} />
                </button>
              </div>

              {/* Sort */}
              <select
                value={sort}
                onChange={e => setSort(e.target.value)}
                className="bg-editor-active border border-editor-border text-xs text-white/70 rounded-md px-2.5 py-1.5 focus:outline-none focus:border-accent"
              >
                {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>

              <Button
                size="sm"
                variant="primary"
                onClick={() => navigate(`/project/${projectId}/timeline`)}
              >
                <Scissors size={12} /> Build Timeline
              </Button>
            </div>
          </div>

          {/* Filter tabs */}
          <div className="flex px-5 gap-0.5 pb-0">
            {FILTER_TABS.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => setFilter(value)}
                className={clsx(
                  'px-3 py-2 text-xs font-medium border-b-2 transition-colors',
                  filter === value
                    ? 'border-accent text-accent'
                    : 'border-transparent text-white/40 hover:text-white/70',
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Grid / List */}
        <div className="flex-1 overflow-y-auto p-5">
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center gap-3">
              <div className="w-14 h-14 rounded-2xl bg-editor-panel border border-editor-border flex items-center justify-center">
                <Tag size={22} className="text-white/15" />
              </div>
              <p className="text-white/50 text-sm font-medium">
                {analysedClips.length === 0
                  ? 'No analysed clips yet'
                  : 'No clips match this filter'}
              </p>
              <p className="text-xs text-white/30">
                {analysedClips.length === 0
                  ? 'Run AI analysis from the Processing page first'
                  : 'Try changing your filter or search term'}
              </p>
            </div>
          ) : viewMode === 'grid' ? (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
              <AnimatePresence>
                {filtered.map((clip) => (
                  <ClipCard
                    key={clip.id}
                    clip={clip}
                    analysis={scoreMap[clip.id]}
                    selected={selectedClip?.id === clip.id}
                    onSelect={setSelectedClip}
                  />
                ))}
              </AnimatePresence>
            </div>
          ) : (
            /* List view */
            <div className="space-y-1.5">
              {filtered.map((clip) => {
                const a = scoreMap[clip.id]
                return (
                  <motion.div
                    key={clip.id}
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    onClick={() => setSelectedClip(clip)}
                    onMouseLeave={() => setConfirmDeleteId(null)}
                    className={clsx(
                      'flex items-center gap-3 p-3 rounded-lg border cursor-pointer hover:border-white/15 transition-all group',
                      selectedClip?.id === clip.id
                        ? 'border-accent/40 bg-accent/5'
                        : 'border-editor-border bg-editor-panel'
                    )}
                  >
                    <div className="w-16 h-10 rounded bg-editor-active flex-shrink-0 overflow-hidden">
                      <img
                        src={`/api/v1/clips/${clip.id}/thumbnail`}
                        alt=""
                        className="w-full h-full object-cover"
                        onError={e => { e.target.style.display = 'none' }}
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-white truncate">{clip.original_filename}</p>
                      <p className="text-2xs text-white/30 font-mono">{clip.duration?.toFixed(1)}s · {clip.width}×{clip.height}</p>
                    </div>
                    {a?.overall_score != null && (
                      <div className={clsx(
                        'text-xs font-bold tabular-nums px-2 py-0.5 rounded border',
                        a.overall_score >= 7 ? 'text-success border-success/30 bg-success/10' :
                        a.overall_score >= 4 ? 'text-warning border-warning/30 bg-warning/10' :
                                               'text-danger border-danger/30 bg-danger/10'
                      )}>
                        {a.overall_score.toFixed(1)}
                      </div>
                    )}
                    {/* Hover delete button in List view */}
                    <button
                      onClick={async (e) => {
                        e.stopPropagation()
                        if (confirmDeleteId !== clip.id) {
                          setConfirmDeleteId(clip.id)
                          if (confirmTimeoutRef.current) clearTimeout(confirmTimeoutRef.current)
                          confirmTimeoutRef.current = setTimeout(() => {
                            setConfirmDeleteId(null)
                          }, 4000)
                          return
                        }

                        if (confirmTimeoutRef.current) clearTimeout(confirmTimeoutRef.current)
                        try {
                          await clipsApi.remove(clip.id)
                          refetch()
                          toast.success('Clip successfully removed')
                          if (selectedClip?.id === clip.id) {
                            setSelectedClip(null)
                          }
                        } catch (err) {
                          const errMsg = err.response?.data?.detail || err.message || 'Unknown error'
                          toast.error(`Failed to remove clip: ${errMsg}`)
                          console.error(err)
                        } finally {
                          setConfirmDeleteId(null)
                        }
                      }}
                      className={clsx(
                        "rounded transition-all duration-150 flex-shrink-0",
                        confirmDeleteId === clip.id
                          ? "p-1 bg-danger text-white scale-105 opacity-100 animate-pulse"
                          : "p-1.5 opacity-0 group-hover:opacity-100 hover:bg-white/10 text-white/40 hover:text-danger"
                      )}
                      title={confirmDeleteId === clip.id ? "Click again to confirm deletion" : "Remove Clip"}
                    >
                      {confirmDeleteId === clip.id ? (
                        <span className="text-[9px] font-bold px-1 uppercase tracking-wider flex items-center gap-1">
                          <Trash2 size={10} /> Confirm
                        </span>
                      ) : (
                        <Trash2 size={12} />
                      )}
                    </button>
                    <ChevronRight size={13} className="text-white/20" />
                  </motion.div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── Detail panel ── */}
      <AnimatePresence>
        {selectedClip && (
          <ClipDetail
            clip={selectedClip}
            onClose={() => setSelectedClip(null)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
