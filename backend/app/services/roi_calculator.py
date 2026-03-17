"""
ROI Calculator
Estimate return on investment from infection prevention improvements
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ROIInputs:
    annual_surgical_cases: int = 5000
    baseline_ssi_rate: float = 0.02  # 2%
    avg_ssi_cost: float = 25000  # USD per SSI case
    system_annual_cost: float = 50000  # InfectionIQ annual cost
    expected_ssi_reduction: float = 0.30  # 30% reduction with system
    implementation_cost: float = 25000  # one-time setup
    staff_training_hours: int = 40
    hourly_staff_rate: float = 50  # USD per hour


@dataclass
class ROIResult:
    baseline_ssi_cases: float
    baseline_ssi_cost: float
    projected_ssi_cases: float
    projected_ssi_cost: float
    annual_savings: float
    net_annual_savings: float
    first_year_savings: float
    roi_percent: float
    payback_months: float
    five_year_net_savings: float


def calculate_roi(inputs: ROIInputs) -> ROIResult:
    """Calculate ROI metrics for InfectionIQ implementation"""

    # Baseline costs
    baseline_ssi_cases = inputs.annual_surgical_cases * inputs.baseline_ssi_rate
    baseline_ssi_cost = baseline_ssi_cases * inputs.avg_ssi_cost

    # Projected with system
    reduced_rate = inputs.baseline_ssi_rate * (1 - inputs.expected_ssi_reduction)
    projected_ssi_cases = inputs.annual_surgical_cases * reduced_rate
    projected_ssi_cost = projected_ssi_cases * inputs.avg_ssi_cost

    # Savings
    annual_savings = baseline_ssi_cost - projected_ssi_cost
    training_cost = inputs.staff_training_hours * inputs.hourly_staff_rate
    total_annual_cost = inputs.system_annual_cost
    net_annual_savings = annual_savings - total_annual_cost

    # First year includes implementation
    first_year_cost = total_annual_cost + inputs.implementation_cost + training_cost
    first_year_savings = annual_savings - first_year_cost

    # ROI and payback
    total_investment = first_year_cost
    roi_percent = (net_annual_savings / total_investment * 100) if total_investment > 0 else 0

    if net_annual_savings > 0:
        payback_months = (total_investment / net_annual_savings) * 12
    else:
        payback_months = float("inf")

    # 5-year projection
    five_year_net = first_year_savings + (net_annual_savings * 4)

    return ROIResult(
        baseline_ssi_cases=round(baseline_ssi_cases, 1),
        baseline_ssi_cost=round(baseline_ssi_cost, 2),
        projected_ssi_cases=round(projected_ssi_cases, 1),
        projected_ssi_cost=round(projected_ssi_cost, 2),
        annual_savings=round(annual_savings, 2),
        net_annual_savings=round(net_annual_savings, 2),
        first_year_savings=round(first_year_savings, 2),
        roi_percent=round(roi_percent, 1),
        payback_months=round(payback_months, 1),
        five_year_net_savings=round(five_year_net, 2),
    )
