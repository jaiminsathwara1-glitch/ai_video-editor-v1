import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useProjectStore = create(
  persist(
    (set, get) => ({
      currentProjectId: null,
      recentProjects: [],  // [{id, name, createdAt}]

      setCurrentProject: (id) => set({ currentProjectId: id }),

      addRecent: (project) =>
        set((s) => {
          const filtered = s.recentProjects.filter((p) => p.id !== project.id)
          return {
            recentProjects: [project, ...filtered].slice(0, 10),
          }
        }),

      clearCurrent: () => set({ currentProjectId: null }),
    }),
    { name: 'cutai-project' },
  ),
)
