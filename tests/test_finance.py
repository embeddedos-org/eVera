"""Tests for Finance agent tools."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest


@pytest.fixture
def finance_env(tmp_path):
    """Patch finance module DATA_DIR to tmp_path so tests use temp storage."""
    import vera.brain.agents.finance as fin_mod
    fin_mod.DATA_DIR = tmp_path
    return tmp_path


# ── CheckBalancesTool ───────────────────────────────────────────

class TestCheckBalances:
    @pytest.mark.asyncio
    async def test_no_accounts_returns_info(self, finance_env):
        from vera.brain.agents.finance import CheckBalancesTool
        tool = CheckBalancesTool()
        result = await tool.execute()
        assert result["status"] == "info"
        assert result["accounts"] == []
        assert "No bank accounts" in result["message"]

    @pytest.mark.asyncio
    async def test_with_accounts_returns_total(self, finance_env):
        from vera.brain.agents.finance import CheckBalancesTool
        data = {
            "accounts": [
                {"name": "Checking", "balance": 1500.50},
                {"name": "Savings", "balance": 3000.00},
            ],
            "last_updated": "2025-01-01T00:00:00",
        }
        (finance_env / "finance.json").write_text(json.dumps(data))

        tool = CheckBalancesTool()
        result = await tool.execute()
        assert result["status"] == "success"
        assert len(result["accounts"]) == 2
        assert result["total_balance"] == 4500.50
        assert result["last_updated"] == "2025-01-01T00:00:00"

    @pytest.mark.asyncio
    async def test_with_zero_balance_account(self, finance_env):
        from vera.brain.agents.finance import CheckBalancesTool
        data = {"accounts": [{"name": "Empty", "balance": 0}]}
        (finance_env / "finance.json").write_text(json.dumps(data))

        tool = CheckBalancesTool()
        result = await tool.execute()
        assert result["status"] == "success"
        assert result["total_balance"] == 0


# ── AddAccountTool ──────────────────────────────────────────────

class TestAddAccount:
    @pytest.mark.asyncio
    async def test_add_valid_account(self, finance_env):
        from vera.brain.agents.finance import AddAccountTool
        tool = AddAccountTool()
        result = await tool.execute(name="Chase Checking", balance=2500.00, type="checking")
        assert result["status"] == "success"
        assert result["account"]["name"] == "Chase Checking"
        assert result["account"]["balance"] == 2500.00
        assert result["account"]["type"] == "checking"
        assert result["account"]["currency"] == "USD"
        # Verify persisted to disk
        data = json.loads((finance_env / "finance.json").read_text())
        assert len(data["accounts"]) == 1

    @pytest.mark.asyncio
    async def test_add_account_empty_name_error(self, finance_env):
        from vera.brain.agents.finance import AddAccountTool
        tool = AddAccountTool()
        result = await tool.execute(name="", balance=100)
        assert result["status"] == "error"
        assert "name is required" in result["message"]

    @pytest.mark.asyncio
    async def test_add_multiple_accounts(self, finance_env):
        from vera.brain.agents.finance import AddAccountTool
        tool = AddAccountTool()
        await tool.execute(name="Account1", balance=100)
        await tool.execute(name="Account2", balance=200)
        data = json.loads((finance_env / "finance.json").read_text())
        assert len(data["accounts"]) == 2


# ── AddTransactionTool ──────────────────────────────────────────

class TestAddTransaction:
    @pytest.mark.asyncio
    async def test_expense_transaction(self, finance_env):
        from vera.brain.agents.finance import AddTransactionTool
        tool = AddTransactionTool()
        result = await tool.execute(description="Coffee", amount=-5.50, category="food")
        assert result["status"] == "success"
        assert result["transaction"]["amount"] == -5.50
        assert result["transaction"]["category"] == "food"
        assert "💸" in result["message"]

    @pytest.mark.asyncio
    async def test_income_transaction(self, finance_env):
        from vera.brain.agents.finance import AddTransactionTool
        tool = AddTransactionTool()
        result = await tool.execute(description="Paycheck", amount=3000.00, category="income")
        assert result["status"] == "success"
        assert result["transaction"]["amount"] == 3000.00
        assert "💰" in result["message"]

    @pytest.mark.asyncio
    async def test_empty_description_error(self, finance_env):
        from vera.brain.agents.finance import AddTransactionTool
        tool = AddTransactionTool()
        result = await tool.execute(description="", amount=50)
        assert result["status"] == "error"
        assert "description is required" in result["message"]

    @pytest.mark.asyncio
    async def test_transaction_persists_to_disk(self, finance_env):
        from vera.brain.agents.finance import AddTransactionTool
        tool = AddTransactionTool()
        await tool.execute(description="Groceries", amount=-42.00, category="food", account="chase")
        data = json.loads((finance_env / "finance.json").read_text())
        assert len(data["transactions"]) == 1
        assert data["transactions"][0]["description"] == "Groceries"
        assert data["transactions"][0]["account"] == "chase"


# ── ViewTransactionsTool ────────────────────────────────────────

class TestViewTransactions:
    @pytest.mark.asyncio
    async def test_no_transactions(self, finance_env):
        from vera.brain.agents.finance import ViewTransactionsTool
        tool = ViewTransactionsTool()
        result = await tool.execute()
        assert result["status"] == "success"
        assert result["transactions"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_filter_by_days(self, finance_env):
        from vera.brain.agents.finance import ViewTransactionsTool
        now = datetime.now()
        data = {
            "transactions": [
                {"description": "Recent", "amount": -10, "date": now.isoformat(), "category": "food"},
                {"description": "Old", "amount": -20, "date": (now - timedelta(days=30)).isoformat(), "category": "food"},
            ]
        }
        (finance_env / "finance.json").write_text(json.dumps(data))

        tool = ViewTransactionsTool()
        result = await tool.execute(days=7)
        assert result["count"] == 1
        assert result["transactions"][0]["description"] == "Recent"

    @pytest.mark.asyncio
    async def test_filter_by_category(self, finance_env):
        from vera.brain.agents.finance import ViewTransactionsTool
        now = datetime.now()
        data = {
            "transactions": [
                {"description": "Lunch", "amount": -15, "date": now.isoformat(), "category": "food"},
                {"description": "Uber", "amount": -25, "date": now.isoformat(), "category": "transport"},
            ]
        }
        (finance_env / "finance.json").write_text(json.dumps(data))

        tool = ViewTransactionsTool()
        result = await tool.execute(days=7, category="food")
        assert result["count"] == 1
        assert result["transactions"][0]["description"] == "Lunch"

    @pytest.mark.asyncio
    async def test_total_spent_and_income(self, finance_env):
        from vera.brain.agents.finance import ViewTransactionsTool
        now = datetime.now()
        data = {
            "transactions": [
                {"description": "Coffee", "amount": -5, "date": now.isoformat(), "category": "food"},
                {"description": "Lunch", "amount": -20, "date": now.isoformat(), "category": "food"},
                {"description": "Refund", "amount": 10, "date": now.isoformat(), "category": "other"},
            ]
        }
        (finance_env / "finance.json").write_text(json.dumps(data))

        tool = ViewTransactionsTool()
        result = await tool.execute(days=7)
        assert result["total_spent"] == 25.0
        assert result["total_income"] == 10.0

    @pytest.mark.asyncio
    async def test_filter_by_account(self, finance_env):
        from vera.brain.agents.finance import ViewTransactionsTool
        now = datetime.now()
        data = {
            "transactions": [
                {"description": "A", "amount": -10, "date": now.isoformat(), "account": "Chase", "category": "food"},
                {"description": "B", "amount": -20, "date": now.isoformat(), "account": "Wells", "category": "food"},
            ]
        }
        (finance_env / "finance.json").write_text(json.dumps(data))

        tool = ViewTransactionsTool()
        result = await tool.execute(days=7, account="chase")
        assert result["count"] == 1
        assert result["transactions"][0]["description"] == "A"


# ── SpendingAnalysisTool ────────────────────────────────────────

class TestSpendingAnalysis:
    @pytest.mark.asyncio
    async def test_analysis_with_transactions_and_budgets(self, finance_env):
        from vera.brain.agents.finance import SpendingAnalysisTool
        now = datetime.now()
        data = {
            "transactions": [
                {"description": "Groceries", "amount": -100, "date": now.isoformat(), "category": "food"},
                {"description": "Gas", "amount": -50, "date": now.isoformat(), "category": "transport"},
                {"description": "More food", "amount": -30, "date": now.isoformat(), "category": "food"},
            ],
            "budgets": {"food": 200, "transport": 100},
        }
        (finance_env / "finance.json").write_text(json.dumps(data))

        tool = SpendingAnalysisTool()
        result = await tool.execute(period="month")
        assert result["status"] == "success"
        analysis = result["analysis"]
        assert analysis["total_spent"] == 180.0
        assert analysis["transaction_count"] == 3
        assert "food" in analysis["categories"]
        assert analysis["categories"]["food"] == 130.0
        assert "budget_status" in analysis
        assert analysis["budget_status"]["food"]["spent"] == 130.0
        assert analysis["budget_status"]["food"]["remaining"] == 70.0

    @pytest.mark.asyncio
    async def test_analysis_no_transactions(self, finance_env):
        from vera.brain.agents.finance import SpendingAnalysisTool
        tool = SpendingAnalysisTool()
        result = await tool.execute()
        assert result["status"] == "success"
        assert result["analysis"]["total_spent"] == 0
        assert result["analysis"]["transaction_count"] == 0

    @pytest.mark.asyncio
    async def test_analysis_weekly_period(self, finance_env):
        from vera.brain.agents.finance import SpendingAnalysisTool
        now = datetime.now()
        data = {
            "transactions": [
                {"description": "Recent", "amount": -50, "date": now.isoformat(), "category": "food"},
                {"description": "Old", "amount": -100, "date": (now - timedelta(days=20)).isoformat(), "category": "food"},
            ]
        }
        (finance_env / "finance.json").write_text(json.dumps(data))

        tool = SpendingAnalysisTool()
        result = await tool.execute(period="week")
        assert result["analysis"]["total_spent"] == 50.0
        assert result["analysis"]["period"] == "week"


# ── SetBudgetTool ───────────────────────────────────────────────

class TestSetBudget:
    @pytest.mark.asyncio
    async def test_set_valid_budget(self, finance_env):
        from vera.brain.agents.finance import SetBudgetTool
        tool = SetBudgetTool()
        result = await tool.execute(category="food", amount=500)
        assert result["status"] == "success"
        assert result["category"] == "food"
        assert result["budget"] == 500
        assert "$500" in result["message"]
        # Verify persisted
        data = json.loads((finance_env / "finance.json").read_text())
        assert data["budgets"]["food"] == 500

    @pytest.mark.asyncio
    async def test_set_budget_empty_category_error(self, finance_env):
        from vera.brain.agents.finance import SetBudgetTool
        tool = SetBudgetTool()
        result = await tool.execute(category="", amount=100)
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_set_budget_zero_amount_error(self, finance_env):
        from vera.brain.agents.finance import SetBudgetTool
        tool = SetBudgetTool()
        result = await tool.execute(category="food", amount=0)
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_set_budget_negative_amount_error(self, finance_env):
        from vera.brain.agents.finance import SetBudgetTool
        tool = SetBudgetTool()
        result = await tool.execute(category="food", amount=-50)
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_set_budget_overwrites_existing(self, finance_env):
        from vera.brain.agents.finance import SetBudgetTool
        tool = SetBudgetTool()
        await tool.execute(category="food", amount=200)
        await tool.execute(category="food", amount=300)
        data = json.loads((finance_env / "finance.json").read_text())
        assert data["budgets"]["food"] == 300


# ── Helper functions ────────────────────────────────────────────

class TestHelpers:
    def test_ensure_data_dir_creates_dir(self, finance_env):
        from vera.brain.agents.finance import _ensure_data_dir
        result = _ensure_data_dir()
        assert result.exists()

    def test_load_json_nonexistent_returns_empty(self, finance_env):
        from vera.brain.agents.finance import _load_json
        result = _load_json("nonexistent.json")
        assert result == {}

    def test_load_json_corrupt_returns_empty(self, finance_env):
        from vera.brain.agents.finance import _load_json
        (finance_env / "corrupt.json").write_text("not valid json{{{")
        result = _load_json("corrupt.json")
        assert result == {}

    def test_save_and_load_roundtrip(self, finance_env):
        from vera.brain.agents.finance import _load_json, _save_json
        data = {"key": "value", "number": 42}
        _save_json("test.json", data)
        loaded = _load_json("test.json")
        assert loaded == data


# ── FinanceAgent registration ───────────────────────────────────

class TestFinanceAgent:
    def test_agent_has_six_tools(self):
        from vera.brain.agents.finance import FinanceAgent
        agent = FinanceAgent()
        assert len(agent.tools) == 6

    def test_agent_name(self):
        from vera.brain.agents.finance import FinanceAgent
        agent = FinanceAgent()
        assert agent.name == "finance"

    def test_agent_has_offline_responses(self):
        from vera.brain.agents.finance import FinanceAgent
        agent = FinanceAgent()
        assert len(agent.offline_responses) > 0
        assert "balance" in agent.offline_responses
