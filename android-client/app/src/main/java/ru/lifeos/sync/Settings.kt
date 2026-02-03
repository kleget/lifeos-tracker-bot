package ru.lifeos.sync

import android.content.Context

class Settings(context: Context) {
    private val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)

    var serverUrl: String
        get() = prefs.getString("server_url", "") ?: ""
        set(value) {
            prefs.edit().putString("server_url", value.trim()).apply()
        }

    var token: String
        get() = prefs.getString("token", "") ?: ""
        set(value) {
            prefs.edit().putString("token", value.trim()).apply()
        }

    var lastSync: String
        get() = prefs.getString("last_sync", "-") ?: "-"
        set(value) {
            prefs.edit().putString("last_sync", value).apply()
        }

    var lastError: String
        get() = prefs.getString("last_error", "") ?: ""
        set(value) {
            prefs.edit().putString("last_error", value).apply()
        }

    var nutritionSource: String
        get() = prefs.getString("nutrition_source", "") ?: ""
        set(value) {
            prefs.edit().putString("nutrition_source", value).apply()
        }

    var nutritionOrigins: String
        get() = prefs.getString("nutrition_origins", "") ?: ""
        set(value) {
            prefs.edit().putString("nutrition_origins", value).apply()
        }
}
