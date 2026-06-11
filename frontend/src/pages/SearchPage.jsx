import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, Loader2, PlaySquare, Sparkles } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { clipsApi } from '@/api/clips'
import ClipCard from '@/components/clips/ClipCard'
import ClipDetail from '@/components/clips/ClipDetail'

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [selectedClip, setSelectedClip] = useState(null)

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedQuery(query)
    }, 600)
    return () => clearTimeout(handler)
  }, [query])

  const { data: results, isLoading } = useQuery({
    queryKey: ['global-search', debouncedQuery],
    queryFn: () => clipsApi.searchGlobal(debouncedQuery),
    enabled: !!debouncedQuery.trim(),
  })

  return (
    <div className="flex h-full bg-editor-bg overflow-hidden flex-col w-full">
      {/* Header & Search Bar */}
      <div className="pt-14 pb-8 px-8 border-b border-editor-border bg-editor-surface flex flex-col items-center">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-accent/20 flex items-center justify-center text-accent">
            <Sparkles size={20} />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">AI Semantic Search</h1>
        </div>
        <p className="text-white/40 text-sm mb-8 text-center max-w-lg">
          Search across all your projects using natural language. The AI understands the visual content, subjects, and meaning behind your clips.
        </p>

        <div className="relative w-full max-w-2xl group">
          <div className="absolute -inset-0.5 bg-gradient-to-r from-accent to-purple-500 rounded-xl blur opacity-25 group-focus-within:opacity-50 transition duration-500"></div>
          <div className="relative flex items-center bg-editor-active border border-editor-border rounded-xl px-4 py-3.5 shadow-2xl transition-all">
            <Search className="text-white/40 mr-3" size={22} />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. 'A beautiful sunset over the mountains', 'Drone shot of a car'..."
              className="flex-1 bg-transparent border-none text-white placeholder-white/20 focus:outline-none text-base"
              autoFocus
            />
            {isLoading && <Loader2 className="animate-spin text-accent ml-3" size={20} />}
          </div>
        </div>
      </div>

      {/* Results Area */}
      <div className="flex-1 overflow-y-auto p-8 relative">
        {isLoading && (
           <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 text-white/40 z-10">
             <Loader2 size={32} className="animate-spin text-accent" />
             <p className="text-sm font-medium animate-pulse">Computing vector similarity...</p>
           </div>
        )}

        {!isLoading && debouncedQuery && (!results || results.length === 0) && (
          <div className="h-full flex flex-col items-center justify-center text-white/30 gap-4 mt-12">
            <Search size={48} className="opacity-20" />
            <p className="text-lg">No clips matched your search.</p>
            <p className="text-sm opacity-60">Try describing the scene differently.</p>
          </div>
        )}

        {!debouncedQuery && (
          <div className="h-full flex flex-col items-center justify-center text-white/20 gap-4 opacity-50 mt-12">
            <PlaySquare size={48} className="opacity-20" />
            <p className="text-lg">Enter a query above to start exploring your footage.</p>
          </div>
        )}

        {!isLoading && results && results.length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-6 max-w-[1600px] mx-auto">
            <AnimatePresence>
              {results.map((result, idx) => (
                <motion.div
                  key={result.clip.id}
                  initial={{ opacity: 0, scale: 0.95, y: 10 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className="relative group"
                >
                  <ClipCard
                    clip={result.clip}
                    analysis={result.analysis}
                    selected={selectedClip?.id === result.clip.id}
                    onSelect={() => setSelectedClip(result.clip)}
                  />
                  {/* Semantic Score Badge */}
                  <div className="absolute -top-3 -right-3 bg-editor-active border-2 border-editor-border shadow-xl rounded-full px-2.5 py-1 z-10 text-[10px] font-bold text-accent">
                    {(result.search_score * 100).toFixed(0)}% Match
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>

      {/* Detail panel */}
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
