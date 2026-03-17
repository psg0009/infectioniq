import { Check } from 'lucide-react'

interface PricingTier {
  name: string
  monthly_price: number
  annual_price: number
  max_ors: number
  max_users: number
  features: string[]
  support_level: string
  is_custom: boolean
}

const TIERS: PricingTier[] = [
  {
    name: 'Starter',
    monthly_price: 2499,
    annual_price: 24990,
    max_ors: 2,
    max_users: 10,
    features: [
      'Real-time hand hygiene monitoring',
      'Basic compliance dashboard',
      'CSV report export',
      'Email alerts',
      'Standard risk scoring',
    ],
    support_level: 'Email (business hours)',
    is_custom: false,
  },
  {
    name: 'Professional',
    monthly_price: 4999,
    annual_price: 49990,
    max_ors: 8,
    max_users: 50,
    features: [
      'Everything in Starter',
      'Advanced analytics & trends',
      'SSO/SAML integration',
      'EMR/EHR integration (FHIR R4)',
      'Zone calibration UI',
      'Multi-OR dashboard',
      'Custom alert routing',
      'Camera health monitoring',
      'API access',
    ],
    support_level: 'Priority email + phone',
    is_custom: false,
  },
  {
    name: 'Enterprise',
    monthly_price: 0,
    annual_price: 0,
    max_ors: 999,
    max_users: 999,
    features: [
      'Everything in Professional',
      'Unlimited ORs and users',
      'Multi-tenant / multi-site',
      'Custom ML model training',
      'Clinical validation tools',
      'SOC2 compliance reports',
      'Dedicated success manager',
      'On-premise deployment option',
      'Custom integrations',
      'SLA guarantee (99.9%)',
    ],
    support_level: '24/7 dedicated support',
    is_custom: true,
  },
]

const fmt = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n)

export default function PricingPage() {
  return (
    <div className="space-y-8">
      <div className="text-center">
        <h1 className="text-3xl font-bold text-slate-900">Pricing</h1>
        <p className="text-slate-500 mt-2 max-w-xl mx-auto">
          Choose the plan that fits your facility. All plans include core infection prevention monitoring.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
        {TIERS.map((tier, i) => (
          <div
            key={tier.name}
            className={`bg-white rounded-xl shadow-sm border p-6 flex flex-col ${
              i === 1 ? 'border-blue-500 ring-2 ring-blue-100' : 'border-slate-200'
            }`}
          >
            {i === 1 && (
              <div className="text-center mb-2">
                <span className="text-xs font-semibold text-blue-600 bg-blue-50 px-3 py-1 rounded-full uppercase">
                  Most Popular
                </span>
              </div>
            )}

            <h3 className="text-xl font-bold text-slate-900">{tier.name}</h3>

            <div className="mt-3 mb-4">
              {tier.is_custom ? (
                <p className="text-3xl font-bold text-slate-900">Custom</p>
              ) : (
                <>
                  <p className="text-3xl font-bold text-slate-900">
                    {fmt(tier.monthly_price)}<span className="text-base font-normal text-slate-500">/mo</span>
                  </p>
                  <p className="text-sm text-slate-500">{fmt(tier.annual_price)}/year (save 17%)</p>
                </>
              )}
            </div>

            <p className="text-sm text-slate-600 mb-1">
              {tier.is_custom ? 'Unlimited ORs and users' : `Up to ${tier.max_ors} ORs, ${tier.max_users} users`}
            </p>
            <p className="text-sm text-slate-500 mb-4">{tier.support_level}</p>

            <ul className="space-y-2 flex-1">
              {tier.features.map((f) => (
                <li key={f} className="flex items-start gap-2 text-sm text-slate-700">
                  <Check className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
                  {f}
                </li>
              ))}
            </ul>

            <button
              type="button"
              onClick={() => {
                if (tier.is_custom) {
                  window.location.href = 'mailto:sales@infectioniq.com?subject=Enterprise%20Inquiry'
                } else {
                  window.location.href = '/login?plan=' + tier.name.toLowerCase()
                }
              }}
              className={`mt-6 w-full py-2.5 rounded-lg font-medium ${
                i === 1
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              {tier.is_custom ? 'Contact Sales' : 'Get Started'}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
