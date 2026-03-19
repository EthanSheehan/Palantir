const API_BASE = '';  // empty — Vite proxy handles /api/* to localhost:8000

export async function fetchTheaters(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/api/theaters`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return data.theaters;
}

export async function switchTheater(theater: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/theater`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ theater }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}
