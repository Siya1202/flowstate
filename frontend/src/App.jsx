import { useCallback, useEffect, useMemo, useState } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Position,
  MarkerType,
  useEdgesState,
  useNodesState,
} from 'reactflow'
import 'reactflow/dist/style.css'
import './App.css'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

function statusClass(status) {
  if (status === 'done') return 'status-done'
  if (status === 'blocked') return 'status-blocked'
  if (status === 'in_progress') return 'status-progress'
  return 'status-open'
}

function TaskNode({ data }) {
  return (
    <div className={`task-node ${data.isCritical ? 'critical' : ''} ${data.isStale ? 'stale' : ''}`}>
      <div className="node-header">
        <span className={`status-pill ${statusClass(data.status)}`}>{data.status.replace('_', ' ')}</span>
        {data.isCritical ? <span className="badge badge-critical">critical</span> : null}
        {data.isStale ? <span className="badge badge-stale">stale blocker</span> : null}
      </div>
      <h3>{data.label}</h3>
      <p>Owner: {data.owner || 'Unassigned'}</p>
      <p>Deadline: {data.deadline || 'No deadline'}</p>
      <p>
        Blocks: {data.outDegree} | Depends on: {data.inDegree}
      </p>
    </div>
  )
}

const nodeTypes = { task: TaskNode }

function App() {
  const [teamId, setTeamId] = useState('team_alpha')
  const [inputTeamId, setInputTeamId] = useState('team_alpha')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [summary, setSummary] = useState(null)
  const [selectedNodeId, setSelectedNodeId] = useState(null)
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])

  const selectedNode = useMemo(() => nodes.find((node) => node.id === selectedNodeId), [nodes, selectedNodeId])

  const loadGraph = useCallback(async (currentTeamId) => {
    setLoading(true)
    setError('')
    try {
      const response = await fetch(`${API_BASE}/graph/${encodeURIComponent(currentTeamId)}/viewer`)
      if (!response.ok) {
        throw new Error(`Graph endpoint returned ${response.status}`)
      }

      const payload = await response.json()
      setSummary(payload.summary)

      const rfNodes = payload.nodes.map((node, index) => ({
        id: node.id,
        type: 'task',
        data: {
          label: node.label,
          owner: node.owner,
          deadline: node.deadline,
          status: node.status,
          isCritical: node.is_critical,
          isStale: node.is_stale_blocker,
          outDegree: node.out_degree,
          inDegree: node.in_degree,
        },
        position: {
          x: 120 + (index % 4) * 300,
          y: 120 + Math.floor(index / 4) * 210,
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      }))

      const rfEdges = payload.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        animated: edge.is_critical,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: edge.is_critical ? '#f04770' : '#4e5b6e',
        },
        style: {
          strokeWidth: edge.is_critical ? 3 : 1.8,
          stroke: edge.is_critical ? '#f04770' : '#4e5b6e',
        },
        label: edge.type,
      }))

      setNodes(rfNodes)
      setEdges(rfEdges)
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : 'Failed to load graph')
      setNodes([])
      setEdges([])
      setSummary(null)
    } finally {
      setLoading(false)
    }
  }, [setEdges, setNodes])

  useEffect(() => {
    loadGraph(teamId)
  }, [teamId, loadGraph])

  return (
    <main className="page">
      <header className="topbar">
        <div>
          <p className="eyebrow">Flowstate Sprint 2</p>
          <h1>Live DAG Viewer</h1>
          <p className="subtitle">Critical path and stale blockers are highlighted directly on the graph.</p>
        </div>
        <form
          className="team-form"
          onSubmit={(event) => {
            event.preventDefault()
            setTeamId(inputTeamId.trim() || 'team_alpha')
          }}
        >
          <label htmlFor="teamId">Team</label>
          <input
            id="teamId"
            value={inputTeamId}
            onChange={(event) => setInputTeamId(event.target.value)}
            placeholder="team_alpha"
          />
          <button type="submit">Load Graph</button>
        </form>
      </header>

      <section className="stats-grid">
        <article>
          <p>Total Tasks</p>
          <h2>{summary?.total_tasks ?? 0}</h2>
        </article>
        <article>
          <p>Total Dependencies</p>
          <h2>{summary?.total_dependencies ?? 0}</h2>
        </article>
        <article>
          <p>Critical Chain Length</p>
          <h2>{summary?.critical_path?.length ?? 0}</h2>
        </article>
        <article>
          <p>Stale Blockers</p>
          <h2>{summary?.stale_blockers?.length ?? 0}</h2>
        </article>
      </section>

      <section className="viewer-layout">
        <div className="canvas">
          {loading ? <p className="state">Loading DAG...</p> : null}
          {error ? <p className="state error">{error}</p> : null}
          {!loading && !error ? (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={(_, node) => setSelectedNodeId(node.id)}
              fitView
              fitViewOptions={{ padding: 0.15 }}
              nodeTypes={nodeTypes}
              attributionPosition="bottom-left"
            >
              <MiniMap pannable zoomable />
              <Controls />
              <Background variant="dots" gap={18} size={1.1} />
            </ReactFlow>
          ) : null}
        </div>

        <aside className="detail-panel">
          <h2>Node Detail</h2>
          {!selectedNode ? <p>Select a node to inspect its details.</p> : null}
          {selectedNode ? (
            <div className="detail-content">
              <h3>{selectedNode.data.label}</h3>
              <p>Status: {selectedNode.data.status.replace('_', ' ')}</p>
              <p>Owner: {selectedNode.data.owner || 'Unassigned'}</p>
              <p>Deadline: {selectedNode.data.deadline || 'No deadline'}</p>
              <p>Dependencies: {selectedNode.data.inDegree}</p>
              <p>Unblocks: {selectedNode.data.outDegree}</p>
              <p>Critical Path: {selectedNode.data.isCritical ? 'Yes' : 'No'}</p>
              <p>Stale Blocker: {selectedNode.data.isStale ? 'Yes' : 'No'}</p>
            </div>
          ) : null}
        </aside>
      </section>
    </main>
  )
}

export default App
