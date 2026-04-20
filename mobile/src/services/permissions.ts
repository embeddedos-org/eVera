/**
 * Native permissions manager for eVoca mobile.
 *
 * Handles runtime permission requests for Android and iOS with
 * user-friendly explanations for each permission.
 */

import { Platform, Alert, Linking } from 'react-native';
import {
  check,
  request,
  PERMISSIONS,
  RESULTS,
  Permission,
  openSettings,
} from 'react-native-permissions';

export type PermissionType =
  | 'microphone'
  | 'camera'
  | 'contacts'
  | 'calendar'
  | 'location'
  | 'notifications';

const PERMISSION_MAP: Record<PermissionType, { android: Permission; ios: Permission }> = {
  microphone: {
    android: PERMISSIONS.ANDROID.RECORD_AUDIO,
    ios: PERMISSIONS.IOS.MICROPHONE,
  },
  camera: {
    android: PERMISSIONS.ANDROID.CAMERA,
    ios: PERMISSIONS.IOS.CAMERA,
  },
  contacts: {
    android: PERMISSIONS.ANDROID.READ_CONTACTS,
    ios: PERMISSIONS.IOS.CONTACTS,
  },
  calendar: {
    android: PERMISSIONS.ANDROID.READ_CALENDAR,
    ios: PERMISSIONS.IOS.CALENDARS,
  },
  location: {
    android: PERMISSIONS.ANDROID.ACCESS_FINE_LOCATION,
    ios: PERMISSIONS.IOS.LOCATION_WHEN_IN_USE,
  },
  notifications: {
    android: PERMISSIONS.ANDROID.POST_NOTIFICATIONS,
    ios: PERMISSIONS.IOS.NOTIFICATIONS,
  },
};

const PERMISSION_DESCRIPTIONS: Record<PermissionType, string> = {
  microphone: 'Voca needs microphone access for voice commands. Speak naturally and Voca will understand!',
  camera: 'Voca can use your camera for visual analysis — tell it "what do you see?" to try it.',
  contacts: 'Voca can help manage your contacts — "call Mom" or "text John" becomes possible.',
  calendar: 'Voca can read and create calendar events — "schedule a meeting tomorrow at 3pm".',
  location: 'Voca can provide location-aware assistance — "find restaurants near me".',
  notifications: 'Voca sends proactive alerts — reminders, calendar warnings, stock price alerts.',
};

function getPlatformPermission(type: PermissionType): Permission {
  const map = PERMISSION_MAP[type];
  return Platform.OS === 'ios' ? map.ios : map.android;
}

export async function checkPermission(type: PermissionType): Promise<boolean> {
  try {
    const permission = getPlatformPermission(type);
    const result = await check(permission);
    return result === RESULTS.GRANTED;
  } catch {
    return false;
  }
}

export async function requestPermission(type: PermissionType): Promise<boolean> {
  try {
    const permission = getPlatformPermission(type);
    const status = await check(permission);

    if (status === RESULTS.GRANTED) return true;

    if (status === RESULTS.DENIED) {
      const result = await request(permission);
      return result === RESULTS.GRANTED;
    }

    if (status === RESULTS.BLOCKED) {
      Alert.alert(
        `${type.charAt(0).toUpperCase() + type.slice(1)} Permission Required`,
        `${PERMISSION_DESCRIPTIONS[type]}\n\nThis permission was previously denied. Please enable it in Settings.`,
        [
          { text: 'Cancel', style: 'cancel' },
          { text: 'Open Settings', onPress: () => openSettings() },
        ]
      );
      return false;
    }

    return false;
  } catch (e) {
    console.warn(`Permission request failed for ${type}:`, e);
    return false;
  }
}

export async function requestAllPermissions(): Promise<Record<PermissionType, boolean>> {
  const types: PermissionType[] = ['microphone', 'notifications', 'camera', 'contacts', 'calendar', 'location'];
  const results: Record<string, boolean> = {};

  for (const type of types) {
    results[type] = await requestPermission(type);
  }

  return results as Record<PermissionType, boolean>;
}

export async function checkAllPermissions(): Promise<Record<PermissionType, boolean>> {
  const types: PermissionType[] = ['microphone', 'notifications', 'camera', 'contacts', 'calendar', 'location'];
  const results: Record<string, boolean> = {};

  for (const type of types) {
    results[type] = await checkPermission(type);
  }

  return results as Record<PermissionType, boolean>;
}
