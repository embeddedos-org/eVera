"""Finance Agent — bank account monitoring and budget tracking.

@file voca/brain/agents/finance.py
@brief Read-only bank account monitoring via Plaid API.
       Tracks balances, transactions, spending alerts, and budgets.
       Safety: ALL transfer/payment actions are DENIED.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from voca.brain.agents.base import BaseAgent, Tool
from voca.providers.models import ModelTier

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"


def _ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def _load_json(filename: str) -> dict:
    path = _ensure_data_dir() / filename
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _save_json(filename: str, data: dict) -> None:
    path = _ensure_data_dir() / filename
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


class CheckBalancesTool(Tool):
    """Check bank account balances."""

    def __init__(self) -> None:
        super().__init__(
            name="check_balances",
            description="Check all linked bank account balances",
            parameters={},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        plaid_key = os.getenv("VOCA_PLAID_CLIENT_ID")

        if plaid_key:
            return await self._fetch_plaid_balances()

        # Use local mock/manual data
        finance = _load_json("finance.json")
        accounts = finance.get("accounts", [])

        if not accounts:
            return {
                "status": "info",
                "message": "No bank accounts linked. Set VOCA_PLAID_CLIENT_ID and VOCA_PLAID_SECRET in .env for Plaid, "
                           "or manually add accounts via add_account tool.",
                "accounts": [],
            }

        total = sum(a.get("balance", 0) for a in accounts)
        return {
            "status": "success",
            "accounts": accounts,
            "total_balance": round(total, 2),
            "last_updated": finance.get("last_updated", "unknown"),
        }

    async def _fetch_plaid_balances(self) -> dict[str, Any]:
        try:
            import plaid
            from plaid.api import plaid_api
            from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest

            client_id = os.getenv("VOCA_PLAID_CLIENT_ID")
            secret = os.getenv("VOCA_PLAID_SECRET")
            access_token = os.getenv("VOCA_PLAID_ACCESS_TOKEN")
            env = os.getenv("VOCA_PLAID_ENV", "sandbox")

            if not access_token:
                return {"status": "error", "message": "VOCA_PLAID_ACCESS_TOKEN not set. Complete Plaid Link flow first."}

            host_map = {"sandbox": plaid.Environment.Sandbox, "development": plaid.Environment.Development, "production": plaid.Environment.Production}
            configuration = plaid.Configuration(host=host_map.get(env, plaid.Environment.Sandbox), api_key={"clientId": client_id, "secret": secret})
            api_client = plaid.ApiClient(configuration)
            client = plaid_api.PlaidApi(api_client)

            request = AccountsBalanceGetRequest(access_token=access_token)
            response = client.accounts_balance_get(request)

            accounts = []
            for acct in response.accounts:
                accounts.append({
                    "name": acct.name,
                    "type": acct.type.value,
                    "subtype": acct.subtype.value if acct.subtype else "",
                    "balance": acct.balances.current,
                    "available": acct.balances.available,
                    "currency": acct.balances.iso_currency_code or "USD",
                })

            return {"status": "success", "accounts": accounts, "total_balance": sum(a["balance"] or 0 for a in accounts)}
        except ImportError:
            return {"status": "error", "message": "plaid-python not installed. Run: pip install plaid-python"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class ViewTransactionsTool(Tool):
    """View recent bank transactions."""

    def __init__(self) -> None:
        super().__init__(
            name="view_transactions",
            description="View recent bank transactions (read-only)",
            parameters={
                "days": {"type": "int", "description": "Number of days to look back (default: 7)"},
                "category": {"type": "str", "description": "Filter by category: food, transport, shopping, bills, all"},
                "account": {"type": "str", "description": "Account name filter"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        days = int(kwargs.get("days", 7))
        category = kwargs.get("category", "all").lower()
        account_filter = kwargs.get("account", "")

        finance = _load_json("finance.json")
        transactions = finance.get("transactions", [])

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        filtered = [t for t in transactions if t.get("date", "") >= cutoff]

        if category != "all":
            filtered = [t for t in filtered if t.get("category", "").lower() == category]
        if account_filter:
            filtered = [t for t in filtered if account_filter.lower() in t.get("account", "").lower()]

        filtered.sort(key=lambda t: t.get("date", ""), reverse=True)
        total_spent = sum(t.get("amount", 0) for t in filtered if t.get("amount", 0) < 0)
        total_income = sum(t.get("amount", 0) for t in filtered if t.get("amount", 0) > 0)

        return {
            "status": "success",
            "transactions": filtered[:30],
            "count": len(filtered),
            "total_spent": round(abs(total_spent), 2),
            "total_income": round(total_income, 2),
            "period": f"Last {days} days",
        }


class SpendingAnalysisTool(Tool):
    """Analyze spending patterns and budget tracking."""

    def __init__(self) -> None:
        super().__init__(
            name="spending_analysis",
            description="Analyze spending patterns by category with budget comparison",
            parameters={
                "period": {"type": "str", "description": "Period: week, month, year (default: month)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        period = kwargs.get("period", "month").lower()

        finance = _load_json("finance.json")
        transactions = finance.get("transactions", [])
        budgets = finance.get("budgets", {})

        days_map = {"week": 7, "month": 30, "year": 365}
        days = days_map.get(period, 30)
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        recent = [t for t in transactions if t.get("date", "") >= cutoff and t.get("amount", 0) < 0]

        by_category: dict[str, float] = {}
        for t in recent:
            cat = t.get("category", "Other")
            by_category[cat] = by_category.get(cat, 0) + abs(t.get("amount", 0))

        total = sum(by_category.values())

        analysis = {
            "period": period,
            "total_spent": round(total, 2),
            "categories": {k: round(v, 2) for k, v in sorted(by_category.items(), key=lambda x: x[1], reverse=True)},
            "transaction_count": len(recent),
            "daily_average": round(total / max(days, 1), 2),
        }

        if budgets:
            analysis["budget_status"] = {}
            for cat, limit in budgets.items():
                spent = by_category.get(cat, 0)
                analysis["budget_status"][cat] = {
                    "budget": limit,
                    "spent": round(spent, 2),
                    "remaining": round(limit - spent, 2),
                    "percent_used": round((spent / limit) * 100, 1) if limit > 0 else 0,
                }

        return {"status": "success", "analysis": analysis}


class SetBudgetTool(Tool):
    """Set a monthly spending budget by category."""

    def __init__(self) -> None:
        super().__init__(
            name="set_budget",
            description="Set a monthly spending budget for a category",
            parameters={
                "category": {"type": "str", "description": "Spending category: food, transport, shopping, bills, entertainment"},
                "amount": {"type": "float", "description": "Monthly budget amount in dollars"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        category = kwargs.get("category", "")
        amount = float(kwargs.get("amount", 0))

        if not category or amount <= 0:
            return {"status": "error", "message": "Both category and a positive amount are required"}

        finance = _load_json("finance.json")
        if "budgets" not in finance:
            finance["budgets"] = {}

        finance["budgets"][category] = amount
        _save_json("finance.json", finance)

        return {"status": "success", "category": category, "budget": amount, "message": f"Budget set: ${amount}/month for {category}"}


class AddAccountTool(Tool):
    """Manually add a bank account for tracking."""

    def __init__(self) -> None:
        super().__init__(
            name="add_account",
            description="Manually add a bank account for balance tracking",
            parameters={
                "name": {"type": "str", "description": "Account name (e.g. 'Chase Checking')"},
                "balance": {"type": "float", "description": "Current balance"},
                "type": {"type": "str", "description": "Account type: checking, savings, credit"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        name = kwargs.get("name", "")
        balance = float(kwargs.get("balance", 0))
        acct_type = kwargs.get("type", "checking")

        if not name:
            return {"status": "error", "message": "Account name is required"}

        finance = _load_json("finance.json")
        if "accounts" not in finance:
            finance["accounts"] = []

        account = {
            "name": name,
            "type": acct_type,
            "balance": balance,
            "currency": "USD",
            "added": datetime.now().isoformat(),
        }
        finance["accounts"].append(account)
        finance["last_updated"] = datetime.now().isoformat()
        _save_json("finance.json", finance)

        return {"status": "success", "account": account}


class AddTransactionTool(Tool):
    """Manually log a transaction."""

    def __init__(self) -> None:
        super().__init__(
            name="add_transaction",
            description="Manually log a transaction (negative = expense, positive = income)",
            parameters={
                "description": {"type": "str", "description": "Transaction description"},
                "amount": {"type": "float", "description": "Amount (negative for expense, positive for income)"},
                "category": {"type": "str", "description": "Category: food, transport, shopping, bills, entertainment, income, other"},
                "account": {"type": "str", "description": "Account name"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        desc = kwargs.get("description", "")
        amount = float(kwargs.get("amount", 0))
        category = kwargs.get("category", "other")
        account = kwargs.get("account", "default")

        if not desc:
            return {"status": "error", "message": "Transaction description is required"}

        finance = _load_json("finance.json")
        if "transactions" not in finance:
            finance["transactions"] = []

        txn = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "description": desc,
            "amount": amount,
            "category": category,
            "account": account,
            "date": datetime.now().isoformat(),
        }
        finance["transactions"].append(txn)
        _save_json("finance.json", finance)

        emoji = "💸" if amount < 0 else "💰"
        return {"status": "success", "transaction": txn, "message": f"{emoji} Logged: {desc} ${abs(amount):.2f}"}


class FinanceAgent(BaseAgent):
    """Monitors bank accounts, tracks spending, and manages budgets.

    Read-only bank access via Plaid API or manual entry.
    Safety: ALL money transfer/payment actions are DENIED by policy.
    """

    name = "finance"
    description = "Monitors bank accounts, tracks spending, manages budgets (read-only, no transfers)"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are a personal finance assistant. You help users track bank account balances, "
        "monitor transactions, analyze spending patterns, and manage budgets. "
        "You NEVER transfer money, make payments, or modify bank accounts. "
        "All access is READ-ONLY for safety. Use check_balances to see account balances, "
        "view_transactions for recent activity, spending_analysis for patterns, "
        "and set_budget to create spending limits. Be helpful and financially aware."
    )

    offline_responses = {
        "balance": "💰 Let me check your account balances!",
        "transaction": "📊 I'll look up your recent transactions!",
        "budget": "💳 I'll help you with your budget!",
        "spending": "📈 Let me analyze your spending!",
        "bank": "🏦 I'll check your bank info!",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            CheckBalancesTool(),
            ViewTransactionsTool(),
            SpendingAnalysisTool(),
            SetBudgetTool(),
            AddAccountTool(),
            AddTransactionTool(),
        ]
