package ru.lifeos.sync

import android.os.Bundle
import androidx.activity.result.ActivityResultLauncher
import androidx.appcompat.app.AppCompatActivity
import ru.lifeos.sync.databinding.ActivityOnboardingBinding

class OnboardingActivity : AppCompatActivity() {
    private lateinit var binding: ActivityOnboardingBinding
    private lateinit var permissionLauncher: ActivityResultLauncher<Set<String>>

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityOnboardingBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val hc = HealthConnectService(this)
        permissionLauncher = registerForActivityResult(
            hc.createPermissionContract()
        ) { _ ->
            finish()
        }

        binding.btnGrant.setOnClickListener {
            permissionLauncher.launch(HealthConnectService.CORE_PERMISSIONS)
        }

        binding.btnClose.setOnClickListener {
            finish()
        }
    }
}
