package com.manu.mobile

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.manu.mobile.accessibility.ManuAccessibilityService
import com.manu.mobile.databinding.ActivityMainBinding
import com.manu.mobile.service.AgentForegroundService
import com.manu.mobile.service.AgentStatus
import com.manu.mobile.voice.VoiceInput
import com.manu.mobile.voice.WakeListener
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val voice by lazy { VoiceInput(applicationContext) }
    private var wakeListener: WakeListener? = null

    private val permissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { }

    // Screen-capture consent for the vision fallback. Denial is fine — text-only mode.
    private val projectionLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            val data = if (result.resultCode == Activity.RESULT_OK) result.data else null
            startTask(result.resultCode, data)
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        requestNeededPermissions()

        val prefs = getSharedPreferences("manu", Context.MODE_PRIVATE)
        binding.backendUrlInput.setText(prefs.getString("backend_url", BuildConfig.BACKEND_URL))

        binding.enableAccessibilityButton.setOnClickListener {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }

        binding.talkButton.setOnClickListener { onTalk(prefs) }
        binding.stopButton.setOnClickListener {
            AgentForegroundService.stop(this)
            setRunning(false)
        }

        binding.handsFreeSwitch.setOnCheckedChangeListener { _, checked ->
            onHandsFreeToggled(checked)
        }

        observeStatus()
    }

    // ---- Hands-free (experimental wake word) ---------------------------------

    private fun wake(): WakeListener =
        wakeListener ?: WakeListener(applicationContext) { command ->
            runOnUiThread { handleWake(command) }
        }.also { wakeListener = it }

    private fun onHandsFreeToggled(checked: Boolean) {
        if (!checked) {
            wakeListener?.stop()
            binding.statusText.text = getString(R.string.tap_to_speak)
            return
        }
        if (!ManuAccessibilityService.isEnabled) {
            binding.handsFreeSwitch.isChecked = false
            Toast.makeText(this, R.string.enable_accessibility, Toast.LENGTH_LONG).show()
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            return
        }
        binding.statusText.setText(R.string.wake_listening)
        wake().start()
    }

    private fun handleWake(command: String?) {
        // Hands-free triggers run text-only: screen-capture consent needs a tap, so we
        // skip the vision fallback when there was no user interaction.
        lifecycleScope.launch {
            val goal = command?.takeIf { it.isNotBlank() } ?: run {
                binding.statusText.setText(R.string.listening)
                voice.listen()
            }
            if (goal.isNullOrBlank()) {
                if (binding.handsFreeSwitch.isChecked) wake().start()
                return@launch
            }
            binding.transcriptText.text = "🗣 $goal"
            AgentForegroundService.start(this@MainActivity, goal)
        }
    }

    private fun onTalk(prefs: android.content.SharedPreferences) {
        // Persist whatever backend URL the user typed so the service uses it.
        prefs.edit().putString("backend_url", binding.backendUrlInput.text.toString().trim()).apply()

        if (!ManuAccessibilityService.isEnabled) {
            Toast.makeText(this, R.string.enable_accessibility, Toast.LENGTH_LONG).show()
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            return
        }

        // Ask for screen-capture consent (for the vision fallback). The result
        // callback then captures the spoken goal and starts the task.
        val mpm = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        projectionLauncher.launch(mpm.createScreenCaptureIntent())
    }

    private fun startTask(projectionCode: Int, projectionData: Intent?) {
        binding.statusText.setText(R.string.listening)
        lifecycleScope.launch {
            val goal = voice.listen()
            if (goal.isNullOrBlank()) {
                binding.statusText.text = getString(R.string.tap_to_speak)
                return@launch
            }
            binding.transcriptText.text = "🗣 $goal"
            AgentForegroundService.start(this@MainActivity, goal, projectionCode, projectionData)
        }
    }

    private fun observeStatus() {
        lifecycleScope.launch {
            AgentStatus.running.collect { running ->
                setRunning(running)
                // Don't fight the task for the mic; resume wake-listening after it ends.
                if (running) {
                    wakeListener?.stop()
                } else if (binding.handsFreeSwitch.isChecked) {
                    wake().start()
                }
            }
        }
        lifecycleScope.launch {
            AgentStatus.status.collect { s -> if (s.isNotEmpty()) binding.statusText.text = s }
        }
    }

    private fun setRunning(running: Boolean) {
        binding.stopButton.isEnabled = running
        binding.talkButton.isEnabled = !running
    }

    override fun onDestroy() {
        wakeListener?.stop()
        super.onDestroy()
    }

    private fun requestNeededPermissions() {
        val needed = mutableListOf(Manifest.permission.RECORD_AUDIO)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            needed.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        val missing = needed.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) permissionLauncher.launch(missing.toTypedArray())
    }
}
