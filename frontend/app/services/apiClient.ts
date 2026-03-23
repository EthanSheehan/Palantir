/**
 * Typed AMS REST API Client
 * Uses Vite proxy — no hardcoded host:port.
 */
import type { Asset, Mission, Task, Command, TimelineReservation, Alert, Recommendation, Aimpoint, Target, HistoricalSnapshot } from '../store/types';

const BASE = '/api/v1';

async function _fetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.detail || err.error?.message || res.statusText);
  }
  return res.json();
}

function _params(filters: Record<string, string>): string {
  const params = new URLSearchParams(filters).toString();
  return params ? '?' + params : '';
}

// ── Assets ──

export function listAssets(filters: Record<string, string> = {}) {
  return _fetch<{ assets: Asset[] }>(`/assets${_params(filters)}`);
}

export function getAsset(id: string) {
  return _fetch<Asset>(`/assets/${id}`);
}

// ── Missions ──

export function listMissions(filters: Record<string, string> = {}) {
  return _fetch<{ missions: Mission[] }>(`/missions${_params(filters)}`);
}

export function getMission(id: string) {
  return _fetch<Mission>(`/missions/${id}`);
}

export function createMission(data: { name: string; type: string; priority: string; objective?: string }) {
  return _fetch<Mission>('/missions', { method: 'POST', body: JSON.stringify(data) });
}

export function proposeMission(id: string) {
  return _fetch<Mission>(`/missions/${id}/propose`, { method: 'POST' });
}

export function approveMission(id: string, approvedBy = 'operator') {
  return _fetch<Mission>(`/missions/${id}/approve`, {
    method: 'POST',
    body: JSON.stringify({ approved_by: approvedBy }),
  });
}

export function pauseMission(id: string) {
  return _fetch<Mission>(`/missions/${id}/pause`, { method: 'POST' });
}

export function resumeMission(id: string) {
  return _fetch<Mission>(`/missions/${id}/resume`, { method: 'POST' });
}

export function abortMission(id: string) {
  return _fetch<Mission>(`/missions/${id}/abort`, { method: 'POST' });
}

// ── Tasks ──

export function listTasks(missionId: string) {
  return _fetch<{ tasks: Task[] }>(`/missions/${missionId}/tasks`);
}

export function createTask(missionId: string, data: Partial<Task>) {
  return _fetch<Task>(`/missions/${missionId}/tasks`, { method: 'POST', body: JSON.stringify(data) });
}

// ── Commands ──

export function listCommands(filters: Record<string, string> = {}) {
  return _fetch<{ commands: Command[] }>(`/commands${_params(filters)}`);
}

export function createCommand(data: Partial<Command>) {
  return _fetch<Command>('/commands', { method: 'POST', body: JSON.stringify(data) });
}

export function approveCommand(id: string, approvedBy = 'operator') {
  return _fetch<Command>(`/commands/${id}/approve`, {
    method: 'POST',
    body: JSON.stringify({ approved_by: approvedBy }),
  });
}

export function cancelCommand(id: string) {
  return _fetch<Command>(`/commands/${id}/cancel`, { method: 'POST' });
}

// ── Timeline ──

export function listReservations(filters: Record<string, string> = {}) {
  return _fetch<{ reservations: TimelineReservation[] }>(`/timeline${_params(filters)}`);
}

export function listConflicts() {
  return _fetch<{ conflicts: unknown[] }>('/timeline/conflicts');
}

// ── Alerts ──

export function listAlerts(filters: Record<string, string> = {}) {
  return _fetch<{ alerts: Alert[] }>(`/alerts${_params(filters)}`);
}

export function acknowledgeAlert(id: string) {
  return _fetch<Alert>(`/alerts/${id}/acknowledge`, { method: 'POST' });
}

export function clearAlert(id: string) {
  return _fetch<Alert>(`/alerts/${id}/clear`, { method: 'POST' });
}

// ── Macro-grid ──

export function getZones() {
  return _fetch<{ zones: unknown[] }>('/macrogrid/zones');
}

export function getRecommendations() {
  return _fetch<{ recommendations: Recommendation[] }>('/macrogrid/recommendations');
}

export function convertRecommendation(recId: string) {
  return _fetch<Mission>(`/macrogrid/recommendations/${recId}/convert`, { method: 'POST' });
}

// ── Aimpoints ──

export function listAimpoints(filters: Record<string, string> = {}) {
  return _fetch<{ aimpoints: Aimpoint[] }>(`/aimpoints${_params(filters)}`);
}

export function createAimpoint(data: { lon: number; lat: number; type?: string; description?: string }) {
  return _fetch<Aimpoint>('/aimpoints', { method: 'POST', body: JSON.stringify(data) });
}

export function updateAimpoint(id: string, data: Partial<Aimpoint>) {
  return _fetch<Aimpoint>(`/aimpoints/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export function deleteAimpoint(id: string) {
  return _fetch<{ ok: boolean }>(`/aimpoints/${id}`, { method: 'DELETE' });
}

// ── Targets ──

export function listTargets(filters: Record<string, string> = {}) {
  return _fetch<{ targets: Target[] }>(`/targets${_params(filters)}`);
}

export function createTarget(data: { name: string; description?: string; aimpoint_ids: string[] }) {
  return _fetch<Target>('/targets', { method: 'POST', body: JSON.stringify(data) });
}

export function updateTargetEntity(id: string, data: Partial<Target>) {
  return _fetch<Target>(`/targets/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export function deleteTarget(id: string) {
  return _fetch<{ ok: boolean }>(`/targets/${id}`, { method: 'DELETE' });
}

export function addAimpointToTarget(targetId: string, aimpointId: string) {
  return _fetch<Target>(`/targets/${targetId}/aimpoints?aimpoint_id=${encodeURIComponent(aimpointId)}`, { method: 'POST' });
}

export function removeAimpointFromTarget(targetId: string, aimpointId: string) {
  return _fetch<Target>(`/targets/${targetId}/aimpoints/${aimpointId}`, { method: 'DELETE' });
}

// ── Historical State ──

export function getStateAtTime(isoTimestamp: string) {
  return _fetch<HistoricalSnapshot>(`/timeline/state?at=${encodeURIComponent(isoTimestamp)}`);
}

// ── Events ──

export function queryEvents(filters: Record<string, string> = {}) {
  return _fetch<{ events: unknown[] }>(`/events${_params(filters)}`);
}
