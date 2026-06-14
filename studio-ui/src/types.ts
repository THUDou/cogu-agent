export interface WorkflowNodeData {
  type: 'start' | 'end' | 'llm' | 'tool' | 'condition' | 'code' | 'parallel' | 'human_input'
  label: string
  config: Record<string, any>
}

export interface WorkflowNode {
  id: string
  type: string
  label: string
  config: Record<string, any>
  position: { x: number; y: number }
}

export interface WorkflowEdge {
  id: string
  source: string
  target: string
  type: 'normal' | 'condition_true' | 'condition_false'
  condition: string
  label: string
}

export interface Workflow {
  id: string
  name: string
  description: string
  version: string
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  variables: Record<string, any>
  created_at: number
  updated_at: number
}

export interface WorkflowState {
  workflow_id: string
  current_node_id: string
  variables: Record<string, any>
  history: Array<{
    node_id: string
    node_type: string
    result: string
    timestamp: number
    error?: string
  }>
  status: string
  started_at: number
  completed_at: number
}

export const NODE_COLORS: Record<string, string> = {
  start: '#22c55e',
  end: '#ef4444',
  llm: '#6366f1',
  tool: '#f59e0b',
  condition: '#8b5cf6',
  code: '#06b6d4',
  parallel: '#ec4899',
  human_input: '#f97316',
}

export const NODE_LABELS: Record<string, string> = {
  start: '开始',
  end: '结束',
  llm: 'LLM 调用',
  tool: '工具调用',
  condition: '条件判断',
  code: '代码执行',
  parallel: '并行',
  human_input: '人工输入',
}
