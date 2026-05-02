package com.patchava.vera.auto

import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class VeraAutoClient {

    private var webSocket: WebSocket? = null
    private val httpClient = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .pingInterval(30, TimeUnit.SECONDS)
        .build()

    private var onResponseCallback: ((String) -> Unit)? = null

    fun connect(serverUrl: String, onResponse: (String) -> Unit) {
        onResponseCallback = onResponse

        val request = Request.Builder()
            .url(serverUrl)
            .addHeader("X-Vera-Client", "android_auto")
            .build()

        webSocket = httpClient.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                val hello = JSONObject().apply {
                    put("type", "hello")
                    put("client", "android_auto")
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
                Thread.sleep(3000)
                connect(serverUrl, onResponse)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                // Don't reconnect on auth/zone denial (4001) or rate limit (4029)
                if (code != 4001 && code != 4029) {
                    Thread.sleep(3000)
                    connect(serverUrl, onResponse)
                }
            }
        })
    }

    fun sendTranscript(text: String) {
        val message = JSONObject().apply {
            put("type", "transcript")
            put("data", text)
        }
        webSocket?.send(message.toString())
    }

    fun disconnect() {
        webSocket?.close(1000, "Client closing")
        httpClient.dispatcher.executorService.shutdown()
    }
}
