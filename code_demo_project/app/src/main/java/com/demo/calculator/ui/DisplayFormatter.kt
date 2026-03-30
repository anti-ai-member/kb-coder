package com.demo.calculator.ui

import android.util.Log
import java.util.Locale
import kotlin.math.abs
import kotlin.math.roundToLong

/**
 * 将 [Double] 结果格式化为适合计算器显示屏的字符串（去掉无意义的小数位）。
 *
 * 与 [com.demo.calculator.domain.CalculatorEngine] 解耦，便于单独调整本地化或科学计数法策略。
 */
class DisplayFormatter(
    private val maxFractionDigits: Int = 12
) {

    /**
     * 把计算结果转成用户可读文本；整数不显示 `.0`，否则保留必要的小数位。
     *
     * @param value 引擎求值得到的数值
     * @return 可直接设置到 [android.widget.TextView] 的字符串
     */
    fun formatResult(value: Double): String {
        Log.d(TAG, "formatResult: in=$value")
        if (value.isNaN()) {
            Log.i(TAG, "formatResult: NaN")
            return "NaN"
        }
        if (value.isInfinite()) {
            Log.i(TAG, "formatResult: infinite")
            return if (value > 0) "∞" else "-∞"
        }
        val v = sanitizeMagnitude(value)
        val asLong = v.roundToLong()
        if (abs(v - asLong) < 1e-9 && abs(asLong) < 1_000_000_000_000L) {
            val s = asLong.toString()
            Log.d(TAG, "formatResult: as integer -> $s")
            return s
        }
        val fmt = "%.${maxFractionDigits}f"
        val s = String.format(Locale.US, fmt, v).trimEnd('0').trimEnd('.')
        Log.d(TAG, "formatResult: decimal -> $s")
        return s
    }

    /**
     * 对极大/极小值做简单规范化，避免屏幕上出现过长指数（演示用）。
     *
     * @param value 原始结果
     */
    fun sanitizeMagnitude(value: Double): Double {
        if (value.isNaN() || value.isInfinite()) return value
        return value
    }

    private companion object {
        private const val TAG = "CalcFormat"
    }
}
