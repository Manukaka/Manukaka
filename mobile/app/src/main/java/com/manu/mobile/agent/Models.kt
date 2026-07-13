package com.manu.mobile.agent

import android.graphics.Rect

/** One interactable element from the accessibility tree, as sent to the backend. */
data class UiNode(
    val id: Int,
    val text: String?,
    val desc: String?,
    val cls: String?,
    val clickable: Boolean,
    val editable: Boolean,
    // Local only — not serialized to the backend; used to actually perform taps.
    val bounds: Rect,
)

/** A snapshot of the current screen. */
data class Observation(
    val appPackage: String?,
    val screenTitle: String?,
    val nodes: List<UiNode>,
    val screenshotB64: String? = null,
)

/** The single next action the backend tells us to perform. Mirrors backend schema. */
data class AgentAction(
    val type: String,
    val app: String? = null,
    val nodeId: Int? = null,
    val text: String? = null,
    val direction: String? = null,
    val say: String? = null,
    val needsConfirmation: Boolean = false,
) {
    companion object {
        const val OPEN_APP = "open_app"
        const val TAP = "tap"
        const val TYPE_TEXT = "type_text"
        const val SWIPE = "swipe"
        const val BACK = "back"
        const val HOME = "home"
        const val READ_ALOUD = "read_aloud"
        const val ASK_USER = "ask_user"
        const val WAIT = "wait"
        const val DONE = "done"
    }
}
