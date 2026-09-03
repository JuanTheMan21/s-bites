import { Link, Route, Routes } from 'react-router-dom'
import { Button } from '@/components/Button'
import { Toaster } from '@/components/Toaster'
import { TooltipProvider } from '@/components/Tooltip'
import { DashboardPage } from '@/routes/DashboardPage'
import { JobDetailPage } from '@/routes/JobDetailPage'
import { LandingPage } from '@/routes/LandingPage'
import { LibraryPage } from '@/routes/LibraryPage'
import { NotFoundPage } from '@/routes/NotFoundPage'

function AppShell() {
  return (
    <header className="border-b border-ink-300/20">
      <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
        <Link to="/" className="font-display text-lg text-ink-900">
          s_bites
        </Link>
        <nav className="flex items-center gap-4">
          <Link to="/jobs" className="font-mono text-xs text-ink-500 hover:text-ink-900">
            Videos
          </Link>
          <Link to="/library" className="font-mono text-xs text-ink-500 hover:text-ink-900">
            Library
          </Link>
          <Link to="/">
            <Button variant="secondary">New video</Button>
          </Link>
        </nav>
      </div>
    </header>
  )
}

export default function App() {
  return (
    <TooltipProvider>
      <AppShell />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/jobs" element={<DashboardPage />} />
        <Route path="/jobs/:jobId" element={<JobDetailPage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
      <Toaster />
    </TooltipProvider>
  )
}
