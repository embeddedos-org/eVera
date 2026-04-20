"""Safety policy engine — action approval rules.

@file voca/safety/policy.py
@brief Rule-based policy engine that determines whether agent actions
       should be allowed, require user confirmation, or be denied.

Each rule maps an `agent.tool` pattern to a PolicyAction (ALLOW/CONFIRM/DENY).
The PolicyService checks specific rules first, then wildcards, then falls back
to the config-level lists in SafetySettings.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from config import settings

logger = logging.getLogger(__name__)


class PolicyAction(str, Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


@dataclass
class PolicyDecision:
    """Result of a policy check."""

    action: PolicyAction
    reason: str
    agent_name: str
    tool_name: str


# Default rules keyed by "agent.tool" patterns
DEFAULT_RULES: dict[str, PolicyAction] = {
    # Companion — all safe
    "companion.*": PolicyAction.ALLOW,
    "companion.chat": PolicyAction.ALLOW,
    "companion.check_mood": PolicyAction.ALLOW,
    "companion.suggest_activity": PolicyAction.ALLOW,
    "companion.tell_joke": PolicyAction.ALLOW,
    "companion.greeting": PolicyAction.ALLOW,
    "companion.joke": PolicyAction.ALLOW,
    "companion.mood": PolicyAction.ALLOW,
    "companion.activity": PolicyAction.ALLOW,
    "companion.conversation": PolicyAction.ALLOW,
    # Home controller — mostly safe
    "home_controller.*": PolicyAction.ALLOW,
    "home_controller.control_light": PolicyAction.ALLOW,
    "home_controller.set_thermostat": PolicyAction.ALLOW,
    "home_controller.play_media": PolicyAction.ALLOW,
    "home_controller.lock_door": PolicyAction.CONFIRM,
    "home_controller.check_security": PolicyAction.ALLOW,
    # Life manager
    "life_manager.check_calendar": PolicyAction.ALLOW,
    "life_manager.list_todos": PolicyAction.ALLOW,
    "life_manager.create_reminder": PolicyAction.ALLOW,
    "life_manager.add_event": PolicyAction.ALLOW,
    "life_manager.send_email": PolicyAction.CONFIRM,
    "life_manager.schedule": PolicyAction.ALLOW,
    "life_manager.calendar": PolicyAction.ALLOW,
    "life_manager.email": PolicyAction.CONFIRM,
    "life_manager.reminder": PolicyAction.ALLOW,
    "life_manager.todo": PolicyAction.ALLOW,
    "life_manager.meeting": PolicyAction.ALLOW,
    "life_manager.appointment": PolicyAction.ALLOW,
    # Researcher — read-only
    "researcher.*": PolicyAction.ALLOW,
    # Writer — mostly safe
    "writer.*": PolicyAction.ALLOW,
    "writer.draft_text": PolicyAction.ALLOW,
    "writer.edit_text": PolicyAction.ALLOW,
    "writer.format_document": PolicyAction.ALLOW,
    "writer.translate": PolicyAction.ALLOW,
    # Operator — open apps is safe, scripts need confirmation
    "operator.open_app": PolicyAction.ALLOW,
    "operator.open_application": PolicyAction.ALLOW,
    "operator.screenshot": PolicyAction.ALLOW,
    "operator.take_screenshot": PolicyAction.ALLOW,
    "operator.execute_script": PolicyAction.CONFIRM,
    "operator.manage_files": PolicyAction.CONFIRM,
    "operator.type_text": PolicyAction.CONFIRM,
    # Operator — mouse & GUI (low risk)
    "operator.mouse_click": PolicyAction.ALLOW,
    "operator.mouse_move": PolicyAction.ALLOW,
    "operator.mouse_drag": PolicyAction.ALLOW,
    "operator.scroll": PolicyAction.ALLOW,
    "operator.press_hotkey": PolicyAction.ALLOW,
    # Operator — window management
    "operator.manage_window": PolicyAction.CONFIRM,
    # Operator — system admin
    "operator.manage_process": PolicyAction.CONFIRM,
    "operator.system_info": PolicyAction.ALLOW,
    "operator.manage_service": PolicyAction.CONFIRM,
    "operator.network_info": PolicyAction.ALLOW,
    "operator.clipboard": PolicyAction.CONFIRM,
    "operator.send_notification": PolicyAction.ALLOW,
    # Income — high-risk
    "income.*": PolicyAction.ALLOW,
    "income.scan_markets": PolicyAction.ALLOW,
    "income.analyze_opportunity": PolicyAction.ALLOW,
    "income.draft_content": PolicyAction.ALLOW,
    "income.track_leads": PolicyAction.CONFIRM,
    "income.transfer_money": PolicyAction.DENY,
    # Tier 0 intents — all safe
    "tier0.*": PolicyAction.ALLOW,
    # Coder — read is safe, write needs confirmation
    "coder.read_file": PolicyAction.ALLOW,
    "coder.search_in_files": PolicyAction.ALLOW,
    "coder.open_in_vscode": PolicyAction.ALLOW,
    "coder.write_file": PolicyAction.CONFIRM,
    "coder.edit_file": PolicyAction.CONFIRM,
    # Browser — browsing is safe, login and posting need confirmation
    "browser.navigate": PolicyAction.ALLOW,
    "browser.click": PolicyAction.ALLOW,
    "browser.extract_text": PolicyAction.ALLOW,
    "browser.page_screenshot": PolicyAction.ALLOW,
    "browser.analyze_page": PolicyAction.ALLOW,
    "browser.get_page_elements": PolicyAction.ALLOW,
    "browser.scroll": PolicyAction.ALLOW,
    "browser.go_back": PolicyAction.ALLOW,
    "browser.fill_form": PolicyAction.CONFIRM,
    "browser.login": PolicyAction.CONFIRM,
    "browser.type_in_browser": PolicyAction.CONFIRM,
    "browser.*": PolicyAction.ALLOW,
    # Income — real broker trades need confirmation
    "income.alpaca_trade": PolicyAction.CONFIRM,
    "income.ibkr_trade": PolicyAction.CONFIRM,
    "income.smart_trade": PolicyAction.CONFIRM,
    "income.get_stock_price": PolicyAction.ALLOW,
    "income.get_stock_history": PolicyAction.ALLOW,
    "income.view_portfolio": PolicyAction.ALLOW,
    "income.watchlist": PolicyAction.ALLOW,
    "income.market_overview": PolicyAction.ALLOW,
    "income.stock_news": PolicyAction.ALLOW,
    "income.paper_trade": PolicyAction.ALLOW,
    "income.alpaca_account": PolicyAction.ALLOW,
    "income.ibkr_account": PolicyAction.ALLOW,
    "income.tradingview_setup": PolicyAction.ALLOW,
    "income.automate_broker_app": PolicyAction.ALLOW,
    # Content creator — all safe except publishing
    "content_creator.generate_script": PolicyAction.ALLOW,
    "content_creator.create_video": PolicyAction.ALLOW,
    "content_creator.optimize_seo": PolicyAction.ALLOW,
    "content_creator.track_analytics": PolicyAction.ALLOW,
    "content_creator.schedule_post": PolicyAction.CONFIRM,
    # Finance — read-only is safe, no transfers ever
    "finance.check_balances": PolicyAction.ALLOW,
    "finance.view_transactions": PolicyAction.ALLOW,
    "finance.spending_analysis": PolicyAction.ALLOW,
    "finance.set_budget": PolicyAction.ALLOW,
    "finance.add_account": PolicyAction.ALLOW,
    "finance.add_transaction": PolicyAction.ALLOW,
    "finance.transfer_money": PolicyAction.DENY,
    "finance.make_payment": PolicyAction.DENY,
    "finance.*": PolicyAction.ALLOW,
    # Live trading plugin — ALL trades require confirmation
    "live_trader.ibkr_connect": PolicyAction.ALLOW,
    "live_trader.ibkr_portfolio": PolicyAction.ALLOW,
    "live_trader.ibkr_trade": PolicyAction.CONFIRM,
    "live_trader.tradestation_trade": PolicyAction.CONFIRM,
    "live_trader.tradestation_account": PolicyAction.ALLOW,
    "live_trader.schwab_trade": PolicyAction.CONFIRM,
    "live_trader.schwab_account": PolicyAction.ALLOW,
    "live_trader.ai_trading_decision": PolicyAction.ALLOW,
    "live_trader.run_strategy": PolicyAction.CONFIRM,
    "live_trader.risk_check": PolicyAction.ALLOW,
    # Email — reading is safe, sending/replying needs confirmation
    "life_manager.read_inbox": PolicyAction.ALLOW,
    "life_manager.read_email": PolicyAction.ALLOW,
    "life_manager.search_emails": PolicyAction.ALLOW,
    "life_manager.reply_email": PolicyAction.CONFIRM,
}


class PolicyService:
    """Evaluates whether an agent action should be allowed, confirmed, or denied.

    Uses a rules dictionary keyed by `agent.tool` patterns (e.g., "operator.execute_script").
    Supports wildcards (e.g., "companion.*") and falls back to SafetySettings lists.

    @param custom_rules: Optional dictionary to override or extend DEFAULT_RULES.
    """

    def __init__(self, custom_rules: dict[str, PolicyAction] | None = None) -> None:
        self._rules = dict(DEFAULT_RULES)
        if custom_rules:
            self._rules.update(custom_rules)

    def check(self, agent_name: str, tool_name: str, args: dict[str, Any] | None = None) -> PolicyDecision:
        """Check whether an action is allowed by policy.

        Evaluation order: specific rule (agent.tool) → wildcard (agent.*) →
        SafetySettings denied list → confirm list → allowed list → default CONFIRM.

        @param agent_name: Name of the agent requesting the action.
        @param tool_name: Name of the tool/intent to be executed.
        @param args: Optional arguments for context-aware rule evaluation.
        @return PolicyDecision with action (ALLOW/CONFIRM/DENY) and reason.
        """
        # Check specific rule first: "agent.tool"
        specific_key = f"{agent_name}.{tool_name}"
        if specific_key in self._rules:
            action = self._rules[specific_key]
            return PolicyDecision(
                action=action,
                reason=f"Rule match: {specific_key}",
                agent_name=agent_name,
                tool_name=tool_name,
            )

        # Check wildcard: "agent.*"
        wildcard_key = f"{agent_name}.*"
        if wildcard_key in self._rules:
            action = self._rules[wildcard_key]
            return PolicyDecision(
                action=action,
                reason=f"Wildcard match: {wildcard_key}",
                agent_name=agent_name,
                tool_name=tool_name,
            )

        # Check config-level lists
        if tool_name in settings.safety.denied_actions:
            return PolicyDecision(
                action=PolicyAction.DENY,
                reason=f"Tool '{tool_name}' in denied list",
                agent_name=agent_name,
                tool_name=tool_name,
            )
        if tool_name in settings.safety.confirm_actions:
            return PolicyDecision(
                action=PolicyAction.CONFIRM,
                reason=f"Tool '{tool_name}' requires confirmation",
                agent_name=agent_name,
                tool_name=tool_name,
            )
        if tool_name in settings.safety.allowed_actions:
            return PolicyDecision(
                action=PolicyAction.ALLOW,
                reason=f"Tool '{tool_name}' in allowed list",
                agent_name=agent_name,
                tool_name=tool_name,
            )

        # Default: require confirmation for unknown actions
        logger.warning("No policy rule for %s — defaulting to CONFIRM", specific_key)
        return PolicyDecision(
            action=PolicyAction.CONFIRM,
            reason=f"No rule found for {specific_key}; defaulting to confirm",
            agent_name=agent_name,
            tool_name=tool_name,
        )
