package com.demo.calculator.domain

import android.util.Log
import com.demo.calculator.model.CalculationOutcome

/**
 * 计算器领域门面：串联分词、中缀转后缀与后缀求值三步，对 UI 提供单一入口。
 *
 * 各子步骤由独立类实现，便于单独编写单元测试或替换算法实现。
 */
class CalculatorEngine(
    private val tokenizer: ExpressionTokenizer = ExpressionTokenizer(),
    private val infixToPostfix: InfixToPostfixConverter = InfixToPostfixConverter(),
    private val postfixEvaluator: PostfixExpressionEvaluator = PostfixExpressionEvaluator()
) {

    /**
     * 对用户输入的一整行表达式求值。
     *
     * @param expression 当前显示屏上的表达式文本（可含括号与小数）
     * @return 成功时携带 [CalculationOutcome.Success]，失败时携带可读错误信息
     */
    fun evaluate(expression: String): CalculationOutcome {
        val trimmed = expression.trim()
        if (trimmed.isEmpty()) {
            Log.d(TAG, "evaluate: empty after trim")
            return CalculationOutcome.Error("empty_expression")
        }
        return try {
            val tokens = tokenizer.tokenize(trimmed)
            Log.d(TAG, "evaluate: token count=${tokens.size}")
            val postfix = infixToPostfix.toPostfix(tokens)
            Log.d(TAG, "evaluate: postfix size=${postfix.size}")
            val value = postfixEvaluator.evaluate(postfix)
            Log.i(TAG, "evaluate: ok value=$value")
            CalculationOutcome.Success(value)
        } catch (e: ArithmeticException) {
            Log.e(TAG, "evaluate: arithmetic ${e.message}", e)
            if (e.message == "divide_by_zero") {
                CalculationOutcome.Error("divide_by_zero")
            } else {
                CalculationOutcome.Error(e.message ?: "arithmetic_error")
            }
        } catch (e: IllegalArgumentException) {
            Log.e(TAG, "evaluate: illegal arg ${e.message}", e)
            CalculationOutcome.Error(e.message ?: "invalid_expression")
        } catch (e: Exception) {
            Log.e(TAG, "evaluate: unexpected ${e.message}", e)
            CalculationOutcome.Error(e.message ?: "unknown_error")
        }
    }

    private companion object {
        private const val TAG = "CalcEngine"
    }
}
