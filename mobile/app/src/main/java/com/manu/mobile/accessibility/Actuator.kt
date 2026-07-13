package com.manu.mobile.accessibility

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.graphics.Rect
import android.os.Bundle
import android.view.accessibility.AccessibilityNodeInfo
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Executes a decided action against the live screen using the accessibility APIs:
 * taps and swipes via gesture dispatch, text entry via ACTION_SET_TEXT, and Back/
 * Home via global actions.
 */
object Actuator {

    fun tap(service: ManuAccessibilityService, bounds: Rect): Boolean {
        val path = Path().apply { moveTo(bounds.exactCenterX(), bounds.exactCenterY()) }
        val stroke = GestureDescription.StrokeDescription(path, 0, 60)
        return dispatchBlocking(service, GestureDescription.Builder().addStroke(stroke).build())
    }

    fun swipe(service: ManuAccessibilityService, direction: String): Boolean {
        val dm = service.resources.displayMetrics
        val w = dm.widthPixels.toFloat()
        val h = dm.heightPixels.toFloat()
        val cx = w / 2f
        val cy = h / 2f
        val (sx, sy, ex, ey) = when (direction) {
            "up" -> listOf(cx, h * 0.7f, cx, h * 0.3f)
            "down" -> listOf(cx, h * 0.3f, cx, h * 0.7f)
            "left" -> listOf(w * 0.7f, cy, w * 0.3f, cy)
            else -> listOf(w * 0.3f, cy, w * 0.7f, cy) // right
        }
        val path = Path().apply {
            moveTo(sx, sy)
            lineTo(ex, ey)
        }
        val stroke = GestureDescription.StrokeDescription(path, 0, 250)
        return dispatchBlocking(service, GestureDescription.Builder().addStroke(stroke).build())
    }

    fun typeText(service: ManuAccessibilityService, text: String): Boolean {
        val target = service.rootInActiveWindow?.let { findEditable(it) } ?: return false
        val args = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
        }
        return target.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
    }

    fun back(service: AccessibilityService): Boolean =
        service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)

    fun home(service: AccessibilityService): Boolean =
        service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_HOME)

    private fun findEditable(root: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)?.let { if (it.isEditable) return it }
        val queue = ArrayDeque<AccessibilityNodeInfo>().apply { add(root) }
        while (queue.isNotEmpty()) {
            val n = queue.removeFirst()
            if (n.isEditable && n.isVisibleToUser) return n
            for (i in 0 until n.childCount) n.getChild(i)?.let { queue.add(it) }
        }
        return null
    }

    private fun dispatchBlocking(service: AccessibilityService, gesture: GestureDescription): Boolean {
        val latch = CountDownLatch(1)
        var ok = false
        val dispatched = service.dispatchGesture(
            gesture,
            object : AccessibilityService.GestureResultCallback() {
                override fun onCompleted(g: GestureDescription?) {
                    ok = true; latch.countDown()
                }

                override fun onCancelled(g: GestureDescription?) {
                    ok = false; latch.countDown()
                }
            },
            null,
        )
        if (!dispatched) return false
        latch.await(3, TimeUnit.SECONDS)
        return ok
    }
}
