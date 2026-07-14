package com.manu.mobile.agent

import com.manu.mobile.BuildConfig
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Talks to the Manu backend. The backend holds the Anthropic key and returns the
 * next action; this class never sees an API key.
 */
class BackendClient(
    private var baseUrl: String = BuildConfig.BACKEND_URL,
    private val sharedSecret: String = BuildConfig.SHARED_SECRET,
) {
    private val http = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .build()

    fun setBaseUrl(url: String) {
        baseUrl = url.trim().trimEnd('/')
    }

    /** Blocking call — invoke from a background thread / coroutine dispatcher. */
    fun step(
        deviceId: String,
        goal: String,
        observation: Observation,
        stepIndex: Int,
        history: List<String>,
        userReply: String?,
    ): AgentAction {
        val payload = JSONObject().apply {
            put("device_id", deviceId)
            put("goal", goal)
            put("step_index", stepIndex)
            put("history", JSONArray(history))
            userReply?.let { put("user_reply", it) }
            put("observation", observationJson(observation))
        }

        val request = Request.Builder()
            .url("$baseUrl/agent/step")
            .apply { if (sharedSecret.isNotEmpty()) header("X-Manu-Key", sharedSecret) }
            .post(payload.toString().toRequestBody(JSON))
            .build()

        http.newCall(request).execute().use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) {
                throw BackendException(resp.code, body)
            }
            val action = JSONObject(body).getJSONObject("action")
            return parseAction(action)
        }
    }

    private fun observationJson(o: Observation): JSONObject = JSONObject().apply {
        o.appPackage?.let { put("app_package", it) }
        o.screenTitle?.let { put("screen_title", it) }
        o.screenshotB64?.let { put("screenshot_b64", it) }
        val arr = JSONArray()
        for (n in o.nodes) {
            arr.put(JSONObject().apply {
                put("id", n.id)
                n.text?.let { put("text", it) }
                n.desc?.let { put("desc", it) }
                n.cls?.let { put("cls", it) }
                put("clickable", n.clickable)
                put("editable", n.editable)
            })
        }
        put("nodes", arr)
    }

    private fun parseAction(o: JSONObject): AgentAction = AgentAction(
        type = o.getString("type"),
        app = o.optStringOrNull("app"),
        nodeId = if (o.has("node_id") && !o.isNull("node_id")) o.getInt("node_id") else null,
        text = o.optStringOrNull("text"),
        direction = o.optStringOrNull("direction"),
        say = o.optStringOrNull("say"),
        needsConfirmation = o.optBoolean("needs_confirmation", false),
    )

    private fun JSONObject.optStringOrNull(key: String): String? =
        if (has(key) && !isNull(key)) getString(key) else null

    companion object {
        private val JSON = "application/json; charset=utf-8".toMediaType()
    }
}

class BackendException(val code: Int, val bodyText: String) :
    Exception("backend $code: $bodyText")
