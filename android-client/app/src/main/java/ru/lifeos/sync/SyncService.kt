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

            val zone = ZoneId.systemDefault()
            val today = LocalDate.now(zone)
            val yesterday = today.minusDays(1)
            val yesterdayMetrics = hc.readMetricsForDate(yesterday)
            val todayMetrics = hc.readMetricsForDate(today)
            settings.nutritionSource = todayMetrics.nutritionSource ?: ""
            settings.nutritionOrigins = todayMetrics.nutritionOrigins.joinToString(",")

            val okYesterday = postJson(baseUrl, token, buildPayload(yesterdayMetrics))
            val okToday = postJson(baseUrl, token, buildPayload(todayMetrics))
            return if (okYesterday && okToday) {
                val stamp = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm"))
                settings.lastSync = stamp
                settings.lastError = ""
                SyncResult(true, "Sync ok")
            } else {
                val failText = buildString {
                    append("Sync failed:")
                    if (!okYesterday) append(" yesterday")
                    if (!okToday) append(" today")
                }
                settings.lastError = failText
                SyncResult(false, failText)
            }
        } catch (e: Exception) {
            val msg = "Sync error: ${e.message ?: "unknown"}"
            settings.lastError = msg
            return SyncResult(false, msg)
        }
    }

    private fun buildPayload(metrics: SyncMetrics): String {
        val json = JSONObject()
        json.put("date", metrics.date.toString())
        json.put("steps", metrics.steps ?: 0)
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
