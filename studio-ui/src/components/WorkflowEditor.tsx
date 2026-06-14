import React, { useState, useCallback, useRef, useMemo } from 'react'
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  addEdge,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
  type Node,
  type Edge,
  type Connection,
  type NodeProps,
  type NodeTypes,
  BackgroundVariant,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import type { Workflow, WorkflowNode, WorkflowEdge } from '../types'
import { NODE_COLORS, NODE_LABELS } from '../types'
import { listWorkflows, createWorkflow, deleteWorkflow, runWorkflow, getMermaid, validateWorkflow } from '../api'

function toFlowNodes(wf: Workflow): Node[] {
  return wf.nodes.map((n) => ({
    id: n.id,
    type: 'workflowNode',
    position: n.position || { x: 0, y: 0 },
    data: { label: n.label || NODE_LABELS[n.type] || n.type, nodeType: n.type, config: n.config },
  }))
}

function toFlowEdges(wf: Workflow): Edge[] {
  return wf.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.label || (e.type === 'condition_true' ? 'Yes' : e.type === 'condition_false' ? 'No' : ''),
    style: e.type === 'condition_false' ? { stroke: '#ef4444' } : e.type === 'condition_true' ? { stroke: '#22c55e' } : {},
    animated: e.type !== 'normal',
  }))
}

function toWorkflowEdges(edges: Edge[]): WorkflowEdge[] {
  return edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    type: (e.label === 'Yes' ? 'condition_true' : e.label === 'No' ? 'condition_false' : 'normal') as any,
    condition: '',
    label: typeof e.label === 'string' ? e.label : '',
  }))
}

function WorkflowNodeComponent({ data }: NodeProps) {
  const nodeType = (data as any).nodeType as string
  const color = NODE_COLORS[nodeType] || '#666'
  const label = (data as any).label as string

  return (
    <div
      style={{
        padding: '10px 16px',
        borderRadius: '8px',
        border: `2px solid ${color}`,
        background: `${color}15`,
        minWidth: '100px',
        textAlign: 'center',
        fontSize: '13px',
        fontWeight: 500,
        cursor: 'grab',
      }}
    >
      {nodeType !== 'start' && <Handle type="target" position={Position.Top} style={{ background: color }} />}
      <div style={{ color, marginBottom: 2, fontSize: '11px', opacity: 0.7 }}>{NODE_LABELS[nodeType] || nodeType}</div>
      <div>{label}</div>
      {nodeType !== 'end' && <Handle type="source" position={Position.Bottom} style={{ background: color }} />}
    </div>
  )
}

const nodeTypes: NodeTypes = { workflowNode: WorkflowNodeComponent }

const NODE_PALETTE = ['start', 'llm', 'tool', 'condition', 'code', 'human_input', 'end']

