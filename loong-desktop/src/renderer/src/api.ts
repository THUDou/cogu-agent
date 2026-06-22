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