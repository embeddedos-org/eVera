package com.patchava.vera.auto

import android.content.Intent
import androidx.car.app.CarAppService
import androidx.car.app.Screen
import androidx.car.app.Session
import androidx.car.app.validation.HostValidator

class VeraCarAppService : CarAppService() {

    override fun createHostValidator(): HostValidator {
        return HostValidator.ALLOW_ALL_HOSTS_VALIDATOR
    }

    override fun onCreateSession(): Session {
        return VeraCarSession()
    }
}

class VeraCarSession : Session() {

    private val client = VeraAutoClient()

    override fun onCreateScreen(intent: Intent): Screen {
        return VeraCarScreen(carContext, client)
    }

    override fun onCarConfigurationChanged(newConfiguration: android.content.res.Configuration) {
        super.onCarConfigurationChanged(newConfiguration)
    }
}
