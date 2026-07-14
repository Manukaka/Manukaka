package com.manu.mobile.service

import kotlinx.coroutines.flow.MutableStateFlow

/** Shared, process-wide state so the UI can observe what the running task is doing. */
object AgentStatus {
    val status = MutableStateFlow("")
    val running = MutableStateFlow(false)
}
