package com.manu.mobile.agent

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager

/** Resolves a spoken app name ("WhatsApp", "settings") to a launchable package. */
object AppLauncher {

    // A few well-known names (incl. Marathi/phonetic) so common apps open reliably
    // even when the on-screen label differs from what the user said.
    private val KNOWN = mapOf(
        "whatsapp" to "com.whatsapp",
        "व्हॉट्सअॅप" to "com.whatsapp",
        "व्हाट्सअप" to "com.whatsapp",
        "settings" to "com.android.settings",
        "सेटिंग" to "com.android.settings",
        "सेटिंग्ज" to "com.android.settings",
        "सेटिंग्स" to "com.android.settings",
        "chrome" to "com.android.chrome",
        "क्रोम" to "com.android.chrome",
        "browser" to "com.android.chrome",
        "ब्राउझर" to "com.android.chrome",
        "messages" to "com.google.android.apps.messaging",
        "मेसेज" to "com.google.android.apps.messaging",
        "संदेश" to "com.google.android.apps.messaging",
        "phone" to "com.android.dialer",
        "फोन" to "com.android.dialer",
        "dialer" to "com.android.dialer",
        "camera" to "com.sec.android.app.camera",
        "कॅमेरा" to "com.sec.android.app.camera",
        "gallery" to "com.sec.android.gallery3d",
        "गॅलरी" to "com.sec.android.gallery3d",
        "youtube" to "com.google.android.youtube",
        "युट्युब" to "com.google.android.youtube",
        "gmail" to "com.google.android.gm",
        "जीमेल" to "com.google.android.gm",
        "notes" to "com.samsung.android.app.notes",
        "नोट्स" to "com.samsung.android.app.notes",
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
