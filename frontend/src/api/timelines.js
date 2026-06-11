import client from './client'

export const timelinesApi = {
  list:      (projectId)     => client.get(`/timelines/project/${projectId}`).then(r => r.data),
  get:       (id)            => client.get(`/timelines/${id}`).then(r => r.data),
  generate:  (body)          => client.post('/timelines/generate', body).then(r => r.data),
  reorder:   (id, analysisMode = 'gemini') => client.post(`/timelines/${id}/reorder`, null, { params: { analysis_mode: analysisMode } }).then(r => r.data),
  exportXml: (id)            => client.post(`/timelines/${id}/export/xml`).then(r => r.data),
  exportEdl: (id)            => client.post(`/timelines/${id}/export/edl`).then(r => r.data),
  exportAll: (id)            => client.post(`/timelines/${id}/export/all`).then(r => r.data),
  download:  (id, fmt)       => client.get(`/timelines/${id}/download/${fmt}`, { responseType: 'blob' }).then(r => r.data),
  renderVideo: (id)          => client.post(`/timelines/${id}/render`).then(r => r.data),
  downloadVideo: (id)        => client.get(`/timelines/${id}/download/video`, { responseType: 'blob' }).then(r => r.data),
}
