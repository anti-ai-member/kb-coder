package com.demo.calculator.model

/**
 * 计算器词法单元，用于在「分词 → 中缀转后缀 → 求值」流水线中传递结构化的输入。
 *
 * 将用户输入的字符串拆解为数字、运算符与括号，便于后续算法处理，而无需在求值阶段再解析字符。
 */
sealed class CalculatorToken {

    /**
     * 字面量数字（已解析为 [Double]，例如 `3`、`12.5`）。
     *
     * @property value 该词法单元对应的数值
     */
    data class Number(val value: Double) : CalculatorToken()

    /**
     * 四则运算符：`+`、`-`、`*`、`/`。
     *
     * @property symbol 运算符字符
     */
    data class Operator(val symbol: Char) : CalculatorToken()

    /** 左括号 `(` */
    data object LeftParen : CalculatorToken()

    /** 右括号 `)` */
    data object RightParen : CalculatorToken()
}
