import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getAgents, getAgent, updateAgent, deleteAgent } from '../api/agents'
import { useAgentStore } from '../stores/agentStore'
import { useEffect } from 'react'

export function useAgents() {
  const setAgents = useAgentStore((s) => s.setAgents)
  const agents = useAgentStore((s) => s.agentsArray)
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['agents'],
    queryFn: getAgents,
    staleTime: Infinity,
    refetchInterval: 30_000, // polling fallback when WS is disconnected
  })
  useEffect(() => { if (data) setAgents(data) }, [data, setAgents])
  return { agents: data ? agents : [], isLoading, error, refetch }
}

export function useAgent(id: string) {
  return useQuery({ queryKey: ['agent', id], queryFn: () => getAgent(id), enabled: !!id })
}

export function useUpdateAgent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      updateAgent(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agents'] }),
  })
}

export function useDeleteAgent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteAgent,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agents'] }),
  })
}
