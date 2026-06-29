import React, { useEffect, useState } from 'react';
import { View, Text, FlatList, TouchableOpacity, TextInput, StyleSheet, Alert } from 'react-native';
import { saveScoutReport, getScoutReports } from '../db';

export default function ScoutScreen() {
  const [reports, setReports] = useState([]);
  const [name, setName] = useState('');
  const [team, setTeam] = useState('');
  const [notes, setNotes] = useState('');

  useEffect(() => { loadReports(); }, []);

  async function loadReports() {
    const r = await getScoutReports();
    setReports(r);
  }

  async function addReport() {
    if (!name.trim()) { Alert.alert('Error', 'Enter a player name'); return; }
    const report = {
      id: 'scout_' + Date.now(),
      player_name: name.trim(),
      team: team.trim() || 'Unknown',
      position: 'N/A',
      rating: Math.floor(Math.random() * 5) + 6,
      notes: notes.trim(),
      photo_uri: '',
    };
    await saveScoutReport(report);
    setName('');
    setTeam('');
    setNotes('');
    await loadReports();
    Alert.alert('Saved', 'Scout report saved offline');
  }

  return (
    <View style={styles.container}>
      <View style={styles.form}>
        <TextInput style={styles.input} placeholder="Player name" placeholderTextColor="#64748b" value={name} onChangeText={setName} />
        <TextInput style={styles.input} placeholder="Team" placeholderTextColor="#64748b" value={team} onChangeText={setTeam} />
        <TextInput style={[styles.input, { height: 60 }]} placeholder="Notes" placeholderTextColor="#64748b" value={notes} onChangeText={setNotes} multiline />
        <TouchableOpacity style={styles.btn} onPress={addReport}>
          <Text style={styles.btnText}>💾 Save Report</Text>
        </TouchableOpacity>
      </View>
      <FlatList
        data={reports}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Text style={styles.name}>{item.player_name}</Text>
            <Text style={styles.team}>{item.team}</Text>
            <Text style={styles.rating}>Rating: {'⭐'.repeat(Math.floor(item.rating / 2))}</Text>
            {item.notes ? <Text style={styles.notes}>{item.notes}</Text> : null}
            {item.synced === 0 && <Text style={styles.unsynced}>⚠ Not synced</Text>}
          </View>
        )}
        ListEmptyComponent={<Text style={styles.empty}>No scout reports yet.</Text>}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a', padding: 12 },
  form: { marginBottom: 12 },
  input: { backgroundColor: '#1e293b', color: '#fff', borderRadius: 6, padding: 10, fontSize: 14, marginBottom: 8 },
  btn: { backgroundColor: '#1e7e34', padding: 12, borderRadius: 6, alignItems: 'center' },
  btnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  card: { backgroundColor: '#1e293b', borderRadius: 8, padding: 12, marginBottom: 8 },
  name: { color: '#fff', fontSize: 16, fontWeight: '700' },
  team: { color: '#64748b', fontSize: 13 },
  rating: { color: '#f59e0b', fontSize: 12, marginVertical: 2 },
  notes: { color: '#cbd5e1', fontSize: 13, marginTop: 4 },
  unsynced: { color: '#f59e0b', fontSize: 11, marginTop: 4 },
  empty: { color: '#64748b', textAlign: 'center', marginTop: 40, fontSize: 14 },
});
