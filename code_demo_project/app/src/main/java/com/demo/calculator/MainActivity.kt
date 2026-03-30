package com.demo.calculator

import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.demo.calculator.databinding.ActivityMainBinding
import com.demo.calculator.domain.CalculatorEngine
import com.demo.calculator.model.CalculationOutcome
import com.demo.calculator.ui.CalculatorInputBuffer
import com.demo.calculator.ui.DisplayFormatter

/**
 * 计算器主界面：仅负责把按键事件交给 [CalculatorInputBuffer]，在等号时调用 [CalculatorEngine] 并刷新显示。
 *
 * 业务规则分布在 `domain` 与 `ui` 包内，本类保持薄控制器，便于你方知识库脚本抽取多个类的结构与注释。
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val inputBuffer = CalculatorInputBuffer()
    private val engine = CalculatorEngine()
    private val formatter = DisplayFormatter()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Log.i(TAG, "onCreate: calculator UI starting")
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        bindKeys()
        refreshDisplay()
    }

    /**
     * 为布局中的按键注册点击回调。
     */
    private fun bindKeys() {
        binding.btn0.setOnClickListener { appendDigit('0') }
        binding.btn1.setOnClickListener { appendDigit('1') }
        binding.btn2.setOnClickListener { appendDigit('2') }
        binding.btn3.setOnClickListener { appendDigit('3') }
        binding.btn4.setOnClickListener { appendDigit('4') }
        binding.btn5.setOnClickListener { appendDigit('5') }
        binding.btn6.setOnClickListener { appendDigit('6') }
        binding.btn7.setOnClickListener { appendDigit('7') }
        binding.btn8.setOnClickListener { appendDigit('8') }
        binding.btn9.setOnClickListener { appendDigit('9') }
        binding.btnDot.setOnClickListener { appendDecimal() }
        binding.btnAdd.setOnClickListener { appendOperator('+') }
        binding.btnSub.setOnClickListener { appendOperator('-') }
        binding.btnMul.setOnClickListener { appendOperator('*') }
        binding.btnDiv.setOnClickListener { appendOperator('/') }
        binding.btnParenOpen.setOnClickListener { appendParenOpen() }
        binding.btnParenClose.setOnClickListener { appendParenClose() }
        binding.btnClear.setOnClickListener { clearAll() }
        binding.btnDelete.setOnClickListener { deleteLast() }
        binding.btnEquals.setOnClickListener { evaluateAndShow() }
    }

    /**
     * 追加数字并刷新显示区。
     */
    private fun appendDigit(d: Char) {
        Log.d(TAG, "input: digit '$d'")
        inputBuffer.appendDigit(d)
        refreshDisplay()
    }

    /**
     * 追加小数点并刷新显示区。
     */
    private fun appendDecimal() {
        Log.d(TAG, "input: decimal separator")
        inputBuffer.appendDecimalSeparator()
        refreshDisplay()
    }

    /**
     * 追加四则运算符并刷新显示区。
     */
    private fun appendOperator(op: Char) {
        Log.d(TAG, "input: operator '$op'")
        inputBuffer.appendOperator(op)
        refreshDisplay()
    }

    /**
     * 追加左括号并刷新显示区。
     */
    private fun appendParenOpen() {
        Log.d(TAG, "input: '('")
        inputBuffer.appendLeftParen()
        refreshDisplay()
    }

    /**
     * 追加右括号并刷新显示区。
     */
    private fun appendParenClose() {
        Log.d(TAG, "input: ')'")
        inputBuffer.appendRightParen()
        refreshDisplay()
    }

    /**
     * 清空输入并显示初始占位。
     */
    private fun clearAll() {
        Log.i(TAG, "input: clear all")
        inputBuffer.clear()
        refreshDisplay()
    }

    /**
     * 删除末字符并刷新显示区。
     */
    private fun deleteLast() {
        Log.d(TAG, "input: delete last char")
        inputBuffer.deleteLast()
        refreshDisplay()
    }

    /**
     * 对当前表达式求值；成功则将结果写回缓冲区并展示，失败则弹出简短提示。
     */
    private fun evaluateAndShow() {
        val expr = inputBuffer.getText()
        Log.d(TAG, "evaluate: expression=\"$expr\"")
        when (val outcome = engine.evaluate(expr)) {
            is CalculationOutcome.Success -> {
                val shown = formatter.formatResult(outcome.value)
                Log.i(TAG, "evaluate: success raw=${outcome.value} display=\"$shown\"")
                inputBuffer.replaceWith(shown)
                refreshDisplay()
            }
            is CalculationOutcome.Error -> {
                Log.e(TAG, "evaluate: failed code=${outcome.message}")
                val msg = when (outcome.message) {
                    "divide_by_zero" -> getString(R.string.error_div_zero)
                    "empty_expression" -> getString(R.string.display_hint)
                    else -> getString(R.string.error_invalid)
                }
                Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
            }
        }
    }

    /**
     * 根据 [CalculatorInputBuffer] 当前内容更新顶部 [android.widget.TextView]。
     */
    private fun refreshDisplay() {
        val t = inputBuffer.getText()
        binding.textDisplay.text = if (t.isEmpty()) {
            getString(R.string.display_hint)
        } else {
            t
        }
    }

    private companion object {
        private const val TAG = "CalcDemo"
    }
}
