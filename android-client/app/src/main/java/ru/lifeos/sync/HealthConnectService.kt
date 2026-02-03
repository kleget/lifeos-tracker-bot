package ru.lifeos.sync

import android.content.Context
import android.content.Intent
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.NutritionRecord
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.records.WeightRecord
import androidx.health.connect.client.request.AggregateRequest
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

data class SyncMetrics(
    val steps: Long?,
    val sleepHours: Double?,
    val weightKg: Double?,
    val calories: Double?,
    val protein: Double?,
    val fat: Double?,
    val carbs: Double?,
)

class HealthConnectService(private val context: Context) {
    companion object {
        val CORE_PERMISSIONS: Set<String> = setOf(
            HealthPermission.getReadPermission(StepsRecord::class),
            HealthPermission.getReadPermission(SleepSessionRecord::class),
            HealthPermission.getReadPermission(WeightRecord::class),
            HealthPermission.getReadPermission(NutritionRecord::class),
        )

        const val BACKGROUND_PERMISSION: String = HealthPermission.PERMISSION_READ_HEALTH_DATA_IN_BACKGROUND
        const val PROVIDER_GOOGLE: String = "com.google.android.apps.healthdata"
        const val PROVIDER_SYSTEM: String = "com.android.healthconnect"
        const val ACTION_SETTINGS: String = "androidx.health.ACTION_HEALTH_CONNECT_SETTINGS"
    }

    fun getSdkStatus(): Int {
        val provider = resolveProviderPackageName()
        if (provider == null) {
            return HealthConnectClient.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED
        }
        return HealthConnectClient.getSdkStatus(context, provider)
    }

    fun isAvailable(): Boolean {
        return getSdkStatus() == HealthConnectClient.SDK_AVAILABLE
    }

    private fun client(): HealthConnectClient {
        val provider = resolveProviderPackageName()
            ?: throw IllegalStateException("Health Connect provider not found")
        return HealthConnectClient.getOrCreate(context, provider)
    }

    suspend fun hasCorePermissions(): Boolean {
        val granted = client().permissionController.getGrantedPermissions()
        return granted.containsAll(CORE_PERMISSIONS)
    }

    suspend fun hasBackgroundPermission(): Boolean {
        val granted = client().permissionController.getGrantedPermissions()
        return granted.contains(BACKGROUND_PERMISSION)
    }

    suspend fun readMetrics(): SyncMetrics {
        val client = client()
        val zone = ZoneId.systemDefault()
        val today = LocalDate.now(zone)
        val startOfDay = today.atStartOfDay(zone).toInstant()
        val now = Instant.now()

        val stepsAgg = client.aggregate(
            AggregateRequest(
                metrics = setOf(StepsRecord.COUNT_TOTAL),
                timeRangeFilter = TimeRangeFilter.between(startOfDay, now),
            )
        )
        val steps = stepsAgg[StepsRecord.COUNT_TOTAL]

        val nutritionAgg = client.aggregate(
            AggregateRequest(
                metrics = setOf(
                    NutritionRecord.ENERGY_TOTAL,
                    NutritionRecord.PROTEIN_TOTAL,
                    NutritionRecord.TOTAL_FAT_TOTAL,
                    NutritionRecord.TOTAL_CARBOHYDRATE_TOTAL,
                ),
                timeRangeFilter = TimeRangeFilter.between(startOfDay, now),
            )
        )
        val calories = nutritionAgg[NutritionRecord.ENERGY_TOTAL]?.inKilocalories
        val protein = nutritionAgg[NutritionRecord.PROTEIN_TOTAL]?.inGrams
        val fat = nutritionAgg[NutritionRecord.TOTAL_FAT_TOTAL]?.inGrams
        val carbs = nutritionAgg[NutritionRecord.TOTAL_CARBOHYDRATE_TOTAL]?.inGrams

        val sleepHours = readLatestSleepHours(client, now)
        val weightKg = readLatestWeight(client, now)

        return SyncMetrics(
            steps = steps,
            sleepHours = sleepHours,
            weightKg = weightKg,
            calories = calories,
            protein = protein,
            fat = fat,
            carbs = carbs,
        )
    }

    fun createPermissionContract(): androidx.activity.result.contract.ActivityResultContract<Set<String>, Set<String>> {
        val provider = resolveProviderPackageName() ?: PROVIDER_GOOGLE
        return androidx.health.connect.client.PermissionController
            .createRequestPermissionResultContract(provider)
    }

    fun buildSettingsIntent(): Intent {
        return Intent(ACTION_SETTINGS)
    }

    fun getProviderPackageName(): String? {
        return resolveProviderPackageName()
    }

    private suspend fun readLatestSleepHours(client: HealthConnectClient, now: Instant): Double? {
        val start = now.minus(Duration.ofHours(36))
        val records = client.readRecords(
            ReadRecordsRequest(
                recordType = SleepSessionRecord::class,
                timeRangeFilter = TimeRangeFilter.between(start, now),
            )
        ).records
        val latest = records.maxByOrNull { it.endTime } ?: return null
        val duration = Duration.between(latest.startTime, latest.endTime)
        return duration.toMinutes().toDouble() / 60.0
    }

    private suspend fun readLatestWeight(client: HealthConnectClient, now: Instant): Double? {
        val start = now.minus(Duration.ofDays(7))
        val records = client.readRecords(
            ReadRecordsRequest(
                recordType = WeightRecord::class,
                timeRangeFilter = TimeRangeFilter.between(start, now),
            )
        ).records
        val latest = records.maxByOrNull { it.time } ?: return null
        return latest.weight.inKilograms
    }

    private fun resolveProviderPackageName(): String? {
        val pm = context.packageManager
        if (isPackageInstalled(pm, PROVIDER_GOOGLE)) return PROVIDER_GOOGLE
        if (isPackageInstalled(pm, PROVIDER_SYSTEM)) return PROVIDER_SYSTEM
        val intent = Intent(ACTION_SETTINGS)
        val resolved = pm.resolveActivity(intent, 0)
        return resolved?.activityInfo?.packageName
    }

    private fun isPackageInstalled(pm: android.content.pm.PackageManager, pkg: String): Boolean {
        return try {
            pm.getPackageInfo(pkg, 0)
            true
        } catch (_: Exception) {
            false
        }
    }
}
