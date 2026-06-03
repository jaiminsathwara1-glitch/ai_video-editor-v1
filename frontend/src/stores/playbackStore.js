import { create } from 'zustand'

export const usePlaybackStore = create((set, get) => ({
  isPlaying:   false,
  currentTime: 0,
  duration:    0,
  volume:      1,
  activeClipId: null,

  play:  () => set({ isPlaying: true }),
  pause: () => set({ isPlaying: false }),
  toggle: () => set((s) => ({ isPlaying: !s.isPlaying })),

  seek:         (t)       => set({ currentTime: Math.max(0, t) }),
  setDuration:  (d)       => set({ duration: d }),
  setVolume:    (v)       => set({ volume: Math.max(0, Math.min(1, v)) }),
  setActiveClip: (clipId) => set({ activeClipId: clipId, isPlaying: false, currentTime: 0 }),
}))
