package com.manu.mobile.voice

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import java.util.Locale
import java.util.concurrent.atomic.AtomicInteger
import kotlin.coroutines.resume
import kotlinx.coroutines.suspendCancellableCoroutine

/**
 * Speaks Manu's replies aloud using Android [TextToSpeech]. Prefers Marathi, falls
 * back to Hindi then the device default if a voice isn't installed.
 */
class Speaker(context: Context) {

    private val ready = kotlinx.coroutines.CompletableDeferred<Boolean>()
    private val counter = AtomicInteger(0)

    private val tts = TextToSpeech(context.applicationContext) { status ->
        if (status == TextToSpeech.SUCCESS) {
            val ok = trySetLanguage(Locale("mr", "IN")) ||
                trySetLanguage(Locale("hi", "IN")) ||
                trySetLanguage(Locale.getDefault())
            ready.complete(ok)
        } else {
            ready.complete(false)
        }
    }

    private fun trySetLanguage(locale: Locale): Boolean {
        val r = tts.setLanguage(locale)
        return r != TextToSpeech.LANG_MISSING_DATA && r != TextToSpeech.LANG_NOT_SUPPORTED
    }

    suspend fun speak(text: String) {
        if (text.isBlank()) return
        ready.await()
        val id = "manu-${counter.incrementAndGet()}"
        suspendCancellableCoroutine<Unit> { cont ->
            tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {}
                override fun onDone(utteranceId: String?) {
                    if (utteranceId == id && cont.isActive) cont.resume(Unit)
                }

                override fun onError(utteranceId: String?) {
                    if (utteranceId == id && cont.isActive) cont.resume(Unit)
                }

                override fun onError(utteranceId: String?, errorCode: Int) {
                    if (utteranceId == id && cont.isActive) cont.resume(Unit)
                }
            })
            tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, id)
        }
    }

    fun shutdown() {
        tts.stop()
        tts.shutdown()
    }
}
