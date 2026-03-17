import { useState } from 'react'
import { Calculator, DollarSign, TrendingUp, Clock } from 'lucide-react'
import { apiFetch } from '../utils/api'

interface ROIResult {
  baseline_ssi_cases: number
  baseline_ssi_cost: number
  projected_ssi_cases: number
  projected_ssi_cost: number
  annual_savings: number
  net_annual_savings: number
  first_year_savings: number
  roi_percent: number
  payback_months: number
  five_year_net_savings: number
}

export default function ROICalculatorPage() {
  const [inputs, setInputs] = useState({
    annual_surgical_cases: 5000,
    baseline_ssi_rate: 0.02,
    avg_ssi_cost: 25000,
    system_annual_cost: 50000,
    expected_ssi_reduction: 0.30,
    implementation_cost: 25000,
    staff_training_hours: 40,
    hourly_staff_rate: 50,
  })
  const [result, setResult] = useState<ROIResult | null>(null)
  const [loading, setLoading] = useState(false)

  const handleCalculate = async () => {
    setLoading(true)
    try {
      const data = await apiFetch<{ results: ROIResult }>('/api/v1/roi/calculate', {
        method: 'POST',
        body: JSON.stringify(inputs),
      })
      setResult(data.results)
    } catch {
      // Calculate locally as fallback
      const baselineCases = inputs.annual_surgical_cases * inputs.baseline_ssi_rate
      const baselineCost = baselineCases * inputs.avg_ssi_cost
      const projectedCases = inputs.annual_surgical_cases * inputs.baseline_ssi_rate * (1 - inputs.expected_ssi_reduction)
      const projectedCost = projectedCases * inputs.avg_ssi_cost
      const annualSavings = baselineCost - projectedCost
      const netAnnual = annualSavings - inputs.system_annual_cost
      const firstYearCost = inputs.system_annual_cost + inputs.implementation_cost + inputs.staff_training_hours * inputs.hourly_staff_rate
      setResult({
        baseline_ssi_cases: baselineCases,
        baseline_ssi_cost: baselineCost,
        projected_ssi_cases: projectedCases,
        projected_ssi_cost: projectedCost,
        annual_savings: annualSavings,
        net_annual_savings: netAnnual,
        first_year_savings: annualSavings - firstYearCost,
        roi_percent: (netAnnual / firstYearCost) * 100,
        payback_months: netAnnual > 0 ? (firstYearCost / netAnnual) * 12 : Infinity,
        five_year_net_savings: (annualSavings - firstYearCost) + netAnnual * 4,
      })
    } finally {
      setLoading(false)
    }
  }

  const fmt = (n: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n)

  const fields = [
    { key: 'annual_surgical_cases', label: 'Annual Surgical Cases', type: 'number' },
    { key: 'baseline_ssi_rate', label: 'Baseline SSI Rate', type: 'number', step: 0.001 },
    { key: 'avg_ssi_cost', label: 'Avg Cost per SSI ($)', type: 'number' },
    { key: 'system_annual_cost', label: 'System Annual Cost ($)', type: 'number' },
    { key: 'expected_ssi_reduction', label: 'Expected SSI Reduction (%)', type: 'number', step: 0.01 },
    { key: 'implementation_cost', label: 'Implementation Cost ($)', type: 'number' },
    { key: 'staff_training_hours', label: 'Training Hours', type: 'number' },
    { key: 'hourly_staff_rate', label: 'Hourly Staff Rate ($)', type: 'number' },
  ] as const

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">ROI Calculator</h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1">Estimate return on investment from InfectionIQ</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-card dark:shadow-none border border-slate-100 dark:border-slate-700 p-6">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">Parameters</h2>
          <div className="grid grid-cols-2 gap-4">
            {fields.map((f) => (
              <div key={f.key}>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">{f.label}</label>
                <input
                  type={f.type}
                  step={'step' in f ? f.step : undefined}
                  title={f.label}
                  value={inputs[f.key]}
                  onChange={(e) => setInputs({ ...inputs, [f.key]: Number(e.target.value) })}
                  className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white rounded-lg focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 outline-none text-sm"
                />
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={handleCalculate}
            disabled={loading}
            className="mt-4 w-full bg-gradient-brand text-white py-2.5 rounded-xl font-semibold hover:opacity-90 shadow-glow-brand disabled:opacity-50 flex items-center justify-center gap-2"
          >
            <Calculator className="w-4 h-4" />
            {loading ? 'Calculating...' : 'Calculate ROI'}
          </button>
        </div>

        {result && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-green-50 rounded-xl border border-green-200 p-4">
                <div className="flex items-center gap-2 mb-1">
                  <DollarSign className="w-4 h-4 text-green-600" />
                  <span className="text-sm text-green-700 font-medium">Net Annual Savings</span>
                </div>
                <p className="text-2xl font-bold text-green-800">{fmt(result.net_annual_savings)}</p>
              </div>
              <div className="bg-blue-50 rounded-xl border border-blue-200 p-4">
                <div className="flex items-center gap-2 mb-1">
                  <TrendingUp className="w-4 h-4 text-blue-600" />
                  <span className="text-sm text-blue-700 font-medium">ROI</span>
                </div>
                <p className="text-2xl font-bold text-blue-800">{result.roi_percent.toFixed(1)}%</p>
              </div>
              <div className="bg-purple-50 rounded-xl border border-purple-200 p-4">
                <div className="flex items-center gap-2 mb-1">
                  <Clock className="w-4 h-4 text-purple-600" />
                  <span className="text-sm text-purple-700 font-medium">Payback Period</span>
                </div>
                <p className="text-2xl font-bold text-purple-800">{result.payback_months.toFixed(1)} mo</p>
              </div>
              <div className="bg-amber-50 rounded-xl border border-amber-200 p-4">
                <div className="flex items-center gap-2 mb-1">
                  <DollarSign className="w-4 h-4 text-amber-600" />
                  <span className="text-sm text-amber-700 font-medium">5-Year Net Savings</span>
                </div>
                <p className="text-2xl font-bold text-amber-800">{fmt(result.five_year_net_savings)}</p>
              </div>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-card dark:shadow-none border border-slate-100 dark:border-slate-700 p-5">
              <h3 className="font-semibold text-slate-900 dark:text-white mb-3">Details</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-slate-600 dark:text-slate-400">Baseline SSI Cases/Year</span><span className="font-medium dark:text-white">{result.baseline_ssi_cases.toFixed(1)}</span></div>
                <div className="flex justify-between"><span className="text-slate-600 dark:text-slate-400">Projected SSI Cases/Year</span><span className="font-medium dark:text-white">{result.projected_ssi_cases.toFixed(1)}</span></div>
                <div className="flex justify-between"><span className="text-slate-600 dark:text-slate-400">Baseline SSI Cost</span><span className="font-medium dark:text-white">{fmt(result.baseline_ssi_cost)}</span></div>
                <div className="flex justify-between"><span className="text-slate-600 dark:text-slate-400">Projected SSI Cost</span><span className="font-medium dark:text-white">{fmt(result.projected_ssi_cost)}</span></div>
                <div className="flex justify-between border-t border-slate-200 dark:border-slate-700 pt-2"><span className="text-slate-600 dark:text-slate-400">Gross Annual Savings</span><span className="font-medium text-green-700">{fmt(result.annual_savings)}</span></div>
                <div className="flex justify-between"><span className="text-slate-600 dark:text-slate-400">First Year Net Savings</span><span className="font-medium dark:text-white">{fmt(result.first_year_savings)}</span></div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
