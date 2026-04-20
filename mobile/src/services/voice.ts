/**
 * Voice service — speech-to-text and text-to-speech for eVoca mobile.
 *
 * Uses @react-native-community/voice for STT and react-native-tts for TTS.
 * Handles native microphone permission and provides a simple API.
 */

import Voice, {
  SpeechResultsEvent,
  SpeechErrorEvent,
  SpeechStartEvent,
  SpeechEndEvent,
} from '@react-native-voice/voice';
import Tts from 'react-native-tts';
import { requestPermission } from './permissions';

type VoiceResultHandler = (text: string) => void;
type VoiceStateHandler = (listening: boolean) => void;

class VoiceService {
  private onResult: VoiceResultHandler | null = null;
  private onStateChange: VoiceStateHandler | null = null;
  private isListening = false;
  private initialized = false;

  async initialize() {
    if (this.initialized) return;

    // Set up STT callbacks
    Voice.onSpeechStart = this.handleSpeechStart;
    Voice.onSpeechEnd = this.handleSpeechEnd;
    Voice.onSpeechResults = this.handleSpeechResults;
    Voice.onSpeechError = this.handleSpeechError;

    // Configure TTS
    try {
      await Tts.setDefaultLanguage('en-US');
      await Tts.setDefaultRate(0.5);
      await Tts.setDefaultPitch(1.0);
    } catch (e) {
      console.warn('TTS setup warning:', e);
    }

    this.initialized = true;
  }

  setOnResult(handler: VoiceResultHandler) {
    this.onResult = handler;
  }

  setOnStateChange(handler: VoiceStateHandler) {
    this.onStateChange = handler;
  }

  async startListening(): Promise<boolean> {
    const hasPermission = await requestPermission('microphone');
    if (!hasPermission) return false;

    try {
      await this.initialize();
      await Voice.start('en-US');
      this.isListening = true;
      this.onStateChange?.(true);
      return true;
    } catch (e) {
      console.error('Voice start error:', e);
      return false;
    }
  }

  async stopListening() {
    try {
      await Voice.stop();
      this.isListening = false;
      this.onStateChange?.(false);
    } catch (e) {
      console.warn('Voice stop error:', e);
    }
  }

  async cancelListening() {
    try {
      await Voice.cancel();
      this.isListening = false;
      this.onStateChange?.(false);
    } catch (e) {
      console.warn('Voice cancel error:', e);
    }
  }

  get listening(): boolean {
    return this.isListening;
  }

  async speak(text: string) {
    try {
      // Strip emoji for cleaner TTS
      const clean = text.replace(/[\u{1F600}-\u{1F9FF}]/gu, '').trim();
      if (clean) {
        await Tts.speak(clean);
      }
    } catch (e) {
      console.warn('TTS error:', e);
    }
  }

  async stopSpeaking() {
    try {
      await Tts.stop();
    } catch (e) {
      console.warn('TTS stop error:', e);
    }
  }

  async destroy() {
    try {
      await Voice.destroy();
      this.initialized = false;
    } catch (e) {
      console.warn('Voice destroy error:', e);
    }
  }

  // --- Internal handlers ---

  private handleSpeechStart = (e: SpeechStartEvent) => {
    this.isListening = true;
    this.onStateChange?.(true);
  };

  private handleSpeechEnd = (e: SpeechEndEvent) => {
    this.isListening = false;
    this.onStateChange?.(false);
  };

  private handleSpeechResults = (e: SpeechResultsEvent) => {
    const text = e.value?.[0];
    if (text) {
      this.onResult?.(text);
    }
  };

  private handleSpeechError = (e: SpeechErrorEvent) => {
    console.warn('Speech error:', e.error);
    this.isListening = false;
    this.onStateChange?.(false);
  };
}

export const voiceService = new VoiceService();
