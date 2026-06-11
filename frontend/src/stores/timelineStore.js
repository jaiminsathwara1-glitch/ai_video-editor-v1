import { create } from 'zustand'

/**
 * Timeline store — manages the rough-cut editor state.
 *
 * Each entry: { clip_id, order, in_point, out_point, track, score, reason,
 *               locked, approved, rejected }
 */
export const useTimelineStore = create((set, get) => ({
  timelineId: null,
  entries: [],               // ordered clip entries
  selectedEntryId: null,
  zoom: 1,                   // px-per-second scale
  isDirty: false,            // unsaved local changes

  setTimeline: (timeline) =>
    set({
      timelineId: timeline.id,
      // Sort by `order` here as a safety net — the API schema validator also
      // sorts, but guarding here ensures any stale or manually-reordered data
      // from a previous session doesn't render clips in the wrong sequence.
      entries: [...(timeline.entries || [])]
        .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
        .map((e) => ({
          ...e,
          locked: false,
          approved: false,
          rejected: false,
        })),
      isDirty: false,
    }),

  selectEntry: (clipId) => set({ selectedEntryId: clipId }),

  // ── Reorder ─────────────────────────────────────────────────────────────
  reorder: (fromIndex, toIndex) =>
    set((s) => {
      const arr = [...s.entries]
      const [moved] = arr.splice(fromIndex, 1)
      arr.splice(toIndex, 0, moved)
      return {
        entries: arr.map((e, i) => ({ ...e, order: i + 1 })),
        isDirty: true,
      }
    }),

  // ── Trim ─────────────────────────────────────────────────────────────────
  setTrim: (clipId, inPoint, outPoint) =>
    set((s) => ({
      entries: s.entries.map((e) =>
        e.clip_id === clipId ? { ...e, in_point: inPoint, out_point: outPoint } : e
      ),
      isDirty: true,
    })),

  // ── Approve / Reject ──────────────────────────────────────────────────────
  approve: (clipId) =>
    set((s) => ({
      entries: s.entries.map((e) =>
        e.clip_id === clipId ? { ...e, approved: true, rejected: false } : e
      ),
      isDirty: true,
    })),

  reject: (clipId) =>
    set((s) => ({
      entries: s.entries.map((e) =>
        e.clip_id === clipId ? { ...e, rejected: true, approved: false } : e
      ),
      isDirty: true,
    })),

  // ── Lock ─────────────────────────────────────────────────────────────────
  toggleLock: (clipId) =>
    set((s) => ({
      entries: s.entries.map((e) =>
        e.clip_id === clipId ? { ...e, locked: !e.locked } : e
      ),
    })),

  // ── Remove ───────────────────────────────────────────────────────────────
  removeEntry: (clipId) =>
    set((s) => ({
      entries: s.entries
        .filter((e) => e.clip_id !== clipId)
        .map((e, i) => ({ ...e, order: i + 1 })),
      isDirty: true,
    })),

  // ── Zoom ─────────────────────────────────────────────────────────────────
  setZoom: (zoom) => set({ zoom: Math.max(0.2, Math.min(10, zoom)) }),

  markSaved: () => set({ isDirty: false }),

  // ── Derived ───────────────────────────────────────────────────────────────
  get totalDuration() {
    return get().entries.reduce((sum, e) => sum + (e.out_point - e.in_point), 0)
  },
  get approvedCount() {
    return get().entries.filter((e) => e.approved).length
  },
  get rejectedEntries() {
    return get().entries.filter((e) => e.rejected)
  },
}))
