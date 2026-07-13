package com.manu.mobile.accessibility

import android.graphics.Rect
import android.view.accessibility.AccessibilityNodeInfo
import com.manu.mobile.agent.Observation
import com.manu.mobile.agent.UiNode

/**
 * Walks the current window's accessibility tree into a compact [Observation].
 * We keep only elements that carry information or can be interacted with, cap the
 * count, and remember each node's on-screen bounds so [Actuator] can tap by id.
 */
object ScreenReader {

    private const val MAX_NODES = 80

    fun capture(service: ManuAccessibilityService): Observation {
        val root = service.rootInActiveWindow
            ?: return Observation(appPackage = null, screenTitle = null, nodes = emptyList())

        val pkg = root.packageName?.toString()
        val nodes = ArrayList<UiNode>()
        var nextId = 1

        val queue = ArrayDeque<AccessibilityNodeInfo>()
        queue.add(root)
        while (queue.isNotEmpty() && nodes.size < MAX_NODES) {
            val node = queue.removeFirst()
            val text = node.text?.toString()?.trim()?.takeIf { it.isNotEmpty() }
            val desc = node.contentDescription?.toString()?.trim()?.takeIf { it.isNotEmpty() }
            val editable = node.isEditable
            val clickable = node.isClickable

            if ((text != null || desc != null || clickable || editable) && node.isVisibleToUser) {
                val bounds = Rect().also { node.getBoundsInScreen(it) }
                if (bounds.width() > 0 && bounds.height() > 0) {
                    nodes.add(
                        UiNode(
                            id = nextId++,
                            text = text,
                            desc = desc,
                            cls = shortClass(node.className?.toString()),
                            clickable = clickable,
                            editable = editable,
                            bounds = bounds,
                        )
                    )
                }
            }
            for (i in 0 until node.childCount) {
                node.getChild(i)?.let { queue.add(it) }
            }
        }

        val title = nodes.firstOrNull()?.text
        return Observation(appPackage = pkg, screenTitle = title, nodes = nodes)
    }

    private fun shortClass(cls: String?): String? =
        cls?.substringAfterLast('.')?.takeIf { it.isNotEmpty() }
}
