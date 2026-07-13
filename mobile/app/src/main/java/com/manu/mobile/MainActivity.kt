package com.manu.mobile

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.manu.mobile.accessibility.ManuAccessibilityService
import com.manu.mobile.databinding.ActivityMainBinding
import com.manu.mobile.service.AgentForegroundService
import com.manu.mobile.service.AgentStatus
import com.manu.mobile.voice.VoiceInput
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val voice by lazy { VoiceInput(applicationContext) }

    private val permissionLauncher =
        registerForActivityResult(androidx.activity.result.contract.ActivityResultContracts.RequestMultiplePermissions()) { }

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

        observeStatus()
    }

    private fun onTalk(prefs: android.content.SharedPreferences) {
        // Persist whatever backend URL the user typed so the service uses it.
        prefs.edit().putString("backend_url", binding.backendUrlInput.text.toString().trim()).apply()

        if (!ManuAccessibilityService.isEnabled) {
            Toast.makeText(this, R.string.enable_accessibility, Toast.LENGTH_LONG).show()
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            return
        }

        binding.statusText.setText(R.string.listening)
        lifecycleScope.launch {
            val goal = voice.listen()
            if (goal.isNullOrBlank()) {
                binding.statusText.text = getString(R.string.tap_to_speak)
                return@launch
            }
            binding.transcriptText.text = "🗣 $goal"
            AgentForegroundService.start(this@MainActivity, goal)
        }
    }

    private fun observeStatus() {
        lifecycleScope.launch {
            AgentStatus.running.collect { running -> setRunning(running) }
        }
        lifecycleScope.launch {
            AgentStatus.status.collect { s -> if (s.isNotEmpty()) binding.statusText.text = s }
        }
    }

    private fun setRunning(running: Boolean) {
        binding.stopButton.isEnabled = running
        binding.talkButton.isEnabled = !running
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
