/**
 * Push notification service for eVoca mobile.
 *
 * Uses Firebase Cloud Messaging (FCM) for Android and APNs for iOS.
 * Handles token registration, incoming notifications, and local notifications.
 */

import { Platform } from 'react-native';
import messaging from '@react-native-firebase/messaging';
import PushNotification from 'react-native-push-notification';
import { requestPermission } from './permissions';

class NotificationService {
  private initialized = false;
  private fcmToken: string | null = null;

  async initialize() {
    if (this.initialized) return;

    // Configure local notification channels (Android)
    PushNotification.createChannel(
      {
        channelId: 'voca-alerts',
        channelName: 'Voca Alerts',
        channelDescription: 'Proactive alerts from Voca (reminders, stock alerts, calendar)',
        importance: 4,
        vibrate: true,
      },
      () => {}
    );

    PushNotification.configure({
      onNotification: (notification) => {
        console.log('[Notification] Received:', notification);
      },
      permissions: {
        alert: true,
        badge: true,
        sound: true,
      },
      popInitialNotification: true,
      requestPermissions: false,
    });

    // Request notification permission
    await requestPermission('notifications');

    // Get FCM token
    try {
      const authStatus = await messaging().requestPermission();
      const enabled =
        authStatus === messaging.AuthorizationStatus.AUTHORIZED ||
        authStatus === messaging.AuthorizationStatus.PROVISIONAL;

      if (enabled) {
        this.fcmToken = await messaging().getToken();
        console.log('[FCM] Token:', this.fcmToken);
      }
    } catch (e) {
      console.warn('[FCM] Token registration failed:', e);
    }

    // Handle foreground messages
    messaging().onMessage(async (remoteMessage) => {
      console.log('[FCM] Foreground message:', remoteMessage);
      this.showLocalNotification(
        remoteMessage.notification?.title || 'Voca',
        remoteMessage.notification?.body || '',
      );
    });

    // Handle background/quit messages
    messaging().setBackgroundMessageHandler(async (remoteMessage) => {
      console.log('[FCM] Background message:', remoteMessage);
    });

    this.initialized = true;
  }

  get token(): string | null {
    return this.fcmToken;
  }

  showLocalNotification(title: string, message: string, data?: object) {
    PushNotification.localNotification({
      channelId: 'voca-alerts',
      title,
      message,
      playSound: true,
      vibrate: true,
      userInfo: data || {},
    });
  }

  scheduleNotification(title: string, message: string, date: Date) {
    PushNotification.localNotificationSchedule({
      channelId: 'voca-alerts',
      title,
      message,
      date,
      allowWhileIdle: true,
    });
  }

  cancelAll() {
    PushNotification.cancelAllLocalNotifications();
  }
}

export const notificationService = new NotificationService();
