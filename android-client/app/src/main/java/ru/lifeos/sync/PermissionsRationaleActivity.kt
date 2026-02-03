package ru.lifeos.sync

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import ru.lifeos.sync.databinding.ActivityPermissionsRationaleBinding

class PermissionsRationaleActivity : AppCompatActivity() {
    private lateinit var binding: ActivityPermissionsRationaleBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityPermissionsRationaleBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.btnClose.setOnClickListener {
            finish()
        }
    }
}