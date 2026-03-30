package com.demo.calculator.domain

import android.util.Log
import com.demo.calculator.model.CalculatorToken
import java.util.ArrayDeque

/**
 * 使用调度场（Shunting-yard）算法将中缀表达式转为后缀（逆波兰）形式。
 *
 * 后缀表达式便于用栈一次性求值，且天然体现运算符优先级（`*`、`/` 高于 `+`、`-`）。
 */
class InfixToPostfixConverter {

    /**
     * 将中缀词法序列转换为后缀词法序列。
     *
     * @param tokens [ExpressionTokenizer] 的输出
     * @return 后缀形式的词法单元列表
     * @throws IllegalArgumentException 括号不匹配或表达式结构非法时抛出
     */
    fun toPostfix(tokens: List<CalculatorToken>): List<CalculatorToken> {
        Log.d(TAG, "toPostfix: infix tokens=${tokens.size}")
        val output = mutableListOf<CalculatorToken>()
        val stack = ArrayDeque<CalculatorToken>()

        for (token in tokens) {
            when (token) {
                is CalculatorToken.Number -> output.add(token)
                is CalculatorToken.Operator -> {
                    while (stack.isNotEmpty()) {
                        val top = stack.peek()
                        if (top is CalculatorToken.Operator &&
                            precedence(top) >= precedence(token)
                        ) {
                            output.add(stack.pop())
                        } else {
                            break
                        }
                    }
                    stack.push(token)
                }
                is CalculatorToken.LeftParen -> stack.push(token)
                is CalculatorToken.RightParen -> {
                    while (stack.isNotEmpty() && stack.peek() !is CalculatorToken.LeftParen) {
                        output.add(stack.pop())
                    }
                    if (stack.isEmpty() || stack.peek() !is CalculatorToken.LeftParen) {
                        Log.e(TAG, "toPostfix: right paren mismatch")
                        throw IllegalArgumentException("paren_mismatch")
                    }
                    stack.pop()
                }
            }
        }
        while (stack.isNotEmpty()) {
            val t = stack.pop()
            if (t is CalculatorToken.LeftParen || t is CalculatorToken.RightParen) {
                Log.e(TAG, "toPostfix: leftover paren on stack")
                throw IllegalArgumentException("paren_mismatch")
            }
            output.add(t)
        }
        Log.i(TAG, "toPostfix: postfix tokens=${output.size}")
        return output
    }

    /**
     * 返回运算符优先级，数值越大优先级越高。
     *
     * @param op 四则运算符词法单元
     */
    fun precedence(op: CalculatorToken.Operator): Int {
        return when (op.symbol) {
            '+', '-' -> 1
            '*', '/' -> 2
            else -> {
                Log.e(TAG, "precedence: unknown op ${op.symbol}")
                throw IllegalArgumentException("unknown_op:${op.symbol}")
            }
        }
    }

    private companion object {
        private const val TAG = "CalcInfix"
    }
}
