package com.manu.mobile.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer

/**
 * Experimental hands-free wake word. Continuously runs the on-device recogniser and
 * fires [onWake] when the user says "Manu" (मनु). Any words after the wake word are
 * passed along as the command. This uses Android's SpeechRecognizer in a restart loop
 * — fine for a trial, but battery-hungry; a dedicated wake-word engine is a later step.
 *
 * The caller should [stop] it while a task runs (so it doesn't fight for the mic) and
 * [start] it again afterwards.
 */
class WakeListener(
    private val context: Context,
    private val onWake: (command: String?) -> Unit,
) {
    private val main = Handler(Looper.getMainLooper())
    private var recognizer: SpeechRecognizer? = null
    private var active = false

    private val wakeWords = listOf("manu", "मनु", "मानू", "मनू")

    fun start() {
        if (active) return
        active = true
        main.post { listenOnce() }
    }

    fun stop() {
        active = false
        main.post {
            recognizer?.destroy()
            recognizer = null
        }
    }

    private fun restartSoon() {
        if (!active) return
        main.postDelayed({ listenOnce() }, 400)
    }

    private fun listenOnce() {
        if (!active) return
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            active = false
            return
        }
        recognizer?.destroy()
        val r = SpeechRecognizer.createSpeechRecognizer(context)
        recognizer = r
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "mr-IN")
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, arrayListOf("mr-IN", "hi-IN", "en-IN"))
        }

        r.setRecognitionListener(object : RecognitionListener {
            override fun onResults(results: Bundle?) {
                val heard = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull()?.trim().orEmpty()
                val command = matchWake(heard)
                if (command != null) {
                    active = false            // pause the loop; caller restarts after the task
                    recognizer?.destroy(); recognizer = null
                    onWake(command.ifBlank { null })
                } else {
                    restartSoon()
                }
            }

            override fun onError(error: Int) = restartSoon()
            override fun onReadyForSpeech(params: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onPartialResults(partialResults: Bundle?) {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })
        r.startListening(intent)
    }

    /** Returns the command after the wake word, "" if only the wake word, or null if absent. */
    private fun matchWake(heard: String): String? {
        val lower = heard.lowercase()
        val hit = wakeWords.firstOrNull { lower.contains(it) } ?: return null
        val idx = lower.indexOf(hit)
        return heard.substring(idx + hit.length).trim().trimStart(',', '।', '.', ' ')
    }
}
