package ru.lifeos.sync

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit

class SyncWorker(appContext: Context, params: WorkerParameters) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        val result = SyncService.performSync(applicationContext)
        return if (result.ok) {
            Result.success()
        } else {
            Result.retry()
        }
    }

    companion object {
        private const val PERIODIC_NAME = "lifeos_sync_periodic"
        private const val ONCE_NAME = "lifeos_sync_once"

        fun schedulePeriodic(context: Context) {
            val request = PeriodicWorkRequestBuilder<SyncWorker>(30, TimeUnit.MINUTES)
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                PERIODIC_NAME,
                ExistingPeriodicWorkPolicy.UPDATE,
                request,
            )
        }

        fun enqueueOnce(context: Context) {
            val request = OneTimeWorkRequestBuilder<SyncWorker>().build()
            WorkManager.getInstance(context).enqueueUniqueWork(
                ONCE_NAME,
                ExistingWorkPolicy.REPLACE,
                request,
            )
        }
    }
}