export default function WorkflowEditor() {
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [current, setCurrent] = useState<Workflow | null>(null)
  const [nodes, setNodes, onNodesChange] = useNodesState([] as Node[])
  const [edges, setEdges, onEdgesChange] = useEdgesState([] as Edge[])
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [mermaid, setMermaid] = useState('')
  const [status, setStatus] = useState('')
  const [runResult, setRunResult] = useState<any>(null)
  const reactFlowWrapper = useRef<HTMLDivElement>(null)

  const loadWorkflows = useCallback(async () => {
    try {
      const list = await listWorkflows()
      setWorkflows(list)
    } catch {
      setStatus('无法连接后端，请先启动 cogu serve')
    }
  }, [])

  const selectWorkflow = useCallback(async (wf: Workflow) => {
    setCurrent(wf)
    setNodes(toFlowNodes(wf))
    setEdges(toFlowEdges(wf))
    setMermaid('')
    setRunResult(null)
    setSelectedNode(null)
  }, [setNodes, setEdges])

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => addEdge({ ...connection, animated: true }, eds))
    },
    [setEdges]
  )

  const onNodeClick = useCallback((_: any, node: Node) => {
    setSelectedNode(node)
  }, [])

  const addNode = useCallback(
    (type: string) => {
      const id = `node_${Date.now()}`
      const newNode: Node = {
        id,
        type: 'workflowNode',
        position: { x: 250, y: (nodes.length + 1) * 100 },
        data: { label: NODE_LABELS[type] || type, nodeType: type, config: {} },
      }
      setNodes((nds) => [...nds, newNode])
    },
    [nodes, setNodes]
  )

  const saveWorkflow = useCallback(async () => {
    if (!current) return
    const wf: Partial<Workflow> = {
      ...current,
      nodes: nodes.map((n) => ({
        id: n.id,
        type: (n.data as any).nodeType,
        label: (n.data as any).label,
        config: (n.data as any).config || {},
        position: n.position,
      })),
      edges: toWorkflowEdges(edges),
    }
    try {
      await createWorkflow(wf)
      setStatus('保存成功')
      loadWorkflows()
    } catch (e: any) {
      setStatus(`保存失败: ${e.message}`)
    }
  }, [current, nodes, edges, loadWorkflows])

  const handleRun = useCallback(async () => {
    if (!current) return
    setStatus('运行中...')
    try {
      const result = await runWorkflow(current.id)
      setRunResult(result)
      setStatus(`运行完成: ${result.status}`)
    } catch (e: any) {
      setStatus(`运行失败: ${e.message}`)
    }
  }, [current])

  const handleValidate = useCallback(async () => {
    if (!current) return
    try {
      const result = await validateWorkflow(current.id)
      setStatus(result.valid ? '验证通过' : `验证失败: ${result.errors.join(', ')}`)
    } catch (e: any) {
      setStatus(`验证错误: ${e.message}`)
    }
  }, [current])

  const handleMermaid = useCallback(async () => {
    if (!current) return
    try {
      const m = await getMermaid(current.id)
      setMermaid(m)
    } catch {}
  }, [current])

  const deleteSelected = useCallback(() => {
    if (!selectedNode) return
    setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id))
    setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id))
    setSelectedNode(null)
  }, [selectedNode, setNodes, setEdges])

  return (
    <div style={{ display: 'flex', height: '100vh', fontFamily: 'sans-serif' }}>
      {/* Left Panel: Workflow List + Node Palette */}
      <div style={{ width: 240, borderRight: '1px solid #e5e7eb', display: 'flex', flexDirection: 'column', background: '#f9fafb' }}>
        <div style={{ padding: 12, borderBottom: '1px solid #e5e7eb' }}>
          <h3 style={{ margin: 0, fontSize: 14 }}>COGU Studio</h3>
          <button onClick={loadWorkflows} style={{ marginTop: 8, width: '100%', padding: '6px 0', cursor: 'pointer' }}>刷新列表</button>
        </div>
        <div style={{ flex: 1, overflow: 'auto', padding: 8 }}>
          {workflows.map((wf) => (
            <div
              key={wf.id}
              onClick={() => selectWorkflow(wf)}
              style={{
                padding: '8px 10px',
                marginBottom: 4,
                borderRadius: 6,
                cursor: 'pointer',
                background: current?.id === wf.id ? '#dbeafe' : 'white',
                border: '1px solid #e5e7eb',
                fontSize: 13,
              }}
            >
              <div style={{ fontWeight: 600 }}>{wf.name || 'Untitled'}</div>
              <div style={{ fontSize: 11, color: '#6b7280' }}>{wf.nodes?.length || 0} 节点 · {wf.edges?.length || 0} 边</div>
            </div>
          ))}
          {workflows.length === 0 && <div style={{ color: '#9ca3af', fontSize: 13, textAlign: 'center', marginTop: 20 }}>暂无工作流</div>}
        </div>
        <div style={{ padding: 8, borderTop: '1px solid #e5e7eb' }}>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: '#374151' }}>节点面板 (点击添加)</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {NODE_PALETTE.map((type) => (
              <button
                key={type}
                onClick={() => addNode(type)}
                style={{
                  padding: '4px 8px',
                  fontSize: 11,
                  borderRadius: 4,
                  border: `1px solid ${NODE_COLORS[type]}`,
                  background: `${NODE_COLORS[type]}15`,
                  color: NODE_COLORS[type],
                  cursor: 'pointer',
                }}
              >
                {NODE_LABELS[type]}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Center: ReactFlow Canvas */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '8px 16px', borderBottom: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', gap: 8, background: 'white' }}>
          <input
            value={current?.name || ''}
            onChange={(e) => current && setCurrent({ ...current, name: e.target.value })}
            placeholder="工作流名称"
            style={{ flex: 1, padding: '6px 10px', border: '1px solid #d1d5db', borderRadius: 4, fontSize: 14, fontWeight: 600 }}
          />
          <button onClick={saveWorkflow} style={{ padding: '6px 14px', background: '#22c55e', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}>保存</button>
          <button onClick={handleRun} style={{ padding: '6px 14px', background: '#6366f1', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}>运行</button>
          <button onClick={handleValidate} style={{ padding: '6px 14px', background: '#f59e0b', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}>验证</button>
          <button onClick={handleMermaid} style={{ padding: '6px 14px', background: '#8b5cf6', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}>Mermaid</button>
          <span style={{ fontSize: 12, color: '#6b7280' }}>{status}</span>
        </div>
        <div ref={reactFlowWrapper} style={{ flex: 1 }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            nodeTypes={nodeTypes}
            fitView
            snapToGrid
            snapGrid={[15, 15]}
          >
            <Controls />
            <MiniMap />
            <Background variant={BackgroundVariant.Dots} gap={15} size={1} />
          </ReactFlow>
        </div>
      </div>

      {/* Right Panel: Properties + Mermaid + Run Result */}
      <div style={{ width: 300, borderLeft: '1px solid #e5e7eb', display: 'flex', flexDirection: 'column', background: '#f9fafb', overflow: 'auto' }}>
        {selectedNode ? (
          <div style={{ padding: 12 }}>
            <h4 style={{ margin: '0 0 8px', fontSize: 13 }}>节点属性</h4>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 8 }}>ID: {selectedNode.id}</div>
            <label style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>标签</label>
            <input
              value={(selectedNode.data as any)?.label || ''}
              onChange={(e) => {
                const label = e.target.value
                setNodes((nds) => nds.map((n) => n.id === selectedNode.id ? { ...n, data: { ...n.data, label } } : n))
              }}
              style={{ width: '100%', padding: '6px 8px', border: '1px solid #d1d5db', borderRadius: 4, fontSize: 13, marginBottom: 8 }}
            />
            {(selectedNode.data as any)?.nodeType === 'llm' && (
              <>
                <label style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>Prompt</label>
                <textarea
                  value={(selectedNode.data as any)?.config?.prompt || ''}
                  onChange={(e) => {
                    const config = { ...(selectedNode.data as any).config, prompt: e.target.value }
                    setNodes((nds) => nds.map((n) => n.id === selectedNode.id ? { ...n, data: { ...n.data, config } } : n))
                  }}
                  rows={4}
                  style={{ width: '100%', padding: '6px 8px', border: '1px solid #d1d5db', borderRadius: 4, fontSize: 13, resize: 'vertical' }}
                />
              </>
            )}
            {(selectedNode.data as any)?.nodeType === 'tool' && (
              <>
                <label style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>工具名</label>
                <input
                  value={(selectedNode.data as any)?.config?.tool || ''}
                  onChange={(e) => {
                    const config = { ...(selectedNode.data as any).config, tool: e.target.value }
                    setNodes((nds) => nds.map((n) => n.id === selectedNode.id ? { ...n, data: { ...n.data, config } } : n))
                  }}
                  style={{ width: '100%', padding: '6px 8px', border: '1px solid #d1d5db', borderRadius: 4, fontSize: 13 }}
                />
              </>
            )}
            {(selectedNode.data as any)?.nodeType === 'condition' && (
              <>
                <label style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>条件表达式</label>
                <input
                  value={(selectedNode.data as any)?.config?.condition || ''}
                  onChange={(e) => {
                    const config = { ...(selectedNode.data as any).config, condition: e.target.value }
                    setNodes((nds) => nds.map((n) => n.id === selectedNode.id ? { ...n, data: { ...n.data, config } } : n))
                  }}
                  style={{ width: '100%', padding: '6px 8px', border: '1px solid #d1d5db', borderRadius: 4, fontSize: 13 }}
                />
              </>
            )}
            {(selectedNode.data as any)?.nodeType === 'code' && (
              <>
                <label style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>代码</label>
                <textarea
                  value={(selectedNode.data as any)?.config?.code || ''}
                  onChange={(e) => {
                    const config = { ...(selectedNode.data as any).config, code: e.target.value }
                    setNodes((nds) => nds.map((n) => n.id === selectedNode.id ? { ...n, data: { ...n.data, config } } : n))
                  }}
                  rows={6}
                  style={{ width: '100%', padding: '6px 8px', border: '1px solid #d1d5db', borderRadius: 4, fontSize: 13, fontFamily: 'monospace', resize: 'vertical' }}
                />
              </>
            )}
            <button onClick={deleteSelected} style={{ marginTop: 12, width: '100%', padding: '6px 0', background: '#ef4444', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}>删除节点</button>
          </div>
        ) : (
          <div style={{ padding: 12, color: '#9ca3af', fontSize: 13 }}>点击节点查看属性</div>
        )}
        {mermaid && (
          <div style={{ padding: 12, borderTop: '1px solid #e5e7eb' }}>
            <h4 style={{ margin: '0 0 8px', fontSize: 13 }}>Mermaid 图</h4>
            <pre style={{ background: 'white', padding: 8, borderRadius: 4, fontSize: 11, overflow: 'auto', border: '1px solid #e5e7eb' }}>{mermaid}</pre>
          </div>
        )}
        {runResult && (
          <div style={{ padding: 12, borderTop: '1px solid #e5e7eb' }}>
            <h4 style={{ margin: '0 0 8px', fontSize: 13 }}>运行结果</h4>
            <div style={{ fontSize: 12 }}>
              <div>状态: <b>{runResult.status}</b></div>
              <div>耗时: {runResult.completed_at ? `${((runResult.completed_at - runResult.started_at) * 1000).toFixed(0)}ms` : '-'}</div>
              {runResult.history?.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  {runResult.history.map((h: any, i: number) => (
                    <div key={i} style={{ padding: '4px 0', borderBottom: '1px solid #e5e7eb' }}>
                      <span style={{ color: h.error ? '#ef4444' : '#22c55e' }}>{h.error ? '✗' : '✓'}</span>
                      {' '}{h.node_type}: {h.result?.slice(0, 60) || h.error}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
