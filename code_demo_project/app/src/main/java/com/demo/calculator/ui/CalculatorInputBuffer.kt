package com.demo.calculator.ui

import android.util.Log

/**
 * 维护用户通过按键拼接出的表达式字符串，不负责语法校验（校验推迟到按下等号时由领域层完成）。
 *
 * 将「按键 → 文本」与「文本 → 求值」分离，避免 [android.app.Activity] 过于臃肿。
 */
class CalculatorInputBuffer {

    private val buffer = StringBuilder()

    /**
     * 当前缓冲区全文，供显示屏与 [com.demo.calculator.domain.CalculatorEngine] 使用。
     */
    fun getText(): String = buffer.toString()

    /**
     * 在末尾追加一个数字字符（`0`–`9`）。
     *
     * @param digit 单个数字字符
     */
    fun appendDigit(digit: Char) {
        require(digit in '0'..'9') { "not_a_digit" }
        buffer.append(digit)
        Log.d(TAG, "buffer after digit: ${buffer}")
    }

    /**
     * 在末尾追加运算符；若上一个字符已是运算符则用新运算符替换之（连续按 `+`、`-` 时修正输入）。
     *
     * @param op 必须是 `+`、`-`、`*`、`/` 之一
     */
    fun appendOperator(op: Char) {
        require(op in OPERATORS) { "not_an_operator" }
        if (buffer.isNotEmpty() && buffer.last() in OPERATORS) {
            buffer.setLength(buffer.length - 1)
            Log.d(TAG, "replaced trailing operator with '$op'")
        }
        buffer.append(op)
        Log.d(TAG, "buffer after operator: ${buffer}")
    }

    /**
     * 追加小数点；若当前「数字段」中已有小数点则忽略本次输入，避免 `1..2` 这类非法串。
     */
    fun appendDecimalSeparator() {
        if (currentNumericSegmentHasDot()) {
            Log.d(TAG, "decimal ignored: segment already has dot")
            return
        }
        if (buffer.isEmpty() || buffer.last() in OPERATORS || buffer.last() == '(') {
            buffer.append('0')
        }
        buffer.append('.')
        Log.d(TAG, "buffer after dot: ${buffer}")
    }

    /**
     * 追加左括号 `(`。
     */
    fun appendLeftParen() {
        buffer.append('(')
    }

    /**
     * 追加右括号 `)`。
     */
    fun appendRightParen() {
        buffer.append(')')
    }

    /**
     * 清空表达式（对应 `C` 键）。
     */
    fun clear() {
        buffer.clear()
        Log.i(TAG, "buffer cleared")
    }

    /**
     * 删除最后一个字符（对应 `DEL` 键）；缓冲区为空时无操作。
     */
    fun deleteLast() {
        if (buffer.isNotEmpty()) {
            buffer.setLength(buffer.length - 1)
        }
    }

    /**
     * 用一段新文本整体替换缓冲区（例如在求值成功后把结果作为下一轮起点）。
     *
     * @param text 新的表达式或结果字符串
     */
    fun replaceWith(text: String) {
        buffer.clear()
        buffer.append(text)
        Log.i(TAG, "buffer replaced with: $text")
    }

    private fun currentNumericSegmentHasDot(): Boolean {
        var i = buffer.length - 1
        while (i >= 0) {
            val c = buffer[i]
            when {
                c == '.' -> return true
                c in OPERATORS || c == '(' || c == ')' -> return false
            }
            i--
        }
        return false
    }

    private companion object {
        private const val TAG = "CalcInput"
        private val OPERATORS = setOf('+', '-', '*', '/')
    }
}
