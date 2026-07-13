package com.manu.mobile.accessibility

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityEvent

/**
 * The one component allowed to read other apps' screens and act on them.
 * Exposed as a singleton so the agent loop can call [ScreenReader] / [Actuator]
 * against the live window. Android keeps exactly one instance while enabled.
 */
class ManuAccessibilityService : AccessibilityService() {

    override fun onServiceConnected() {
        instance = this
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // The agent polls the tree on demand; we don't need to react to every event.
    }

    override fun onInterrupt() {}

    override fun onUnbind(intent: android.content.Intent?): Boolean {
        if (instance === this) instance = null
        return super.onUnbind(intent)
    }

    companion object {
        @Volatile
        var instance: ManuAccessibilityService? = null
            private set

        val isEnabled: Boolean get() = instance != null
    }
}
