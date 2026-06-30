const API_BASE = `http://127.0.0.1:8198/api`;

export interface Skill {
  name: string;
  description: string;
  source: string;
}

export interface Settings {
  api_base_url: string;
  model: string;
  provider: string;
  pangu_mini_enabled: boolean;
  pangu_mini_backend: string;
  pangu_mini_api_port: number;
}

export interface PanguStatus {
  model_available: boolean;
  server_running: boolean;
  model_size_mb: number | null;
  backends: { transformers: boolean; gguf: boolean };
}

export interface Plugin {
  plugin_id: string;
  name: string;
  description: string;
  version: string;
  tool_count: number;
  category: string;
  tags: string[];
}

export interface NodeTypeDef {
  type: string;
  display_key: string;
  category: string;
  description: string;
  icon: string;
  color: string;
  is_composite: boolean;
}

export interface TraceSpan {
  trace_id: string;
  span_id: string;
  span_type: string;
  span_name: string;
  duration: number;
  status_code: string;
  start_time: number;
}

export interface MetricsSummary {
  [key: string]: any;
}

export interface EvalResult {
  avg_score: number;
  pass_rate: number;
  evaluated_items: number;
  total_items: number;
}

export interface KnowledgeDoc {
  doc_id: string;
  content: string;
  score: number;
  source: string;
}

export async function fetchSkills(): Promise<Skill[]> {
  const res = await fetch(`${API_BASE}/skills`);
  const data = await res.json();
  return data.skills || [];
}

export async function fetchTools(): Promise<Skill[]> {
  const res = await fetch(`${API_BASE}/tools`);
  const data = await res.json();
  return data.tools || [];
}

export async function fetchSettings(): Promise<Settings> {
  const res = await fetch(`${API_BASE}/settings`);
  return res.json();
}

export async function saveSettings(settings: Partial<Settings>): Promise<Settings> {
  const res = await fetch(`${API_BASE}/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });
  return res.json();
}

export async function setApiKey(provider: string, apiKey: string, baseUrl?: string, model?: string) {
  await fetch(`${API_BASE}/settings/api-key`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider, api_key: apiKey, base_url: baseUrl, model }),
  });
}

export async function fetchPanguStatus(): Promise<PanguStatus> {
  const res = await fetch(`${API_BASE}/settings/pangu/status`);
  return res.json();
}

export async function panguStart() {
  await fetch(`${API_BASE}/settings/pangu/start`, { method: 'POST' });
}

export async function panguStop() {
  await fetch(`${API_BASE}/settings/pangu/stop`, { method: 'POST' });
}

export async function checkOnboarding(): Promise<{ needs_onboarding: boolean }> {
  const res = await fetch(`${API_BASE}/settings/onboarding`);
  return res.json();
}

export async function streamChat(message: string, sessionId: string, model?: string): Promise<ReadableStream<Uint8Array>> {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId, model }),
  });
  return res.body!;
}

export async function fetchPlugins(): Promise<Plugin[]> {
  const res = await fetch(`${API_BASE}/plugins`);
  const data = await res.json();
  return data.plugins || [];
}

export async function registerPlugin(name: string, openapiDoc: any): Promise<any> {
  const res = await fetch(`${API_BASE}/plugins`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, openapi_doc: openapiDoc }),
  });
  return res.json();
}

export async function executePluginTool(pluginId: string, toolId: string, args: any = {}): Promise<any> {
  const res = await fetch(`${API_BASE}/plugins/${pluginId}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tool_id: toolId, args }),
  });
  return res.json();
}

export async function fetchNodeTypes(category?: string): Promise<NodeTypeDef[]> {
  const url = category ? `${API_BASE}/node-types?category=${category}` : `${API_BASE}/node-types`;
  const res = await fetch(url);
  const data = await res.json();
  return data.node_types || [];
}

export async function convertCanvas(canvas: any): Promise<any> {
  const res = await fetch(`${API_BASE}/node-types/canvas/convert`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(canvas),
  });
  return res.json();
}

export async function fetchTraces(traceId?: string, limit: number = 50): Promise<TraceSpan[]> {
  const url = traceId ? `${API_BASE}/observability/traces?trace_id=${traceId}&limit=${limit}` : `${API_BASE}/observability/traces?limit=${limit}`;
  const res = await fetch(url);
  const data = await res.json();
  return data.spans || [];
}

export async function fetchMetricsSummary(hours: number = 24): Promise<MetricsSummary> {
  const res = await fetch(`${API_BASE}/observability/metrics/summary?hours=${hours}`);
  return res.json();
}

export async function fetchModelMetrics(model?: string): Promise<any> {
  const url = model ? `${API_BASE}/observability/metrics/model?model=${model}` : `${API_BASE}/observability/metrics/model`;
  const res = await fetch(url);
  return res.json();
}

export async function fetchPipelineStats(): Promise<any> {
  const res = await fetch(`${API_BASE}/observability/pipeline/stats`);
  return res.json();
}

export async function fetchBuiltinEvaluators(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/evaluators/builtins`);
  const data = await res.json();
  return data.evaluators || [];
}

export async function runEvaluation(evaluatorIds: string[], items: any[]): Promise<EvalResult> {
  const res = await fetch(`${API_BASE}/evaluators/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ evaluator_ids: evaluatorIds, items }),
  });
  return res.json();
}

export async function knowledgeRetrieve(query: string, topK: number = 5): Promise<KnowledgeDoc[]> {
  const res = await fetch(`${API_BASE}/knowledge/retrieve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_k: topK }),
  });
  const data = await res.json();
  return data.documents || [];
}

export async function knowledgeIndex(knowledgeId: string, documents: any[]): Promise<any> {
  const res = await fetch(`${API_BASE}/knowledge/index`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ knowledge_id: knowledgeId, documents }),
  });
  return res.json();
}
