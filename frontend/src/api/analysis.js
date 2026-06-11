import client from './client'

export const analysisApi = {
  startClip:      (clipId)     => client.post(`/analysis/clip/${clipId}/start`).then(r => r.data),
  startProject:   (projectId, analysisMode = 'gemini')  => client.post(`/analysis/project/${projectId}/start`, null, { params: { analysis_mode: analysisMode } }).then(r => r.data),
  taskStatus:     (taskId)     => client.get(`/analysis/task/${taskId}/status`).then(r => r.data),
  getClip:        (clipId)     => client.get(`/analysis/clip/${clipId}`).then(r => r.data),
  projectScores:  (projectId)  => client.get(`/analysis/project/${projectId}/scores`).then(r => r.data),
  detectDupes:    (projectId)  => client.post(`/analysis/project/${projectId}/duplicates`).then(r => r.data),
}
