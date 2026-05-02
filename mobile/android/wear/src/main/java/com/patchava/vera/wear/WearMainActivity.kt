package com.patchava.vera.wear

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.speech.RecognizerIntent
import android.speech.tts.TextToSpeech
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.wear.compose.material.Button
import androidx.wear.compose.material.ButtonDefaults
import androidx.wear.compose.material.MaterialTheme
import androidx.wear.compose.material.Text
import androidx.wear.compose.material.TimeText
import java.util.Locale

class WearMainActivity : ComponentActivity(), TextToSpeech.OnInitListener {

    private var tts: TextToSpeech? = null
    private val client = VeraWearClient()

    private var lastResponse by mutableStateOf("Tap the mic to talk to Vera")
    private var isConnected by mutableStateOf(false)
    private var isListening by mutableStateOf(false)

    private val speechLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        isListening = false
        if (result.resultCode == Activity.RESULT_OK) {
            val matches = result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            val transcript = matches?.firstOrNull() ?: return@registerForActivityResult
            client.sendTranscript(transcript)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        tts = TextToSpeech(this, this)

        val serverUrl = getServerUrl()
        client.connect(serverUrl) { response ->
            lastResponse = response
            isConnected = true
            tts?.speak(response, TextToSpeech.QUEUE_FLUSH, null, "vera_wear")
        }

        setContent {
            VeraWearScreen(
                lastResponse = lastResponse,
                isConnected = isConnected,
                isListening = isListening,
                onMicTap = { startVoiceInput() }
            )
        }
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts?.language = Locale.US
        }
    }

    private fun startVoiceInput() {
        isListening = true
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_PROMPT, "Talk to Vera")
        }
        speechLauncher.launch(intent)
    }

    private fun getServerUrl(): String {
        val prefs = getSharedPreferences("vera_config", MODE_PRIVATE)
        val baseUrl = prefs.getString("server_url", "ws://192.168.1.100:8000/ws")
            ?: "ws://192.168.1.100:8000/ws"
        val apiKey = prefs.getString("api_key", "") ?: ""
        return if (apiKey.isNotEmpty()) "$baseUrl?api_key=$apiKey" else baseUrl
    }

    override fun onDestroy() {
        tts?.shutdown()
        client.disconnect()
        super.onDestroy()
    }
}

@Composable
fun VeraWearScreen(
    lastResponse: String,
    isConnected: Boolean,
    isListening: Boolean,
    onMicTap: () -> Unit
) {
    MaterialTheme {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black),
            contentAlignment = Alignment.Center
        ) {
            TimeText()

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center
            ) {
                // Connection status
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .background(
                            color = if (isConnected) Color.Green else Color.Red,
                            shape = CircleShape
                        )
                )

                Spacer(modifier = Modifier.height(8.dp))

                // Response text
                Text(
                    text = lastResponse,
                    style = MaterialTheme.typography.body2,
                    color = Color.White,
                    textAlign = TextAlign.Center,
                    modifier = Modifier
                        .weight(1f)
                        .verticalScroll(rememberScrollState())
                )

                Spacer(modifier = Modifier.height(8.dp))

                // Mic button
                Button(
                    onClick = onMicTap,
                    modifier = Modifier.size(52.dp),
                    colors = ButtonDefaults.buttonColors(
                        backgroundColor = if (isListening) Color(0xFFFF4444) else Color(0xFF6200EE)
                    )
                ) {
                    Text(
                        text = if (isListening) "..." else "🎤",
                        style = MaterialTheme.typography.title3
                    )
                }
            }
        }
    }
}
