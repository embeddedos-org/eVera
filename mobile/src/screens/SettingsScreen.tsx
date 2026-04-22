/**
 * SettingsScreen — Configure eVera server connection.
 *
 * Allows user to enter server host, port, and API key.
 * Tests connection before saving.
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
  ScrollView,
  Switch,
} from 'react-native';
import { ServerConfig, fetchHealth } from '../services/api';
import { requestAllPermissions, checkAllPermissions, PermissionType } from '../services/permissions';

interface Props {
  currentConfig: ServerConfig | null;
  onSave: (config: ServerConfig) => void;
  navigation: any;
}

export default function SettingsScreen({ currentConfig, onSave }: Props) {
  const [host, setHost] = useState(currentConfig?.host || '192.168.1.100');
  const [port, setPort] = useState(String(currentConfig?.port || 8000));
  const [apiKey, setApiKey] = useState(currentConfig?.apiKey || '');
  const [useTLS, setUseTLS] = useState(currentConfig?.useTLS || false);
  const [testing, setTesting] = useState(false);
  const [permissions, setPermissions] = useState<Record<PermissionType, boolean> | null>(null);

  const testAndSave = async () => {
    const config: ServerConfig = {
      host: host.trim(),
      port: parseInt(port, 10) || 8000,
      apiKey: apiKey.trim() || undefined,
      useTLS,
    };

    setTesting(true);
    const ok = await fetchHealth(config);
    setTesting(false);

    if (ok) {
      onSave(config);
    } else {
      Alert.alert(
        'Connection Failed',
        `Could not connect to ${config.host}:${config.port}.\n\nMake sure:\n• eVera server is running\n• Your phone is on the same network\n• VERA_SERVER_HOST=0.0.0.0 in .env`,
        [
          { text: 'Save Anyway', onPress: () => onSave(config) },
          { text: 'Try Again', style: 'cancel' },
        ]
      );
    }
  };

  const handleCheckPermissions = async () => {
    const results = await checkAllPermissions();
    setPermissions(results);
  };

  const handleRequestPermissions = async () => {
    const results = await requestAllPermissions();
    setPermissions(results);
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.sectionTitle}>🔌 Server Connection</Text>

      <Text style={styles.label}>Server IP / Hostname</Text>
      <TextInput
        style={styles.input}
        value={host}
        onChangeText={setHost}
        placeholder="192.168.1.100"
        placeholderTextColor="#555"
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
      />

      <Text style={styles.label}>Port</Text>
      <TextInput
        style={styles.input}
        value={port}
        onChangeText={setPort}
        placeholder="8000"
        placeholderTextColor="#555"
        keyboardType="numeric"
      />

      <Text style={styles.label}>API Key (optional)</Text>
      <TextInput
        style={styles.input}
        value={apiKey}
        onChangeText={setApiKey}
        placeholder="Leave empty if no auth"
        placeholderTextColor="#555"
        autoCapitalize="none"
        autoCorrect={false}
        secureTextEntry
      />

      <View style={styles.switchRow}>
        <Text style={styles.label}>Use HTTPS/WSS</Text>
        <Switch value={useTLS} onValueChange={setUseTLS} />
      </View>

      <TouchableOpacity style={styles.primaryBtn} onPress={testAndSave} disabled={testing}>
        {testing ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.primaryBtnText}>Test & Connect</Text>
        )}
      </TouchableOpacity>

      {/* Permissions section */}
      <Text style={[styles.sectionTitle, { marginTop: 32 }]}>📱 Native Permissions</Text>
      <Text style={styles.hint}>
        Grant permissions to unlock voice commands, calendar management, contacts, and more.
      </Text>

      <TouchableOpacity style={styles.secondaryBtn} onPress={handleRequestPermissions}>
        <Text style={styles.secondaryBtnText}>Grant All Permissions</Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.outlineBtn} onPress={handleCheckPermissions}>
        <Text style={styles.outlineBtnText}>Check Status</Text>
      </TouchableOpacity>

      {permissions && (
        <View style={styles.permissionsList}>
          {Object.entries(permissions).map(([key, granted]) => (
            <View key={key} style={styles.permissionRow}>
              <Text style={styles.permissionIcon}>{granted ? '✅' : '❌'}</Text>
              <Text style={styles.permissionName}>{key}</Text>
            </View>
          ))}
        </View>
      )}

      <Text style={[styles.sectionTitle, { marginTop: 32 }]}>ℹ️ Setup Guide</Text>
      <Text style={styles.hint}>
        1. On your PC, set VERA_SERVER_HOST=0.0.0.0 in .env{'\n'}
        2. Run: python main.py --mode server{'\n'}
        3. Find your PC's IP: ipconfig (Windows) or ifconfig (Mac/Linux){'\n'}
        4. Enter the IP above and tap "Test & Connect"{'\n'}
        5. Both devices must be on the same WiFi network
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0a1a',
  },
  content: {
    padding: 20,
    paddingBottom: 40,
  },
  sectionTitle: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 16,
  },
  label: {
    color: '#94a3b8',
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 6,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  input: {
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    color: '#fff',
    fontSize: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.1)',
  },
  switchRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  primaryBtn: {
    backgroundColor: '#2563eb',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 8,
  },
  primaryBtnText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
  },
  secondaryBtn: {
    backgroundColor: '#166534',
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: 'center',
    marginTop: 8,
  },
  secondaryBtnText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  outlineBtn: {
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.2)',
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: 'center',
    marginTop: 8,
  },
  outlineBtnText: {
    color: '#94a3b8',
    fontSize: 14,
    fontWeight: '600',
  },
  hint: {
    color: '#64748b',
    fontSize: 13,
    lineHeight: 20,
    marginBottom: 12,
  },
  permissionsList: {
    marginTop: 12,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderRadius: 12,
    padding: 12,
  },
  permissionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
  },
  permissionIcon: {
    fontSize: 16,
    marginRight: 10,
  },
  permissionName: {
    color: '#e2e8f0',
    fontSize: 14,
    textTransform: 'capitalize',
  },
});
