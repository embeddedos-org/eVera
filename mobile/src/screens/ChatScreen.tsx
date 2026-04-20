/**
 * ChatScreen — Main voice-first chat interface for eVoca mobile.
 *
 * Features: animated mic button, message bubbles with agent badges,
 * streaming text display, confirmation flow, haptic feedback.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  Animated,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  Vibration,
} from 'react-native';
import { ServerConfig, VocaWebSocket, ChatMessage, VocaResponse } from '../services/api';
import { voiceService } from '../services/voice';

interface Props {
  serverConfig: ServerConfig;
  onOpenSettings: () => void;
  navigation: any;
}

const MOOD_COLORS: Record<string, string> = {
  happy: '#4ade80',
  excited: '#facc15',
  thinking: '#60a5fa',
  empathetic: '#c084fc',
  error: '#f87171',
  neutral: '#94a3b8',
};

const AGENT_EMOJI: Record<string, string> = {
  companion: '💬',
  operator: '💻',
  browser: '🌐',
  researcher: '🔍',
  writer: '✍️',
  life_manager: '📅',
  home_controller: '🏠',
  income: '📈',
  coder: '💻',
  git: '📦',
  system: '⚙️',
  scheduler: '⏰',
  tier0: '⚡',
};

export default function ChatScreen({ serverConfig, onOpenSettings }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [connected, setConnected] = useState(false);
  const [listening, setListening] = useState(false);
  const [streamingText, setStreamingText] = useState('');

  const wsRef = useRef<VocaWebSocket | null>(null);
  const flatListRef = useRef<FlatList>(null);
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const msgIdCounter = useRef(0);

  const newMsgId = () => `msg-${++msgIdCounter.current}-${Date.now()}`;

  // ─── WebSocket setup ───

  useEffect(() => {
    const ws = new VocaWebSocket(serverConfig);

    ws.onConnection = (isConnected) => {
      setConnected(isConnected);
    };

    ws.onMessage = (msg: VocaResponse) => {
      addAssistantMessage(msg);
      if (msg.mood !== 'error') {
        voiceService.speak(msg.response);
      }
    };

    ws.onStreamToken = (token: string) => {
      setStreamingText((prev) => prev + token);
    };

    ws.onStreamEnd = (msg: VocaResponse) => {
      setStreamingText('');
      addAssistantMessage(msg);
      voiceService.speak(msg.response);
    };

    ws.connect();
    wsRef.current = ws;

    // Init voice service
    voiceService.initialize();
    voiceService.setOnResult((text) => {
      setListening(false);
      if (text.trim()) {
        sendMessage(text);
      }
    });
    voiceService.setOnStateChange(setListening);

    return () => {
      ws.disconnect();
      voiceService.destroy();
    };
  }, [serverConfig]);

  // ─── Mic pulse animation ───

  useEffect(() => {
    if (listening) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, { toValue: 1.3, duration: 600, useNativeDriver: true }),
          Animated.timing(pulseAnim, { toValue: 1, duration: 600, useNativeDriver: true }),
        ])
      ).start();
    } else {
      pulseAnim.setValue(1);
    }
  }, [listening]);

  // ─── Helpers ───

  const addAssistantMessage = useCallback((msg: VocaResponse) => {
    const chatMsg: ChatMessage = {
      id: newMsgId(),
      role: 'assistant',
      content: msg.response,
      agent: msg.agent,
      tier: msg.tier,
      intent: msg.intent,
      mood: msg.mood,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, chatMsg]);
    Vibration.vibrate(50);
    setTimeout(() => flatListRef.current?.scrollToEnd({ animated: true }), 100);
  }, []);

  const sendMessage = useCallback((text: string) => {
    if (!text.trim() || !wsRef.current) return;

    const userMsg: ChatMessage = {
      id: newMsgId(),
      role: 'user',
      content: text.trim(),
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);
    wsRef.current.send(text.trim(), false);
    setInputText('');
    Keyboard.dismiss();
    setTimeout(() => flatListRef.current?.scrollToEnd({ animated: true }), 100);
  }, []);

  const toggleMic = async () => {
    if (listening) {
      await voiceService.stopListening();
    } else {
      await voiceService.startListening();
    }
  };

  // ─── Render ───

  const renderMessage = ({ item }: { item: ChatMessage }) => {
    const isUser = item.role === 'user';
    const moodColor = MOOD_COLORS[item.mood || 'neutral'] || MOOD_COLORS.neutral;
    const agentEmoji = AGENT_EMOJI[item.agent || ''] || '🤖';

    return (
      <View style={[styles.messageBubble, isUser ? styles.userBubble : styles.assistantBubble]}>
        {!isUser && (
          <View style={styles.agentBadge}>
            <Text style={styles.agentEmoji}>{agentEmoji}</Text>
            <Text style={[styles.agentName, { color: moodColor }]}>{item.agent}</Text>
          </View>
        )}
        <Text style={[styles.messageText, isUser && styles.userText]}>{item.content}</Text>
        <Text style={styles.timestamp}>
          {new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </Text>
      </View>
    );
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={90}
    >
      {/* Connection status */}
      <View style={[styles.statusBar, { backgroundColor: connected ? '#166534' : '#991b1b' }]}>
        <Text style={styles.statusText}>
          {connected ? '● Connected' : '○ Disconnected'}
        </Text>
        <TouchableOpacity onPress={onOpenSettings}>
          <Text style={styles.settingsBtn}>⚙️</Text>
        </TouchableOpacity>
      </View>

      {/* Messages */}
      <FlatList
        ref={flatListRef}
        data={messages}
        keyExtractor={(item) => item.id}
        renderItem={renderMessage}
        contentContainerStyle={styles.messageList}
        onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: true })}
      />

      {/* Streaming indicator */}
      {streamingText ? (
        <View style={[styles.messageBubble, styles.assistantBubble, styles.streamingBubble]}>
          <Text style={styles.messageText}>{streamingText}▊</Text>
        </View>
      ) : null}

      {/* Input area */}
      <View style={styles.inputArea}>
        <TextInput
          style={styles.textInput}
          value={inputText}
          onChangeText={setInputText}
          placeholder="Type a message..."
          placeholderTextColor="#666"
          onSubmitEditing={() => sendMessage(inputText)}
          returnKeyType="send"
        />

        {inputText.trim() ? (
          <TouchableOpacity style={styles.sendBtn} onPress={() => sendMessage(inputText)}>
            <Text style={styles.sendBtnText}>➤</Text>
          </TouchableOpacity>
        ) : (
          <Animated.View style={{ transform: [{ scale: pulseAnim }] }}>
            <TouchableOpacity
              style={[styles.micBtn, listening && styles.micBtnActive]}
              onPress={toggleMic}
            >
              <Text style={styles.micIcon}>{listening ? '⏹' : '🎙️'}</Text>
            </TouchableOpacity>
          </Animated.View>
        )}
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0a1a',
  },
  statusBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 6,
  },
  statusText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '600',
  },
  settingsBtn: {
    fontSize: 20,
  },
  messageList: {
    paddingHorizontal: 12,
    paddingBottom: 8,
  },
  messageBubble: {
    maxWidth: '82%',
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 10,
    marginVertical: 4,
  },
  userBubble: {
    alignSelf: 'flex-end',
    backgroundColor: '#1d4ed8',
  },
  assistantBubble: {
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.12)',
  },
  streamingBubble: {
    marginHorizontal: 12,
    marginBottom: 4,
  },
  agentBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  agentEmoji: {
    fontSize: 14,
    marginRight: 4,
  },
  agentName: {
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  messageText: {
    color: '#e2e8f0',
    fontSize: 15,
    lineHeight: 21,
  },
  userText: {
    color: '#fff',
  },
  timestamp: {
    color: 'rgba(255,255,255,0.35)',
    fontSize: 10,
    marginTop: 4,
    alignSelf: 'flex-end',
  },
  inputArea: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.08)',
  },
  textInput: {
    flex: 1,
    height: 44,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderRadius: 22,
    paddingHorizontal: 16,
    color: '#fff',
    fontSize: 15,
    marginRight: 8,
  },
  sendBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#2563eb',
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendBtnText: {
    color: '#fff',
    fontSize: 20,
  },
  micBtn: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: '#2563eb',
    justifyContent: 'center',
    alignItems: 'center',
  },
  micBtnActive: {
    backgroundColor: '#dc2626',
  },
  micIcon: {
    fontSize: 24,
  },
});
