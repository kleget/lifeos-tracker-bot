package ru.lifeos.sync

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class SyncBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val action = intent?.action ?: return
        if (
            action == Intent.ACTION_BOOT_COMPLETED ||
            action == Intent.ACTION_MY_PACKAGE_REPLACED
        ) {
            val settings = Settings(context)
            if (settings.serverUrl.isNotBlank() && settings.token.isNotBlank()) {
                SyncWorker.schedulePeriodic(context)
                SyncWorker.enqueueOnce(context)
            }
        }
    }
}
