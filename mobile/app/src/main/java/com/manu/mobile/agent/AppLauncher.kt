package com.manu.mobile.agent

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager

/** Resolves a spoken app name ("WhatsApp", "settings") to a launchable package. */
object AppLauncher {

    // A few well-known names so common apps open reliably even if labels differ.
    private val KNOWN = mapOf(
        "whatsapp" to "com.whatsapp",
        "settings" to "com.android.settings",
        "chrome" to "com.android.chrome",
        "messages" to "com.google.android.apps.messaging",
        "phone" to "com.android.dialer",
        "camera" to "com.sec.android.app.camera",
        "gallery" to "com.sec.android.gallery3d",
    )

    fun launch(context: Context, appName: String): Boolean {
        val pm = context.packageManager
        val key = appName.trim().lowercase()

        KNOWN[key]?.let { pkg ->
            launchPackage(context, pkg)?.let { return true }
        }

        // Fall back to matching the launcher label the user actually sees.
        val main = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val resolved = pm.queryIntentActivities(main, 0)
        val match = resolved.firstOrNull {
            it.loadLabel(pm).toString().lowercase().contains(key)
        } ?: return false

        return launchPackage(context, match.activityInfo.packageName) != null
    }

    private fun launchPackage(context: Context, pkg: String): Intent? {
        val intent = context.packageManager.getLaunchIntentForPackage(pkg) ?: return null
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
        return intent
    }
}
