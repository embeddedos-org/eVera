package com.patchava.vera.auto

import android.content.Context
import android.speech.tts.TextToSpeech
import androidx.car.app.CarContext
import androidx.car.app.Screen
import androidx.car.app.model.Action
import androidx.car.app.model.ActionStrip
import androidx.car.app.model.CarIcon
import androidx.car.app.model.MessageTemplate
import androidx.car.app.model.Template
import androidx.core.graphics.drawable.IconCompat
import java.util.Locale

class VeraCarScreen(
    carContext: CarContext,
    private val client: VeraAutoClient
) : Screen(carContext), TextToSpeech.OnInitListener {

    private var tts: TextToSpeech? = null
    private val messages = mutableListOf<Pair<String, String>>() // role, content
    private var isListening = false

    init {
        tts = TextToSpeech(carContext, this)

        val prefs = carContext.getSharedPreferences("vera_config", Context.MODE_PRIVATE)
        val serverUrl = prefs.getString("server_url", "ws://192.168.1.100:8000/ws") ?: "ws://192.168.1.100:8000/ws"
        val apiKey = prefs.getString("api_key", "") ?: ""
        val wsUrl = if (apiKey.isNotEmpty()) "$serverUrl?api_key=$apiKey" else serverUrl

        client.connect(wsUrl) { response ->
            messages.add("vera" to response)
            if (messages.size > 5) messages.removeAt(0)
            tts?.speak(response, TextToSpeech.QUEUE_FLUSH, null, "vera_response")
            invalidate()
        }
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts?.language = Locale.US
        }
    }

    override fun onGetTemplate(): Template {
        val lastMessage = messages.lastOrNull()?.second ?: "Hi! I'm Vera. Tap the mic to talk."

        return MessageTemplate.Builder(lastMessage)
            .setTitle("eVera")
            .setHeaderAction(Action.APP_ICON)
            .setActionStrip(
                ActionStrip.Builder()
                    .addAction(
                        Action.Builder()
                            .setTitle(if (isListening) "Listening..." else "🎤 Talk")
                            .setOnClickListener { startVoiceInput() }
                            .build()
                    )
                    .build()
            )
            .build()
    }

    private fun startVoiceInput() {
        isListening = true
        invalidate()

        val recognizerIntent = android.content.Intent(
            android.speech.RecognizerIntent.ACTION_RECOGNIZE_SPEECH
        ).apply {
            putExtra(
                android.speech.RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                android.speech.RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
            )
            putExtra(android.speech.RecognizerIntent.EXTRA_PROMPT, "Talk to Vera")
        }

        carContext.startActivity(recognizerIntent)
    }

    fun onSpeechResult(transcript: String) {
        isListening = false
        messages.add("user" to transcript)
        if (messages.size > 5) messages.removeAt(0)
        client.sendTranscript(transcript)
        invalidate()
    }

    override fun onDestroy(owner: androidx.lifecycle.LifecycleOwner) {
        tts?.shutdown()
        client.disconnect()
        super.onDestroy(owner)
    }
}
