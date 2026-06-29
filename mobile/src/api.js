import axios from 'axios';
import * as SecureStore from 'expo-secure-store';

const CLOUD_URL = 'http://localhost:8741';

const api = axios.create({ baseURL: CLOUD_URL, timeout: 10000 });

api.interceptors.request.use(async (config) => {
  const token = await SecureStore.getItemAsync('kawkab_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export async function login(email, password) {
  const res = await api.post('/auth/login', { email, password });
  await SecureStore.setItemAsync('kawkab_token', res.data.access_token);
  return res.data;
}

export async function register(username, email, password) {
  const res = await api.post('/auth/register', { username, email, password });
  await SecureStore.setItemAsync('kawkab_token', res.data.access_token);
  return res.data;
}

export async function logout() {
  await SecureStore.deleteItemAsync('kawkab_token');
}

export async function getMe() {
  const res = await api.get('/auth/me');
  return res.data;
}

export async function syncPush(deviceId, operations) {
  const res = await api.post('/sync/push', { device_id: deviceId, operations });
  return res.data;
}

export async function syncPull(deviceId) {
  const res = await api.post('/sync/pull', { device_id: deviceId, operations: [] });
  return res.data;
}

export async function listTeams() {
  const res = await api.get('/teams');
  return res.data;
}

export async function createTeam(name) {
  const res = await api.post('/teams', { name });
  return res.data;
}

export async function addMarker(streamId, label) {
  const res = await api.post(`/sync/marker/${streamId}`, { label });
  return res.data;
}

export default api;
