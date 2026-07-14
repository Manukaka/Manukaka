package com.manu.mobile.accessibility

import android.content.Context
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.Image
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.os.Handler
import android.os.Looper
import android.util.Base64
import android.util.DisplayMetrics
import java.io.ByteArrayOutputStream

/**
 * Captures the current screen as a base64 PNG using a MediaProjection token, for the
 * vision fallback when the accessibility tree is too sparse to act on. Frames are
 * downscaled to keep tokens (and cost) low.
 */
class ScreenCapturer(
    context: Context,
    private val projection: MediaProjection,
) {
    private val metrics: DisplayMetrics = context.resources.displayMetrics
    private val width = metrics.widthPixels
    private val height = metrics.heightPixels
    private val density = metrics.densityDpi

    private var reader: ImageReader? = null
    private var display: VirtualDisplay? = null
    private var started = false

    fun start() {
        if (started) return
        // Android 14 requires a registered callback before creating the display.
        projection.registerCallback(object : MediaProjection.Callback() {}, Handler(Looper.getMainLooper()))
        val ir = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2)
        reader = ir
        display = projection.createVirtualDisplay(
            "manu-capture",
            width, height, density,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            ir.surface, null, null,
        )
        started = true
    }

    /** Grab the latest frame as a downscaled base64 PNG, or null if none is ready. */
    fun captureBase64(targetWidth: Int = 720): String? {
        val ir = reader ?: return null
        var image: Image? = null
        // A frame may not be ready the instant we ask — retry briefly.
        var tries = 0
        while (image == null && tries < 20) {
            image = ir.acquireLatestImage()
            if (image == null) {
                Thread.sleep(50); tries++
            }
        }
        image ?: return null
        return try {
            val bitmap = toBitmap(image)
            val scaled = downscale(bitmap, targetWidth)
            val out = ByteArrayOutputStream()
            scaled.compress(Bitmap.CompressFormat.PNG, 100, out)
            Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP)
        } finally {
            image.close()
        }
    }

    private fun toBitmap(image: Image): Bitmap {
        val plane = image.planes[0]
        val buffer = plane.buffer
        val pixelStride = plane.pixelStride
        val rowStride = plane.rowStride
        val rowPadding = rowStride - pixelStride * width
        val bmp = Bitmap.createBitmap(
            width + rowPadding / pixelStride, height, Bitmap.Config.ARGB_8888,
        )
        bmp.copyPixelsFromBuffer(buffer)
        return if (rowPadding == 0) bmp else Bitmap.createBitmap(bmp, 0, 0, width, height)
    }

    private fun downscale(bmp: Bitmap, targetWidth: Int): Bitmap {
        if (bmp.width <= targetWidth) return bmp
        val ratio = targetWidth.toFloat() / bmp.width
        return Bitmap.createScaledBitmap(bmp, targetWidth, (bmp.height * ratio).toInt(), true)
    }

    fun stop() {
        display?.release()
        reader?.close()
        runCatching { projection.stop() }
        display = null
        reader = null
        started = false
    }
}
