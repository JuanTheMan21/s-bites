import { useQuery } from '@tanstack/react-query'
import { fetchSceneTree } from '@/adapters/scene-adapter'

export function useSegmentSceneQuery(jobId: string, index: number | null) {
  return useQuery({
    queryKey: ['job', jobId, 'segments', index, 'scene'],
    queryFn: () => fetchSceneTree(jobId, index!),
    enabled: index !== null,
  })
}
