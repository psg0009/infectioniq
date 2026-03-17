"""
Subscription tier enforcement
Checks that the authenticated user's tier allows access to the requested feature.
"""

from fastapi import Depends, HTTPException, status
from app.core.auth_deps import get_current_active_user
from app.core.enums import SubscriptionTier
from app.models.user import User


# Map tier → allowed feature sets
TIER_FEATURES = {
    SubscriptionTier.TRIAL: {
        "dashboard", "cases", "compliance", "alerts", "staff",
        "dispensers", "analytics", "video", "roi",
    },
    SubscriptionTier.STARTER: {
        "dashboard", "cases", "compliance", "alerts", "staff",
        "dispensers", "analytics", "video", "roi", "reports_csv",
    },
    SubscriptionTier.PROFESSIONAL: {
        "dashboard", "cases", "compliance", "alerts", "staff",
        "dispensers", "analytics", "video", "roi", "reports_csv",
        "reports_html", "sso", "fhir", "calibration", "cameras",
        "consent", "api_access",
    },
    SubscriptionTier.ENTERPRISE: {
        "dashboard", "cases", "compliance", "alerts", "staff",
        "dispensers", "analytics", "video", "roi", "reports_csv",
        "reports_html", "sso", "fhir", "calibration", "cameras",
        "consent", "api_access", "validation", "multi_tenant",
        "custom_ml",
    },
}

# Map tier → max ORs
TIER_MAX_ORS = {
    SubscriptionTier.TRIAL: 1,
    SubscriptionTier.STARTER: 2,
    SubscriptionTier.PROFESSIONAL: 8,
    SubscriptionTier.ENTERPRISE: 999,
}


def require_feature(feature: str):
    """FastAPI dependency that checks the user's subscription tier allows a feature."""
    async def _check(user: User = Depends(get_current_active_user)):
        if user.is_superuser:
            return user
        tier = user.subscription_tier or SubscriptionTier.TRIAL
        allowed = TIER_FEATURES.get(tier, set())
        if feature not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature '{feature}' requires a higher subscription tier. "
                       f"Current tier: {tier.value}. Please upgrade.",
            )
        return user
    return _check


def require_tier(*tiers: SubscriptionTier):
    """FastAPI dependency that requires one of the specified subscription tiers."""
    async def _check(user: User = Depends(get_current_active_user)):
        if user.is_superuser:
            return user
        tier = user.subscription_tier or SubscriptionTier.TRIAL
        if tier not in tiers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires one of: {[t.value for t in tiers]}. "
                       f"Current tier: {tier.value}.",
            )
        return user
    return _check
