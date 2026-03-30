package com.demo.calculator.model

/**
 * 封装一次表达式求值的结果：要么得到数值，要么得到可展示给用户的错误说明。
 *
 * UI 层只需根据类型分支更新显示屏或提示文案，无需捕获各类底层异常细节。
 */
sealed class CalculationOutcome {

    /**
     * 求值成功。
     *
     * @property value 计算得到的数值
     */
    data class Success(val value: Double) : CalculationOutcome()

    /**
     * 求值失败（语法错误、除零、空表达式等）。
     *
     * @property message 可直接显示或记入日志的说明
     */
    data class Error(val message: String) : CalculationOutcome()
}
