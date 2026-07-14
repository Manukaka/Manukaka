package com.manu.mobile.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import kotlin.coroutines.resume
import kotlinx.coroutines.suspendCancellableCoroutine

/**
 * On-device speech-to-text via Android's [SpeechRecognizer]. Free, offline-capable
 * on Samsung, and understands Marathi / Hindi / English. Must be driven from the
 * main thread, so all recognizer calls are posted to the main looper.
 */
class VoiceInput(private val context: Context) {

    private val main = Handler(Looper.getMainLooper())

    /** Listens once and returns the best transcript, or null if nothing was heard. */
    suspend fun listen(languageTag: String = "mr-IN"): String? =
        suspendCancellableCoroutine { cont ->
            main.post {
                if (!SpeechRecognizer.isRecognitionAvailable(context)) {
                    if (cont.isActive) cont.resume(null)
                    return@post
                }
                val recognizer = SpeechRecognizer.createSpeechRecognizer(context)
                val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(
                        RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                        RecognizerIntent.LANGUAGE_MODEL_FREE_FORM,
                    )
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE, languageTag)
                    // Allow Hindi/English to be recognised too, not just Marathi.
                    putExtra(
                        RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE,
                        arrayListOf("mr-IN", "hi-IN", "en-IN"),
                    )
                    putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
                }

                recognizer.setRecognitionListener(object : RecognitionListener {
                    private fun finish(result: String?) {
                        recognizer.destroy()
                        if (cont.isActive) cont.resume(result)
                    }

                    override fun onResults(results: Bundle?) {
                        val list = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                        finish(list?.firstOrNull())
                    }

                    override fun onError(error: Int) = finish(null)
                    override fun onReadyForSpeech(params: Bundle?) {}
                    override fun onBeginningOfSpeech() {}
                    override fun onRmsChanged(rmsdB: Float) {}
                    override fun onBufferReceived(buffer: ByteArray?) {}
                    override fun onEndOfSpeech() {}
                    override fun onPartialResults(partialResults: Bundle?) {}
                    override fun onEvent(eventType: Int, params: Bundle?) {}
                })

                cont.invokeOnCancellation {
                    main.post { recognizer.destroy() }
                }
                recognizer.startListening(intent)
            }
        }
}
