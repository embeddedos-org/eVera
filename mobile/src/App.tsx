import React, { useEffect, useState } from 'react';
import { StatusBar, LogBox } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import AsyncStorage from '@react-native-async-storage/async-storage';

import ChatScreen from './screens/ChatScreen';
import SettingsScreen from './screens/SettingsScreen';
import { ServerConfig } from './services/api';

LogBox.ignoreLogs(['Reanimated']);

const Stack = createNativeStackNavigator();

export default function App() {
  const [serverConfig, setServerConfig] = useState<ServerConfig | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const saved = await AsyncStorage.getItem('vera_server_config');
      if (saved) {
        setServerConfig(JSON.parse(saved));
      }
    } catch (e) {
      console.warn('Failed to load config:', e);
    }
    setLoading(false);
  };

  const saveConfig = async (config: ServerConfig) => {
    await AsyncStorage.setItem('vera_server_config', JSON.stringify(config));
    setServerConfig(config);
  };

  if (loading) return null;

  return (
    <NavigationContainer>
      <StatusBar barStyle="light-content" backgroundColor="#0a0a1a" />
      <Stack.Navigator
        initialRouteName={serverConfig ? 'Chat' : 'Settings'}
        screenOptions={{
          headerStyle: { backgroundColor: '#0a0a1a' },
          headerTintColor: '#fff',
          headerTitleStyle: { fontWeight: '600' },
          contentStyle: { backgroundColor: '#0a0a1a' },
        }}
      >
        <Stack.Screen
          name="Chat"
          options={{
            title: 'Vera',
            headerRight: () => null,
          }}
        >
          {(props) => (
            <ChatScreen
              {...props}
              serverConfig={serverConfig!}
              onOpenSettings={() => props.navigation.navigate('Settings')}
            />
          )}
        </Stack.Screen>
        <Stack.Screen name="Settings" options={{ title: 'Server Settings' }}>
          {(props) => (
            <SettingsScreen
              {...props}
              currentConfig={serverConfig}
              onSave={(config) => {
                saveConfig(config);
                props.navigation.navigate('Chat');
              }}
            />
          )}
        </Stack.Screen>
      </Stack.Navigator>
    </NavigationContainer>
  );
}
