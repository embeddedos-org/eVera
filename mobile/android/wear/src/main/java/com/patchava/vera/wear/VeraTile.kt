package com.patchava.vera.wear

import androidx.wear.tiles.RequestBuilders
import androidx.wear.tiles.ResourceBuilders
import androidx.wear.tiles.TileBuilders
import androidx.wear.tiles.TileService
import androidx.wear.tiles.LayoutElementBuilders
import androidx.wear.tiles.DimensionBuilders
import androidx.wear.tiles.ColorBuilders
import androidx.wear.tiles.ModifiersBuilders
import androidx.wear.tiles.ActionBuilders
import androidx.wear.tiles.TimelineBuilders
import com.google.common.util.concurrent.Futures
import com.google.common.util.concurrent.ListenableFuture

class VeraTile : TileService() {

    companion object {
        private const val RESOURCES_VERSION = "1"
    }

    override fun onTileRequest(requestParams: RequestBuilders.TileRequest): ListenableFuture<TileBuilders.Tile> {
        val prefs = getSharedPreferences("vera_wear_state", MODE_PRIVATE)
        val lastResponse = prefs.getString("last_response", "Tap to talk to Vera") ?: "Tap to talk to Vera"
        val lastAgent = prefs.getString("last_agent_emoji", "🤖") ?: "🤖"
        val isConnected = prefs.getBoolean("is_connected", false)

        val truncatedResponse = if (lastResponse.length > 60) {
            lastResponse.take(57) + "..."
        } else {
            lastResponse
        }

        val layout = LayoutElementBuilders.Column.Builder()
            .setWidth(DimensionBuilders.expand())
            .setHorizontalAlignment(LayoutElementBuilders.HORIZONTAL_ALIGN_CENTER)
            // Status dot + agent emoji
            .addContent(
                LayoutElementBuilders.Text.Builder()
                    .setText("${if (isConnected) "🟢" else "🔴"} $lastAgent eVera")
                    .setFontStyle(
                        LayoutElementBuilders.FontStyle.Builder()
                            .setSize(DimensionBuilders.sp(14f))
                            .setColor(ColorBuilders.argb(0xFFFFFFFF.toInt()))
                            .build()
                    )
                    .build()
            )
            // Response text
            .addContent(
                LayoutElementBuilders.Text.Builder()
                    .setText(truncatedResponse)
                    .setFontStyle(
                        LayoutElementBuilders.FontStyle.Builder()
                            .setSize(DimensionBuilders.sp(12f))
                            .setColor(ColorBuilders.argb(0xFFCCCCCC.toInt()))
                            .build()
                    )
                    .setMaxLines(3)
                    .build()
            )
            // Tap to talk
            .addContent(
                LayoutElementBuilders.Text.Builder()
                    .setText("🎤 Tap to talk")
                    .setFontStyle(
                        LayoutElementBuilders.FontStyle.Builder()
                            .setSize(DimensionBuilders.sp(12f))
                            .setColor(ColorBuilders.argb(0xFF6200EE.toInt()))
                            .build()
                    )
                    .setModifiers(
                        ModifiersBuilders.Modifiers.Builder()
                            .setClickable(
                                ModifiersBuilders.Clickable.Builder()
                                    .setOnClick(
                                        ActionBuilders.LaunchAction.Builder()
                                            .setAndroidActivity(
                                                ActionBuilders.AndroidActivity.Builder()
                                                    .setPackageName("com.patchava.vera.wear")
                                                    .setClassName("com.patchava.vera.wear.WearMainActivity")
                                                    .build()
                                            )
                                            .build()
                                    )
                                    .setId("tap_to_talk")
                                    .build()
                            )
                            .build()
                    )
                    .build()
            )
            .build()

        val tile = TileBuilders.Tile.Builder()
            .setResourcesVersion(RESOURCES_VERSION)
            .setFreshnessIntervalMillis(15 * 60 * 1000) // 15 minutes
            .setTileTimeline(
                TimelineBuilders.Timeline.Builder()
                    .addTimelineEntry(
                        TimelineBuilders.TimelineEntry.Builder()
                            .setLayout(
                                LayoutElementBuilders.Layout.Builder()
                                    .setRoot(layout)
                                    .build()
                            )
                            .build()
                    )
                    .build()
            )
            .build()

        return Futures.immediateFuture(tile)
    }

    override fun onTileResourcesRequest(requestParams: RequestBuilders.ResourcesRequest): ListenableFuture<ResourceBuilders.Resources> {
        return Futures.immediateFuture(
            ResourceBuilders.Resources.Builder()
                .setVersion(RESOURCES_VERSION)
                .build()
        )
    }
}
