import React, { useEffect, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Text, View, ActivityIndicator, StyleSheet } from 'react-native';

import LoginScreen from './src/screens/LoginScreen';
import MatchesScreen from './src/screens/MatchesScreen';
import ScoutScreen from './src/screens/ScoutScreen';
import SyncScreen from './src/screens/SyncScreen';

const Tab = createBottomTabNavigator();

export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { getMe } = require('./src/api');
        const u = await getMe();
        setUser(u);
      } catch (e) {
        setUser(null);
      }
      setLoading(false);
    })();
  }, []);

  if (loading) {
    return (
      <View style={styles.container}>
        <ActivityIndicator size="large" color="#1e7e34" />
        <StatusBar style="light" />
      </View>
    );
  }

  if (!user) {
    return <LoginScreen onLogin={(u) => setUser(u)} />;
  }

  return (
    <SafeAreaProvider>
      <NavigationContainer>
        <Tab.Navigator
          screenOptions={{
            headerStyle: { backgroundColor: '#0f172a' },
            headerTintColor: '#fff',
            tabBarStyle: { backgroundColor: '#0f172a', borderTopColor: '#1e293b' },
            tabBarActiveTintColor: '#1e7e34',
            tabBarInactiveTintColor: '#64748b',
          }}
        >
          <Tab.Screen name="Matches" component={MatchesScreen} options={{ tabBarLabel: 'Matches', tabBarIcon: () => <Text>⚽</Text> }} />
          <Tab.Screen name="Scout" component={ScoutScreen} options={{ tabBarLabel: 'Scout', tabBarIcon: () => <Text>🔎</Text> }} />
          <Tab.Screen name="Sync" component={SyncScreen} options={{ tabBarLabel: 'Sync', tabBarIcon: () => <Text>🔄</Text> }} />
        </Tab.Navigator>
      </NavigationContainer>
      <StatusBar style="light" />
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a', alignItems: 'center', justifyContent: 'center' },
});
