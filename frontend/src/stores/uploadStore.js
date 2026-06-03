import { create } from 'zustand'
import { clipsApi } from '@/api/clips'

/**
 * Upload store — tracks all in-flight and completed uploads.
 *
 * Shape of each upload entry:
 * {
 *   id: string (temp local id before clip_id arrives),
 *   file: File,
 *   clipId: string | null,
 *   status: 'queued' | 'uploading' | 'processing' | 'done' | 'error',
 *   progress: 0-100,
 *   chunksTotal: number,
 *   chunksDone: number,
 *   error: string | null,
 * }
 */
export const useUploadStore = create((set, get) => ({
  uploads: [],        // list of upload entries
  projectId: null,

  setProject: (projectId) => set({ projectId }),

  /** Add files to the upload queue */
  enqueue: (files) => {
    const newEntries = Array.from(files).map((file) => ({
      id: crypto.randomUUID(),
      file,
      clipId: null,
      status: 'queued',
      progress: 0,
      chunksTotal: 0,
      chunksDone: 0,
      error: null,
    }))
    set((s) => ({ uploads: [...s.uploads, ...newEntries] }))
  },

  /** Update a single upload entry */
  _update: (localId, patch) =>
    set((s) => ({
      uploads: s.uploads.map((u) => (u.id === localId ? { ...u, ...patch } : u)),
    })),

  /** Start uploading all queued files */
  startAll: async () => {
    const { uploads, projectId, _update } = get()
    const queued = uploads.filter((u) => u.status === 'queued')

    for (const entry of queued) {
      _update(entry.id, { status: 'uploading' })
      try {
        const clip = await clipsApi.uploadFile(
          projectId,
          entry.file,
          (pct, chunksDone, chunksTotal) => {
            _update(entry.id, { progress: pct, chunksDone, chunksTotal })
          },
        )
        _update(entry.id, { status: 'done', progress: 100, clipId: clip.id })
      } catch (err) {
        _update(entry.id, {
          status: 'error',
          error: err?.response?.data?.detail || err.message,
        })
      }
    }
  },

  /** Remove a single upload from the list */
  remove: (localId) =>
    set((s) => ({ uploads: s.uploads.filter((u) => u.id !== localId) })),

  clearAll: () => set({ uploads: [] }),

  // ── Derived ──────────────────────────────────────────────────────────────
  get totalFiles()    { return get().uploads.length },
  get doneCount()     { return get().uploads.filter(u => u.status === 'done').length },
  get hasErrors()     { return get().uploads.some(u => u.status === 'error') },
  get isUploading()   { return get().uploads.some(u => u.status === 'uploading') },
}))
