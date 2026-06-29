import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, FlatList, StyleSheet, Alert } from 'react-native';
import { getMe, syncPush, logout } from '../api';
import { getUnsynced, clearSyncQueue } from '../db';

export default function SyncScreen() {
  const [user, setUser] = useState(null);
  const [unsynced, setUnsynced] = useState([]);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    getMe().then(setUser).catch(() => setUser(null));
    loadUnsynced();
  }, []);

  async function loadUnsynced() {
    const items = await getUnsynced();
    setUnsynced(items);
  }

  async function handleSync() {
    setSyncing(true);
    try {
      const items = await getUnsynced();
      if (items.length === 0) { Alert.alert('Sync', 'Nothing to sync'); setSyncing(false); return; }
      const ops = items.map(i => ({
        op: 'update',
        entity_type: i.entity_type,
        entity_id: i.entity_id,
        data: JSON.parse(i.data),
      }));
      const res = await syncPush('mobile-' + Date.now(), ops);
      await clearSyncQueue();
      await loadUnsynced();
      Alert.alert('Sync Complete', `Synced ${res.operations?.length || 0} items`);
    } catch (e) {
      Alert.alert('Sync Error', e.message);
    }
    setSyncing(false);
  }

  async function handleLogout() {
    await logout();
    Alert.alert('Logged Out', 'Please restart the app');
  }

  return (
    <View style={styles.container}>
      {user && <Text style={styles.user}>👤 {user.display_name || user.username}</Text>}
      <TouchableOpacity style={styles.syncBtn} onPress={handleSync} disabled={syncing}>
        <Text style={styles.syncBtnText}>{syncing ? '⏳ Syncing...' : `🔄 Sync (${unsynced.length} pending)`}</Text>
      </TouchableOpacity>
      <FlatList
        data={unsynced}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <View style={styles.item}>
            <Text style={styles.itemType}>{item.entity_type}</Text>
            <Text style={styles.itemOp}>{item.operation}</Text>
            <Text style={styles.itemId}>{item.entity_id.slice(0, 20)}</Text>
          </View>
        )}
        ListEmptyComponent={<Text style={styles.empty}>All data synced ✅</Text>}
      />
      <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
        <Text style={styles.logoutText}>🚪 Log Out</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a', padding: 12 },
  user: { color: '#fff', fontSize: 16, fontWeight: '700', textAlign: 'center', marginBottom: 12 },
  syncBtn: { backgroundColor: '#1e7e34', padding: 14, borderRadius: 8, alignItems: 'center', marginBottom: 12 },
  syncBtnText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  item: { flexDirection: 'row', gap: 8, padding: 8, borderBottomWidth: 1, borderBottomColor: '#1e293b' },
  itemType: { color: '#1e7e34', fontWeight: '600', fontSize: 13, minWidth: 60 },
  itemOp: { color: '#64748b', fontSize: 13, minWidth: 40 },
  itemId: { color: '#64748b', fontSize: 11, flex: 1 },
  empty: { color: '#64748b', textAlign: 'center', marginTop: 40, fontSize: 14 },
  logoutBtn: { marginTop: 'auto', padding: 12, alignItems: 'center' },
  logoutText: { color: '#dc2626', fontSize: 14, fontWeight: '600' },
});
