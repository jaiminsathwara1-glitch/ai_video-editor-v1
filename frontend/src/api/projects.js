import client from './client'

export const projectsApi = {
  list:   ()           => client.get('/projects').then(r => r.data),
  get:    (id)         => client.get(`/projects/${id}`).then(r => r.data),
  create: (body)       => client.post('/projects', body).then(r => r.data),
  update: (id, body)   => client.put(`/projects/${id}`, body).then(r => r.data),
  delete: (id)         => client.delete(`/projects/${id}`),
  stats:  (id)         => client.get(`/projects/${id}/stats`).then(r => r.data),
}
