package com.manu.mobile.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.manu.mobile.R
import com.manu.mobile.accessibility.ScreenCapturer
import com.manu.mobile.agent.AgentLoop
import com.manu.mobile.agent.BackendClient
import com.manu.mobile.voice.Speaker
import com.manu.mobile.voice.VoiceInput
import java.util.UUID
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

/**
 * Hosts a running agent task in the foreground so it keeps executing while Manu
 * drives other apps (the UI is no longer in front). One task at a time.
 */
class AgentForegroundService : Service() {

    private val scope = CoroutineScope(SupervisorJob())
    private var job: Job? = null
    private var speaker: Speaker? = null
    private var capturer: ScreenCapturer? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val goal = intent?.getStringExtra(EXTRA_GOAL).orEmpty()
        startForegroundCompat()

        if (goal.isBlank()) {
            stopSelf(); return START_NOT_STICKY
        }

        job?.cancel()
        val prefs = getSharedPreferences("manu", Context.MODE_PRIVATE)
        val backendUrl = prefs.getString("backend_url", null)
        val deviceId = prefs.getString("device_id", null) ?: UUID.randomUUID().toString().also {
            prefs.edit().putString("device_id", it).apply()
        }

        // Optional screen-capture token from MainActivity for the vision fallback.
        val projectionCode = intent?.getIntExtra(EXTRA_RESULT_CODE, 0) ?: 0
        val projectionData: Intent? =
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU)
                intent?.getParcelableExtra(EXTRA_RESULT_DATA, Intent::class.java)
            else @Suppress("DEPRECATION") intent?.getParcelableExtra(EXTRA_RESULT_DATA)

        var screenshot: (() -> String?)? = null
        if (projectionData != null) {
            runCatching {
                val mpm = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
                val projection: MediaProjection = mpm.getMediaProjection(projectionCode, projectionData)
                val cap = ScreenCapturer(applicationContext, projection)
                cap.start()
                capturer = cap
                screenshot = { cap.captureBase64() }
            }
        }

        val backend = BackendClient().apply { backendUrl?.let { setBaseUrl(it) } }
        val voice = VoiceInput(applicationContext)
        val tts = Speaker(applicationContext).also { speaker = it }

        val loop = AgentLoop(
            context = applicationContext,
            backend = backend,
            voice = voice,
            speaker = tts,
            deviceId = deviceId,
            captureScreenshot = screenshot,
            onStatus = { AgentStatus.status.value = it },
        )

        AgentStatus.running.value = true
        job = scope.launch {
            try {
                loop.run(goal)
            } finally {
                AgentStatus.running.value = false
                speaker?.shutdown()
                speaker = null
                capturer?.stop()
                capturer = null
                stopSelf()
            }
        }
        return START_NOT_STICKY
    }

    private fun startForegroundCompat() {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            nm.createNotificationChannel(
                NotificationChannel(CHANNEL, getString(R.string.notif_channel), NotificationManager.IMPORTANCE_LOW)
            )
        }
        val notif: Notification = NotificationCompat.Builder(this, CHANNEL)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(getString(R.string.notif_running))
            .setSmallIcon(R.drawable.ic_launcher)
            .setOngoing(true)
            .build()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val type = ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE or
                ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION
            startForeground(NOTIF_ID, notif, type)
        } else {
            startForeground(NOTIF_ID, notif)
        }
    }

    override fun onDestroy() {
        job?.cancel()
        scope.cancel()
        speaker?.shutdown()
        capturer?.stop()
        capturer = null
        AgentStatus.running.value = false
        super.onDestroy()
    }

    companion object {
        const val EXTRA_GOAL = "goal"
        const val EXTRA_RESULT_CODE = "result_code"
        const val EXTRA_RESULT_DATA = "result_data"
        private const val CHANNEL = "manu_agent"
        private const val NOTIF_ID = 1

        fun start(context: Context, goal: String, resultCode: Int = 0, resultData: Intent? = null) {
            val intent = Intent(context, AgentForegroundService::class.java)
                .putExtra(EXTRA_GOAL, goal)
                .putExtra(EXTRA_RESULT_CODE, resultCode)
            resultData?.let { intent.putExtra(EXTRA_RESULT_DATA, it) }
            context.startForegroundService(intent)
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, AgentForegroundService::class.java))
        }
    }
}
