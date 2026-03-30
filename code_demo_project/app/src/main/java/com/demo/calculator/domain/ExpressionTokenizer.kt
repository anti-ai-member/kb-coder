package com.demo.calculator.domain

import android.util.Log
import com.demo.calculator.model.CalculatorToken

/**
 * 将用户输入的原始字符串拆分为 [CalculatorToken] 列表。
 *
 * 负责识别数字（含小数）、四则运算符与括号，并支持简单的一元负号（如 `(-3+5)` 或开头的 `-2`）。
 */
class ExpressionTokenizer {

    /**
     * 对非空表达式进行词法分析。
     *
     * @param input 用户在显示屏上编辑的完整表达式字符串
     * @return 从左到右排列的词法单元序列
     * @throws IllegalArgumentException 出现非法字符或无法解析的数字时抛出
     */
    fun tokenize(input: String): List<CalculatorToken> {
        val s = input.trim()
        Log.d(TAG, "tokenize: len=${s.length}")
        if (s.isEmpty()) {
            Log.e(TAG, "tokenize: empty input")
            throw IllegalArgumentException("empty_expression")
        }
        val out = mutableListOf<CalculatorToken>()
        var i = 0
        while (i < s.length) {
            val c = s[i]
            if (c.isWhitespace()) {
                i++
                continue
            }
            when (c) {
                '(' -> {
                    out.add(CalculatorToken.LeftParen)
                    i++
                }
                ')' -> {
                    out.add(CalculatorToken.RightParen)
                    i++
                }
                '+', '*', '/' -> {
                    out.add(CalculatorToken.Operator(c))
                    i++
                }
                '-' -> {
                    if (isUnaryMinusPosition(out)) {
                        i++
                        val (value, nextIndex) = readNumber(s, i)
                        i = nextIndex
                        out.add(CalculatorToken.Number(-value))
                    } else {
                        out.add(CalculatorToken.Operator('-'))
                        i++
                    }
                }
                in '0'..'9', '.' -> {
                    val (value, nextIndex) = readNumber(s, i)
                    i = nextIndex
                    out.add(CalculatorToken.Number(value))
                }
                else -> {
                    Log.e(TAG, "tokenize: illegal char '$c' at $i")
                    throw IllegalArgumentException("illegal_char:$c")
                }
            }
        }
        Log.i(TAG, "tokenize: produced ${out.size} tokens")
        return out
    }

    /**
     * 判断当前位置的 `-` 是否应作为一元负号（紧跟在表达式开头、左括号或其它运算符之后）。
     *
     * @param tokensSoFar 已输出的词法单元前缀
     */
    fun isUnaryMinusPosition(tokensSoFar: List<CalculatorToken>): Boolean {
        if (tokensSoFar.isEmpty()) return true
        return when (val last = tokensSoFar.last()) {
            is CalculatorToken.Operator -> true
            is CalculatorToken.LeftParen -> true
            else -> false
        }
    }

    /**
     * 从 [start] 起读取一个非负数字面量（可含一个小数点）。
     *
     * @return 数值与下一个待读下标
     */
    fun readNumber(source: String, start: Int): Pair<Double, Int> {
        var i = start
        if (i >= source.length) {
            Log.e(TAG, "readNumber: expected digit at end of string")
            throw IllegalArgumentException("number_expected")
        }
        val sb = StringBuilder()
        var dotSeen = false
        while (i < source.length) {
            val ch = source[i]
            when {
                ch.isDigit() -> {
                    sb.append(ch)
                    i++
                }
                ch == '.' -> {
                    if (dotSeen) break
                    dotSeen = true
                    sb.append(ch)
                    i++
                }
                else -> break
            }
        }
        val raw = sb.toString()
        if (raw.isEmpty() || raw == ".") {
            Log.e(TAG, "readNumber: invalid raw='$raw'")
            throw IllegalArgumentException("invalid_number")
        }
        val v = raw.toDoubleOrNull() ?: run {
            Log.e(TAG, "readNumber: parse failed raw='$raw'")
            throw IllegalArgumentException("invalid_number")
        }
        return v to i
    }

    private companion object {
        private const val TAG = "CalcTokenizer"
    }
}
