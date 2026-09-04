import { Link, Route, Routes } from 'react-router-dom'
import { Button } from '@/components/Button'
import { ThemeToggle } from '@/components/ThemeToggle'
import { useApplyTheme } from '@/components/theme-store'
import { Toaster } from '@/components/Toaster'
import { TooltipProvider } from '@/components/Tooltip'
import { DashboardPage } from '@/routes/DashboardPage'
import { LibraryPage } from '@/routes/LibraryPage'
import { NotFoundPage } from '@/routes/NotFoundPage'
import { StudioPage } from '@/routes/StudioPage'

function AppShell() {
  return (
    <header className="border-b border-ink-300/20">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-8 py-5">
        <Link to="/" className="font-display text-2xl font-bold tracking-tight text-ink-900">
          skill-bites
        </Link>
        <nav className="flex items-center gap-5">
          <Link
            to="/jobs"
            className="font-mono text-sm text-ink-500 underline decoration-accent decoration-2 underline-offset-4 decoration-transparent transition-[color,text-decoration-color] duration-(--duration-1) hover:text-ink-900 hover:decoration-accent"
          >
            Videos
          </Link>
          <Link
            to="/library"
            className="font-mono text-sm text-ink-500 underline decoration-accent decoration-2 underline-offset-4 decoration-transparent transition-[color,text-decoration-color] duration-(--duration-1) hover:text-ink-900 hover:decoration-accent"
          >
            Library
          </Link>
          <ThemeToggle />
          <Link to="/">
            <Button variant="secondary">New video</Button>
          </Link>
        </nav>
      </div>
    </header>
  )
}

export default function App() {
  useApplyTheme()
  return (
    <TooltipProvider>
      <AppShell />
      <Routes>
        <Route path="/" element={<StudioPage />} />
        <Route path="/jobs" element={<DashboardPage />} />
        <Route path="/jobs/:jobId" element={<StudioPage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
      <Toaster />
    </TooltipProvider>
  )
}
