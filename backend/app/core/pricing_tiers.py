"""
Pricing Model Configuration
Defines pricing tiers for InfectionIQ
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PricingTier:
    name: str
    monthly_price: float
    annual_price: float  # annual total (discounted)
    max_ors: int
    max_users: int
    features: List[str]
    support_level: str
    storage_gb: int


PRICING_TIERS: List[PricingTier] = [
    PricingTier(
        name="Starter",
        monthly_price=2499,
        annual_price=24990,  # 2 months free
        max_ors=2,
        max_users=10,
        features=[
            "Real-time hand hygiene monitoring",
            "Basic compliance dashboard",
            "CSV report export",
            "Email alerts",
            "Standard risk scoring",
        ],
        support_level="Email (business hours)",
        storage_gb=50,
    ),
    PricingTier(
        name="Professional",
        monthly_price=4999,
        annual_price=49990,
        max_ors=8,
        max_users=50,
        features=[
            "Everything in Starter",
            "Advanced analytics & trends",
            "SSO/SAML integration",
            "EMR/EHR integration (FHIR R4)",
            "Zone calibration UI",
            "Multi-OR dashboard",
            "Custom alert routing",
            "Camera health monitoring",
            "API access",
        ],
        support_level="Priority email + phone",
        storage_gb=250,
    ),
    PricingTier(
        name="Enterprise",
        monthly_price=0,  # Custom pricing
        annual_price=0,
        max_ors=999,
        max_users=999,
        features=[
            "Everything in Professional",
            "Unlimited ORs and users",
            "Multi-tenant / multi-site",
            "Custom ML model training",
            "Clinical validation tools",
            "SOC2 compliance reports",
            "Dedicated success manager",
            "On-premise deployment option",
            "Custom integrations",
            "SLA guarantee (99.9%)",
        ],
        support_level="24/7 dedicated support",
        storage_gb=999,
    ),
]


def get_pricing() -> List[dict]:
    """Get pricing tiers as dict for API response"""
    return [
        {
            "name": t.name,
            "monthly_price": t.monthly_price,
            "annual_price": t.annual_price,
            "max_ors": t.max_ors,
            "max_users": t.max_users,
            "features": t.features,
            "support_level": t.support_level,
            "storage_gb": t.storage_gb,
            "is_custom": t.monthly_price == 0,
        }
        for t in PRICING_TIERS
    ]
