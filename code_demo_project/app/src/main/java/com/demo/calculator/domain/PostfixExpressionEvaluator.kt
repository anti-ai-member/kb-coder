package com.demo.calculator.domain

import android.util.Log
import com.demo.calculator.model.CalculatorToken
import java.util.ArrayDeque

/**
 * 对后缀（逆波兰）表达式求值。
 *
 * 从左到右扫描：遇到数字入栈，遇到运算符则弹出栈顶两个操作数运算后再入栈。
 */
class PostfixExpressionEvaluator {

    /**
     * 计算后缀表达式的数值结果。
     *
     * @param postfix [InfixToPostfixConverter.toPostfix] 的输出
     * @return 栈中最终应仅剩一个数值，即为本结果
     * @throws IllegalArgumentException 操作数个数与运算符不匹配时抛出
     * @throws ArithmeticException 发生除零时抛出
     */
    fun evaluate(postfix: List<CalculatorToken>): Double {
        val stack = ArrayDeque<Double>()
        for (token in postfix) {
            when (token) {
                is CalculatorToken.Number -> stack.push(token.value)
                is CalculatorToken.Operator -> {
                    if (stack.size < 2) {
                        Log.e(TAG, "apply op '${token.symbol}': operands missing (stack=${stack.size})")
                        throw IllegalArgumentException("operand_missing")
                    }
                    val b = stack.pop()
                    val a = stack.pop()
                    stack.push(apply(a, b, token.symbol))
                }
                else -> throw IllegalArgumentException("unexpected_token")
            }
        }
        if (stack.size != 1) {
            Log.e(TAG, "evaluate: stack size=${stack.size} expected 1")
            throw IllegalArgumentException("invalid_expression")
        }
        val result = stack.pop()
        Log.i(TAG, "evaluate: result=$result")
        return result
    }

    /**
     * 对两个操作数施加 [symbol] 所表示的运算。
     *
     * @param left 左操作数（减法、除法中作为被减数、被除数）
     * @param right 右操作数
     * @param symbol `+`、`-`、`*` 或 `/`
     */
    fun apply(left: Double, right: Double, symbol: Char): Double {
        return when (symbol) {
            '+' -> left + right
            '-' -> left - right
            '*' -> left * right
            '/' -> {
                if (right == 0.0) {
                    Log.e(TAG, "divide by zero: left=$left right=$right")
                    throw ArithmeticException("divide_by_zero")
                }
                left / right
            }
            else -> {
                Log.e(TAG, "unknown operator symbol=$symbol")
                throw IllegalArgumentException("unknown_op:$symbol")
            }
        }
    }

    private companion object {
        private const val TAG = "CalcPostfix"
    }
}
