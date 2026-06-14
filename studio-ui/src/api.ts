import type { Workflow, WorkflowState } from './types'

const BASE = '/api/workflows'

export async function listWorkflows(): Promise<Workflow[]> {
  const res = await fetch(BASE)
  const data = await res.json()
  return data.workflows || []
}

export async function getWorkflow(id: string): Promise<Workflow> {
  const res = await fetch(`${BASE}/${id}`)
  if (!res.ok) throw new Error('Not found')
  return res.json()
}

export async function createWorkflow(wf: Partial<Workflow>): Promise<Workflow> {
  const res = await fetch(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: wf.name || 'Untitled',
      description: wf.description || '',
      nodes: wf.nodes || [],
      edges: wf.edges || [],
      variables: wf.variables || {},
    }),
  })
  return res.json()
}

export async function updateWorkflow(id: string, wf: Partial<Workflow>): Promise<Workflow> {
  const res = await fetch(`${BASE}/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(wf),
  })
  if (!res.ok) throw new Error('Update failed')
  return res.json()
}

export async function deleteWorkflow(id: string): Promise<void> {
  await fetch(`${BASE}/${id}`, { method: 'DELETE' })
}

export async function runWorkflow(id: string, variables: Record<string, any> = {}): Promise<WorkflowState> {
  const res = await fetch(`${BASE}/${id}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ variables }),
  })
  return res.json()
}

export async function getMermaid(id: string): Promise<string> {
  const res = await fetch(`${BASE}/${id}/mermaid`)
  const data = await res.json()
  return data.mermaid || ''
}

export async function validateWorkflow(id: string): Promise<{ valid: boolean; errors: string[] }> {
  const res = await fetch(`${BASE}/${id}/validate`)
  return res.json()
}
