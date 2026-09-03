import { Button } from '@/components/Button'
import { DropdownMenu, type MenuItem } from '@/components/DropdownMenu'
import { artifactUrls } from '@/domain/artifact-links'
import type { JobView } from '@/domain/job'

export function ArtifactActions({ job }: { job: JobView }) {
  if (!job.videoKey) return null

  const items: MenuItem[] = [
    { key: 'mp4', label: 'Download MP4', href: artifactUrls.video(job.jobId) },
    ...(job.subtitlesKey
      ? [{ key: 'srt', label: 'Download subtitles (.srt)', href: artifactUrls.subtitles(job.jobId) }]
      : []),
    { key: 'scorm', label: 'Download SCORM package', href: artifactUrls.scorm(job.jobId) },
  ]

  return <DropdownMenu trigger={<Button variant="secondary">Download ▾</Button>} items={items} />
}
