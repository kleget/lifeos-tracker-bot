package ru.lifeos.sync

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.activity.result.ActivityResultLauncher
import androidx.appcompat.app.AppCompatActivity
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.contracts.HealthPermissionsRequestContract
import androidx.lifecycle.lifecycleScope
import ru.lifeos.sync.databinding.ActivityMainBinding
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding
    private lateinit var settings: Settings
    private lateinit var permissionLauncher: ActivityResultLauncher<Set<String>>

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        settings = Settings(this)
        binding.editServerUrl.setText(settings.serverUrl)
        binding.editToken.setText(settings.token)

        val hc = HealthConnectService(this)
        permissionLauncher = registerForActivityResult(
            hc.createPermissionContract()
        ) { _ ->
            refreshStatus()
        }

        binding.btnSave.setOnClickListener {
            settings.serverUrl = binding.editServerUrl.text.toString()
            settings.token = binding.editToken.text.toString()
            SyncWorker.schedulePeriodic(this)
            toast("Saved. Auto-sync every 30 min.")
            refreshStatus()
        }

        binding.btnPermissions.setOnClickListener {
            requestPermissions()
        }

        binding.btnSyncNow.setOnClickListener {
            toast("Sync started")
            lifecycleScope.launch {
                val result = SyncService.performSync(this@MainActivity)
                refreshStatus()
                toast(result.message)
            }
        }

        binding.btnOpenHealthConnect.setOnClickListener {
            openHealthConnect()
        }

        refreshStatus()
    }

    private fun requestPermissions() {
        val hc = HealthConnectService(this)
        val perms = HealthConnectService.CORE_PERMISSIONS
        val provider = hc.getProviderPackageName() ?: HealthConnectService.PROVIDER_GOOGLE
        val contract = HealthPermissionsRequestContract(provider)
        val intent = contract.createIntent(this, perms)
        val canResolve = intent.resolveActivity(packageManager) != null
        if (!canResolve) {
            toast("Permission screen not found, opening Health Connect")
            val settingsIntent = hc.buildSettingsIntent()
            if (packageManager.resolveActivity(settingsIntent, 0) != null) {
                startActivity(settingsIntent)
            }
            return
        }
        toast("Requesting permissions...")
        permissionLauncher.launch(perms)
    }

    private fun refreshStatus() {
        val hc = HealthConnectService(this)
        val status = when (hc.getSdkStatus()) {
            HealthConnectClient.SDK_AVAILABLE -> "available"
            HealthConnectClient.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED -> "update required"
            else -> "unavailable"
        }
        val server = if (settings.serverUrl.isBlank()) "not set" else settings.serverUrl
        val token = if (settings.token.isBlank()) "not set" else "set"
        val provider = hc.getProviderPackageName() ?: "unknown"

        lifecycleScope.launch {
            val coreGranted = if (hc.isAvailable()) hc.hasCorePermissions() else false
            val bgGranted = if (hc.isAvailable()) hc.hasBackgroundPermission() else false
            binding.txtStatus.text = buildString {
                append("Health Connect: ").append(status).append('\n')
                append("Permissions: ").append(if (coreGranted) "granted" else "missing").append('\n')
                append("Background: ").append(if (bgGranted) "granted" else "missing").append('\n')
                append("Server: ").append(server).append('\n')
                append("Token: ").append(token).append('\n')
                append("Provider: ").append(provider)
            }
            binding.txtLastSync.text = buildString {
                append("Last sync: ").append(settings.lastSync)
                if (settings.lastError.isNotBlank()) {
                    append("\nLast error: ").append(settings.lastError)
                }
            }
        }
    }

    private fun openHealthConnect() {
        val hc = HealthConnectService(this)
        val intent = hc.buildSettingsIntent()
        val resolved = packageManager.resolveActivity(intent, 0)
        if (resolved != null) {
            startActivity(intent)
            return
        }
        val pkg = hc.getProviderPackageName() ?: HealthConnectService.PROVIDER_GOOGLE
        val store = Intent(Intent.ACTION_VIEW, Uri.parse("https://play.google.com/store/apps/details?id=$pkg"))
        startActivity(store)
    }

    private fun toast(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
    }
}
