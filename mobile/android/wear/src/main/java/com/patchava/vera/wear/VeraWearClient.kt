package com.patchava.vera.wear

import android.content.Context
import android.content.SharedPreferences
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import kotlin.math.min

class VeraWearClient {

    private var webSocket: WebSocket? = null
    private val httpClient = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .pingInterval(30, TimeUnit.SECONDS)
        .build()

    private var onResponseCallback: ((String) -> Unit)? = null
    private var serverUrl: String = ""
    private var reconnectAttempt = 0
    private var shouldReconnect = true

    fun connect(url: String, onResponse: (String) -> Unit) {
        serverUrl = url
        onResponseCallback = onResponse
        shouldReconnect = true
        reconnectAttempt = 0
        doConnect()
    }

    private fun doConnect() {
        val request = Request.Builder()
            .url(serverUrl)
            .build()

        val request = Request.Builder()
            .url(serverUrl)
            .addHeader("X-Vera-Client", "wear_os")
            .build()

        webSocket = httpClient.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                reconnectAttempt = 0
                val hello = JSONObject().apply {
                    put("type", "hello")
                    put("client", "wear_os")
                    put("version", "1.0.3")
                }
                webSocket.send(hello.toString())
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val json = JSONObject(text)
                    val type = json.optString("type", "")
                    if (type == "response" || type == "agent_response") {
                        val content = json.optString("data",
                            json.optString("message", ""))
                        if (content.isNotEmpty()) {
                            onResponseCallback?.invoke(content)
                        }
                    }
                } catch (e: Exception) {
                    // Ignore malformed messages
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                if (shouldReconnect) {
                    reconnectWithBackoff()
                }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                // Don't reconnect on auth/zone denial (4001) or rate limit (4029)
                if (shouldReconnect && code != 4001 && code != 4029) {
                    reconnectWithBackoff()
                }
            }
        })
    }

    private fun reconnectWithBackoff() {
        reconnectAttempt++
        val delayMs = min(30000L, (1000L * (1L shl min(reconnectAttempt, 5))))
        Thread {
            Thread.sleep(delayMs)
            if (shouldReconnect) {
                doConnect()
            }
        }.start()
    }

    fun sendTranscript(text: String) {
        val message = JSONObject().apply {
            put("type", "transcript")
            put("data", text)
        }
        webSocket?.send(message.toString())
    }

    fun disconnect() {
        shouldReconnect = false
        webSocket?.close(1000, "Client closing")
        httpClient.dispatcher.executorService.shutdown()
    }
}
