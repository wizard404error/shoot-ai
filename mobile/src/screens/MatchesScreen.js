import React, { useEffect, useState } from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet, Alert } from 'react-native';
import { getMatches, saveMatch, getDb } from '../db';

export default function MatchesScreen() {
  const [matches, setMatches] = useState([]);

  useEffect(() => { loadMatches(); }, []);

  async function loadMatches() {
    const m = await getMatches();
    setMatches(m);
  }

  async function addDemoMatch() {
    const demo = {
      id: 'demo_' + Date.now(),
      name: 'FC Stars vs United Athletic',
      home_team: 'FC Stars',
      away_team: 'United Athletic',
      home_score: 2,
      away_score: 1,
      date: new Date().toISOString(),
    };
    await saveMatch(demo);
    await loadMatches();
    Alert.alert('Saved', 'Demo match added offline');
  }

  async function clearAll() {
    const db = await getDb();
    await db.runAsync('DELETE FROM matches');
    await loadMatches();
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity style={styles.btn} onPress={addDemoMatch}>
          <Text style={styles.btnText}>➕ Add Demo</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.btn, styles.btnDanger]} onPress={clearAll}>
          <Text style={styles.btnText}>🗑 Clear</Text>
        </TouchableOpacity>
      </View>
      <FlatList
        data={matches}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Text style={styles.matchName}>{item.name}</Text>
            <Text style={styles.score}>{item.home_score} - {item.away_score}</Text>
            <Text style={styles.date}>{item.date?.slice(0, 10)}</Text>
            {item.synced === 0 && <Text style={styles.unsynced}>⚠ Not synced</Text>}
          </View>
        )}
        ListEmptyComponent={<Text style={styles.empty}>No matches yet. Add a demo match to get started.</Text>}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a', padding: 12 },
  header: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  btn: { backgroundColor: '#1e7e34', padding: 10, borderRadius: 6, flex: 1, alignItems: 'center' },
  btnDanger: { backgroundColor: '#dc2626' },
  btnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  card: { backgroundColor: '#1e293b', borderRadius: 8, padding: 14, marginBottom: 8 },
  matchName: { color: '#fff', fontSize: 16, fontWeight: '700' },
  score: { color: '#1e7e34', fontSize: 24, fontWeight: '800', marginVertical: 4 },
  date: { color: '#64748b', fontSize: 12 },
  unsynced: { color: '#f59e0b', fontSize: 11, marginTop: 4 },
  empty: { color: '#64748b', textAlign: 'center', marginTop: 40, fontSize: 14 },
});
