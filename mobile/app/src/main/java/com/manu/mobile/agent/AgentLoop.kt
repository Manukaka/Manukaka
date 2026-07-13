package com.manu.mobile.agent

import android.content.Context
import com.manu.mobile.accessibility.Actuator
import com.manu.mobile.accessibility.ManuAccessibilityService
import com.manu.mobile.accessibility.ScreenReader
import com.manu.mobile.voice.Speaker
import com.manu.mobile.voice.VoiceInput
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext

/**
 * The observe -> ask backend -> act loop. Given a spoken goal it drives the phone
 * until the task is done, the user is asked something, or a budget/safety limit hits.
 */
class AgentLoop(
    private val context: Context,
    private val backend: BackendClient,
    private val voice: VoiceInput,
    private val speaker: Speaker,
    private val deviceId: String,
    private val onStatus: (String) -> Unit,
) {
    private val maxSteps = 40

    private val yesWords = setOf(
        "हो", "हा", "होय", "हां", "haan", "ha", "yes", "yeah", "ok", "okay",
        "ठीक", "चालेल", "करा", "kar", "karo", "kara",
    )

    suspend fun run(goal: String) = withContext(Dispatchers.IO) {
        val service = ManuAccessibilityService.instance
        if (service == null) {
            speaker.speak("मला फोन चालवण्याची परवानगी नाही. कृपया Settings मध्ये Manu ला Accessibility परवानगी द्या.")
            onStatus("Accessibility off")
            return@withContext
        }

        val history = ArrayList<String>()
        var pendingReply: String? = null
        var step = 0

        while (step < maxSteps) {
            onStatus("thinking… (step ${step + 1})")
            val obs = ScreenReader.capture(service)

            val action = try {
                backend.step(deviceId, goal, obs, step, history, pendingReply)
            } catch (e: BackendException) {
                speaker.speak("Server शी संपर्क होत नाही आहे. थोड्या वेळाने पुन्हा प्रयत्न करा.")
                onStatus("backend error ${e.code}")
                return@withContext
            } catch (e: Exception) {
                speaker.speak("काहीतरी अडचण आली. पुन्हा प्रयत्न करा.")
                onStatus("error: ${e.message}")
                return@withContext
            }
            pendingReply = null
            step++

            // Confirm risky actions before doing them.
            if (action.needsConfirmation) {
                val question = action.say ?: "हे करू का?"
                speaker.speak(question)
                onStatus("confirm: $question")
                val reply = voice.listen()
                if (reply == null || yesWords.none { reply.lowercase().contains(it) }) {
                    history.add("user declined: $question")
                    speaker.speak("ठीक आहे, ते केलं नाही.")
                    continue
                }
                history.add("user confirmed: $question")
            }

            when (action.type) {
                AgentAction.DONE -> {
                    action.say?.let { speaker.speak(it) }
                    onStatus("done")
                    return@withContext
                }

                AgentAction.ASK_USER -> {
                    val q = action.say ?: "काय करू?"
                    speaker.speak(q)
                    onStatus("listening…")
                    pendingReply = voice.listen()
                    history.add("asked: $q -> ${pendingReply ?: "(no reply)"}")
                }

                AgentAction.READ_ALOUD -> {
                    action.say?.let { speaker.speak(it) }
                    history.add("read_aloud: ${action.say?.take(60)}")
                }

                AgentAction.OPEN_APP -> {
                    val ok = action.app?.let { AppLauncher.launch(context, it) } ?: false
                    history.add("open_app ${action.app} -> ${if (ok) "ok" else "not found"}")
                    if (!ok) speaker.speak("${action.app} सापडलं नाही.")
                }

                AgentAction.TAP -> {
                    val node = action.nodeId?.let { id -> obs.nodes.firstOrNull { it.id == id } }
                    val ok = node?.let { Actuator.tap(service, it.bounds) } ?: false
                    history.add("tap ${action.nodeId} -> ${if (ok) "ok" else "fail"}")
                }

                AgentAction.TYPE_TEXT -> {
                    val ok = action.text?.let { Actuator.typeText(service, it) } ?: false
                    history.add("type '${action.text?.take(30)}' -> ${if (ok) "ok" else "fail"}")
                }

                AgentAction.SWIPE -> {
                    val ok = Actuator.swipe(service, action.direction ?: "down")
                    history.add("swipe ${action.direction} -> ${if (ok) "ok" else "fail"}")
                }

                AgentAction.BACK -> {
                    Actuator.back(service); history.add("back")
                }

                AgentAction.HOME -> {
                    Actuator.home(service); history.add("home")
                }

                AgentAction.WAIT -> {
                    history.add("wait"); delay(1000)
                }

                else -> history.add("unknown action ${action.type}")
            }

            delay(700) // let the UI settle before the next observation
        }

        speaker.speak("हे काम खूप मोठं झालं, म्हणून मी थांबतो.")
        onStatus("step limit")
    }
}
