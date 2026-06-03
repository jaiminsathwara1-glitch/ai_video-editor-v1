import client from './client'

const CHUNK_SIZE = 10 * 1024 * 1024 // 10 MB

export const clipsApi = {
  list:       (projectId, params) => client.get(`/clips/project/${projectId}`, { params }).then(r => r.data),
  get:        (id)                => client.get(`/clips/${id}`).then(r => r.data),
  delete:     (id)                => client.delete(`/clips/${id}`),
  remove:     (id)                => client.delete(`/clips/${id}`),

  /** Initialise a chunked upload session */
  initChunked: (body) =>
    client.post('/clips/upload/init', body).then(r => r.data),

  /** Upload a single binary chunk */
  uploadChunk: (clipId, chunkIndex, chunkData, onProgress) =>
    client.post(`/clips/${clipId}/chunk/${chunkIndex}`, chunkData, {
      headers: { 'Content-Type': 'application/octet-stream' },
      onUploadProgress: onProgress,
    }).then(r => r.data),

  /**
   * Full chunked upload with progress callback.
   * onProgress(pct: 0-100, chunksDone, total)
   */
  async uploadFile(projectId, file, onProgress) {
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE)

    // 1. Init session
    const clip = await clipsApi.initChunked({
      project_id: projectId,
      filename: file.name,
      file_size: file.size,
      mime_type: file.type || 'video/mp4',
      total_chunks: totalChunks,
    })

    // 2. Upload chunks sequentially
    for (let i = 0; i < totalChunks; i++) {
      const start = i * CHUNK_SIZE
      const chunk = file.slice(start, start + CHUNK_SIZE)
      const buffer = await chunk.arrayBuffer()

      await clipsApi.uploadChunk(clip.id, i, buffer, (evt) => {
        if (evt.total) {
          const chunkPct  = evt.loaded / evt.total
          const overall   = ((i + chunkPct) / totalChunks) * 100
          onProgress?.(Math.round(overall), i + 1, totalChunks)
        }
      })
    }

    return clip
  },
}
