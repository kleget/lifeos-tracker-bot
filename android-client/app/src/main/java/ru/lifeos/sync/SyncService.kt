package ru.lifeos.sync

import android.content.Context
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

data class SyncResult(val ok: Boolean, val message: String)

object SyncService {
    suspend fun performSync(context: Context): SyncResult {
        val settings = Settings(context)
        val baseUrl = settings.serverUrl
        val token = settings.token

        try {
            if (baseUrl.isBlank() || token.isBlank()) {
                settings.lastError = "Missing server URL or token"
                return SyncResult(false, "Missing server URL or token")
            }

            val hc = HealthConnectService(context)
            if (!hc.isAvailable()) {
                settings.lastError = "Health Connect not available"
                return SyncResult(false, "Health Connect not available")
            }
            if (!hc.hasCorePermissions()) {
                settings.lastError = "Health Connect permissions not granted"
                return SyncResult(false, "Permissions not granted")
            }

            val metrics = hc.readMetrics()
            val missing = mutableListOf<String>()
            if (metrics.steps == null) missing.add("steps")
            if (metrics.sleepHours == null) missing.add("sleep")
            if (metrics.weightKg == null) missing.add("weight")
            val nutritionOk =
                metrics.calories != null &&
                    metrics.protein != null &&
                    metrics.fat != null &&
                    metrics.carbs != null
            if (!nutritionOk) missing.add("kbju")

            if (missing.isNotEmpty()) {
                val msg = "Missing data: ${missing.joinToString(", ")}"
                settings.lastError = msg
                return SyncResult(false, msg)
            }

            val payload = buildPayload(metrics)
            val ok = postJson(baseUrl, token, payload)
            return if (ok) {
                val stamp = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm"))
                settings.lastSync = stamp
                settings.lastError = ""
                SyncResult(true, "Sync ok")
            } else {
                settings.lastError = "Sync failed"
                SyncResult(false, "Sync failed")
            }
        } catch (e: Exception) {
            val msg = "Sync error: ${e.message ?: "unknown"}"
            settings.lastError = msg
            return SyncResult(false, msg)
        }
    }

    private fun buildPayload(metrics: SyncMetrics): String {
        val zone = ZoneId.systemDefault()
        val date = LocalDate.now(zone).toString()
        val json = JSONObject()
        json.put("date", date)
        json.put("steps", metrics.steps)
        json.put("sleep_hours", roundOne(metrics.sleepHours ?: 0.0))
        json.put("weight", roundOne(metrics.weightKg ?: 0.0))

        val food = JSONObject()
        food.put("kcal", roundOne(metrics.calories ?: 0.0))
        food.put("protein", roundOne(metrics.protein ?: 0.0))
        food.put("fat", roundOne(metrics.fat ?: 0.0))
        food.put("carb", roundOne(metrics.carbs ?: 0.0))
        json.put("food", food)
        json.put("food_source", "health_connect")
        return json.toString()
    }

    private fun roundOne(value: Double): Double {
        return kotlin.math.round(value * 10.0) / 10.0
    }

    private suspend fun postJson(baseUrl: String, token: String, payload: String): Boolean {
        val url = normalizeUrl(baseUrl)
        return withContext(Dispatchers.IO) {
            val client = OkHttpClient.Builder()
                .callTimeout(20, TimeUnit.SECONDS)
                .build()
            val mediaType = "application/json; charset=utf-8".toMediaType()
            val request = Request.Builder()
                .url(url)
                .addHeader("X-Api-Key", token)
                .post(payload.toRequestBody(mediaType))
                .build()
            client.newCall(request).execute().use { it.isSuccessful }
        }
    }

    private fun normalizeUrl(baseUrl: String): String {
        val trimmed = baseUrl.trim().trimEnd('/')
        return if (trimmed.endsWith("/sync")) trimmed else "$trimmed/sync"
    }
}
