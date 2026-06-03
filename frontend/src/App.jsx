import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from '@/components/layout/Layout'
import HomePage from '@/pages/HomePage'
import UploadPage from '@/pages/UploadPage'
import ProcessingPage from '@/pages/ProcessingPage'
import ClipsPage from '@/pages/ClipsPage'
import TimelinePage from '@/pages/TimelinePage'
import ExportPage from '@/pages/ExportPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="upload" element={<UploadPage />} />
          <Route path="project/:projectId/processing" element={<ProcessingPage />} />
          <Route path="project/:projectId/clips" element={<ClipsPage />} />
          <Route path="project/:projectId/timeline" element={<TimelinePage />} />
          <Route path="project/:projectId/export" element={<ExportPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
