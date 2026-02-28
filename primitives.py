# --------------------------------------------------
# external
# --------------------------------------------------
from enum import Enum
from typing import List, Optional
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from jinja2 import Environment, FileSystemLoader

# --------------------------------------------------
# local
# --------------------------------------------------
from helpers import parse_money


@dataclass
class BudgetMetadata:
    name: str
    spreadsheet_url: str


class ExpenseType(Enum):
    Expendable = 1
    Saving = 2
    RequiredPayment = 3

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def description(self):
        match self:
            case ExpenseType.Expendable:
                return "`Expendable` expenses are those which are used daily, without any committed savings or bills. For example, groceries, entertainment, transportation, etc."
            case ExpenseType.Saving:
                return "`Saving` expenses are those which must not be spent, since they are being saved for future use. For example, dates, vacations, investments, etc."
            case ExpenseType.RequiredPayment:
                return "`Required Payment` expenses are those which must be paid each month. For example, rent/bills, insurance, credit card payments, student loans, etc."


class BssCategory(Enum):
    Spending = 1
    Bills = 2
    Savings = 3


@dataclass
class BssSpent:
    category: BssCategory
    amount: float

    @classmethod
    def from_rows(cls, rows: List[List[str]]) -> List["BssSpent"]:
        result: List["BssSpent"] = []
        i = 0
        while i < len(rows):
            # --------------------------------------------------
            # skip empty rows
            # --------------------------------------------------
            if not rows[i] or not rows[i][0].strip():
                i += 1
                continue
            # --------------------------------------------------
            # get category
            # --------------------------------------------------
            category_str = rows[i][0].strip().lower()
            if "bill" in category_str:
                category = BssCategory.Bills
            elif "sav" in category_str:
                category = BssCategory.Savings
            else:
                category = BssCategory.Spending
            # --------------------------------------------------
            # get amount
            # --------------------------------------------------
            amount = 0.0
            if i + 1 < len(rows):
                amount = parse_money(rows[i + 1][0])
            i += 2
            result.append(cls(category=category, amount=amount))
        return result


@dataclass
class Bss:
    elements: List[BssSpent]

    @classmethod
    def from_rows(cls, rows: List[List[str]]) -> "Bss":
        return cls(elements=BssSpent.from_rows(rows))

    def spending(self) -> float:
        return sum(
            bss.amount for bss in self.elements if bss.category == BssCategory.Spending
        )

    def bills(self) -> float:
        return sum(
            bss.amount for bss in self.elements if bss.category == BssCategory.Bills
        )

    def savings(self) -> float:
        return sum(
            bss.amount for bss in self.elements if bss.category == BssCategory.Savings
        )

    def total(self) -> float:
        return sum(bss.amount for bss in self.elements)


@dataclass
# --------------------------------------------------
# this is found in "Payments" column of `Budgeting` sheet,
# where an overview of general payments w.r.t. categories
# is presented.
#
# note that this does not break down to sub-categories
# ------------------------------------------------
class PaymentsOverview:
    category: str
    amount: float

    @classmethod
    # column 0: category
    # column 1: amount (payments)
    # column 2: amount (savings)
    # ...
    def from_row(cls, row: List[str]) -> Optional["PaymentsOverview"]:
        amount = parse_money(row[1])
        if amount == 0.0:
            return None
        return cls(category=row[0], amount=amount)

    @classmethod
    # column 0: category
    # column 1: amount (payments)
    # column 2: amount (savings)
    # ...
    def from_range(cls, rows: List[List[str]]) -> List["PaymentsOverview"]:
        return [
            r for row in rows for r in [PaymentsOverview.from_row(row)] if r is not None
        ]


@dataclass
# --------------------------------------------------
# this is found in "To Save" column of `Budgeting` sheet,
# where an overview of general payments w.r.t. categories
# is presented.
#
# note that this does not break down to sub-categories
# ------------------------------------------------
class SavingsOverview:
    category: str
    amount: float

    @classmethod
    # column 0: category
    # column 1: amount (payments)
    # column 2: amount (savings)
    # ...
    def from_row(cls, row: List[str]) -> Optional["SavingsOverview"]:
        amount = parse_money(row[2])
        if amount == 0.0:
            return None
        return cls(category=row[0], amount=amount)

    @classmethod
    # column 0: category
    # column 1: amount (payments)
    # column 2: amount (savings)
    # ...
    def from_range(cls, rows: List[List[str]]) -> List["SavingsOverview"]:
        return [
            r for row in rows for r in [SavingsOverview.from_row(row)] if r is not None
        ]


@dataclass
class SpendableOverview:
    category: str
    spendable_amount: float
    future_daily: float
    left_today: float

    @classmethod
    # column 0: category
    # column 1: spendable amount
    # column 2: future daily
    # column 3: left today
    def from_row(cls, row: List[str]) -> "SpendableOverview":
        spendable_amount = parse_money(row[1])
        future_daily = parse_money(row[2])
        left_today = parse_money(row[3])
        return cls(
            category=row[0],
            spendable_amount=spendable_amount,
            future_daily=future_daily,
            left_today=left_today,
        )

    @classmethod
    # column 0: category
    # column 1: spendable amount
    # column 2: future daily
    # column 3: left today
    def from_range(cls, rows: List[List[str]]) -> List["SpendableOverview"]:
        return [SpendableOverview.from_row(row) for row in rows]


@dataclass
class TransferOverview:
    from_account: str
    to_account: str
    amount: float

    @classmethod
    # column 0: from account
    # column 1: to account
    # column 2: amount
    def from_row(cls, row: List[str]) -> Optional["TransferOverview"]:
        amount = parse_money(row[2])
        if amount == 0.0:
            return None
        return cls(
            from_account=row[0],
            to_account=row[1],
            amount=amount,
        )

    @classmethod
    # column 0: from account
    # column 1: to account
    # column 2: amount
    def from_range(cls, rows: List[List[str]]) -> List["TransferOverview"]:
        return [
            r for row in rows for r in [TransferOverview.from_row(row)] if r is not None
        ]


@dataclass
class Budget:
    category: str
    subcategory: Optional[str]
    amount: float
    timeframe: float
    description: str
    expense_type: ExpenseType
    paid_from: Optional[str]
    next_approx_payment: Optional[date]

    @classmethod
    # column 0: category
    # column 1: amount
    # column 2: description
    # column 3: is per-day expendable?
    def from_manual_budget_row(cls, period_size: float, row: List[str]) -> "Budget":
        category = row[0].strip()
        detailed_description = row[2].strip()
        description = (category, category + " / " + detailed_description)[
            bool(detailed_description)
        ]
        match str(row[3]):  # Is Per-Day Expendable?
            case "FALSE":
                expense_type = ExpenseType.RequiredPayment
            case _:
                expense_type = ExpenseType.Expendable
        return cls(
            category=category,
            subcategory=None,
            amount=parse_money(row[1]),
            timeframe=period_size,
            description=description,
            expense_type=expense_type,
            paid_from=None,
            next_approx_payment=None,
        )

    @classmethod
    # column 0: category
    # column 1: amount
    # column 2: description
    # column 3: is per-day expendable?
    def from_manual_budget_range(
        cls, period_size: float, rows: List[List[str]]
    ) -> List["Budget"]:
        return [cls.from_manual_budget_row(period_size, row) for row in rows]

    @classmethod
    # column 0: subcategory
    # column 1: description
    # column 2: amount
    # column 3: time (days)
    # column 4: is saving?
    # column 5: paid from
    # column 6 (unused): adjusted start date
    # column 7: next approx payment date
    def from_recurring_budget_row(
        cls, cat2subcat: dict[str, List[str]], row: List[str]
    ) -> "Budget":
        subcategory = row[0].strip()
        description = row[1].strip()
        amount = parse_money(row[2])
        timeframe = float(row[3])
        match str(row[4]):  # Is Saving?
            case "FALSE":
                expense_type = ExpenseType.RequiredPayment
            case _:
                expense_type = ExpenseType.Saving
        paid_from = row[5].strip()
        next_approx_payment = datetime.strptime(row[7].strip(), "%m/%d/%Y").date()
        category = None
        for cat in cat2subcat:
            if subcategory in cat2subcat[cat]:
                category = cat
                break
        if not category:
            raise Exception(
                f"Could not find category for subcategory {subcategory}, this is impossible."
            )
        return cls(
            category=category,
            subcategory=subcategory,
            amount=amount,
            timeframe=timeframe,
            description=description,
            expense_type=expense_type,
            paid_from=paid_from,
            next_approx_payment=next_approx_payment,
        )

    @classmethod
    # column 0: subcategory
    # column 1: description
    # column 2: amount
    # column 3: time (days)
    # column 4: is saving?
    # column 5: paid from
    # column 6 (unused): adjusted start date
    # column 7: next approx payment date
    def from_recurring_budget_range(
        cls, cat2subcat: dict[str, List[str]], rows: List[List[str]]
    ) -> List["Budget"]:
        return [cls.from_recurring_budget_row(cat2subcat, row) for row in rows]


@dataclass
class AccountBalance:
    name: str
    amount_manual: float
    amount_calc: float
    amount_diff: float

    @classmethod
    # column 0: name
    # column 1: amount @ start
    # column 2: amount (calc.)
    # column 3: amount (actual / manual)
    def from_rows(cls, rows: List[List[str]]) -> List["AccountBalance"]:
        result: List["AccountBalance"] = []
        for row in rows:
            name = row[0].strip()
            amount_calc = parse_money(row[2])
            amount_manual = parse_money(row[3])
            amount_diff = amount_manual - amount_calc
            result.append(
                cls(
                    name=name,
                    amount_manual=amount_manual,
                    amount_calc=amount_calc,
                    amount_diff=amount_diff,
                )
            )
        return result


@dataclass
class BudgetStats:
    # --------------------------------------------------
    # income account (name of account where income is received, e.g. "Checking")
    # --------------------------------------------------
    income_account: str

    # --------------------------------------------------
    # total budget
    # --------------------------------------------------
    total_budget: float
    # --------------------------------------------------
    # income @ period start
    # --------------------------------------------------
    income_at_period_start: float
    # --------------------------------------------------
    # the amount in checking account, at the start of the period
    # upon being paid
    # --------------------------------------------------
    checking_amount_period_start: float

    # --------------------------------------------------
    # the total amount of REQUIRED expenses during this
    # period. See `ExpenseType.RequiredPayment`
    # --------------------------------------------------
    total_withheld_required_payments: float
    # --------------------------------------------------
    # the total amount of SAVINGS during this period. See
    # `ExpenseType.Saving`
    # --------------------------------------------------
    total_withheld_savings: float

    # --------------------------------------------------
    # the checking balance after withheld payments and
    # savings are accounted for
    # --------------------------------------------------
    balance_after_withheld: float
    # --------------------------------------------------
    # the budget after withheld payments and savings are
    # accounted for
    # --------------------------------------------------
    budget_after_withheld: float

    # --------------------------------------------------
    # the amount ALLOCATED to spend during this period
    # note that this amount can be greater than how much
    # SHOULD be spent
    # --------------------------------------------------
    allocated_spending_budget: float

    # --------------------------------------------------
    # the balance after all withheld payments and savings
    # AND spending budget are accounted for
    # --------------------------------------------------
    balance_after_withheld_and_spending: float
    # --------------------------------------------------
    # the budget after all withheld payments and savings
    # AND spending budget are accounted for
    # --------------------------------------------------
    budget_after_withheld_and_spending: float
    # --------------------------------------------------
    # the spending budget, accounting for all that has
    # already been spent this period
    # --------------------------------------------------
    budget_after_withheld_and_spent: float

    # --------------------------------------------------
    # did we softly overspend?
    # e.g. go over the allocated spending budget
    # --------------------------------------------------
    overspent_soft: bool
    # -------------------------------------------------
    # did we hard overspend?
    # e.g. breach the checking floor, need to be bailed out
    # in order to afford bills and required payments
    # --------------------------------------------------
    overspent_hard: bool

    # --------------------------------------------------
    # the minimum amount that should be in checking account
    # by the end of the period
    # --------------------------------------------------
    checking_floor: float
    # --------------------------------------------------
    # money able to be spent freely, after all budgets
    # accounted for. This is 0 if the allocated spending budget
    # equals exactly the checking balance @ start minus the checking floor.
    # --------------------------------------------------
    free_to_spend: float

    @classmethod
    def from_rows(cls, rows: List[List[str]]) -> "BudgetStats":
        return cls(
            income_account=rows[0][0].strip(),
            total_budget=parse_money(rows[3][0]),
            income_at_period_start=parse_money(rows[5][0]),
            checking_amount_period_start=parse_money(rows[7][0]),
            total_withheld_required_payments=parse_money(rows[9][0]),
            total_withheld_savings=parse_money(rows[11][0]),
            balance_after_withheld=parse_money(rows[13][0]),
            budget_after_withheld=parse_money(rows[15][0]),
            allocated_spending_budget=parse_money(rows[17][0]),
            balance_after_withheld_and_spending=parse_money(rows[19][0]),
            budget_after_withheld_and_spending=parse_money(rows[21][0]),
            budget_after_withheld_and_spent=parse_money(rows[23][0]),
            overspent_soft=rows[25][0].strip().upper() == "TRUE",
            overspent_hard=rows[27][0].strip().upper() == "TRUE",
            checking_floor=parse_money(rows[29][0]),
            free_to_spend=parse_money(rows[31][0]),
        )


@dataclass
class Summary:
    meta: BudgetMetadata

    start_date: date
    end_date: date
    period_size: float

    spent_categorized: Bss
    account_balances: List[AccountBalance]
    transfer_overviews: List[TransferOverview]

    spendable_overviews: List[SpendableOverview]
    payments_overviews: List[PaymentsOverview]
    savings_overviews: List[SavingsOverview]

    budgets: List[Budget]
    budget_stats: BudgetStats
    time: str
    horoscope: Optional[str] = None
    horoscope_url: Optional[str] = None
    custom_alert: Optional[str] = None

    def to_email_html(self, template_path: str = "budget-email.html") -> str:
        env = Environment(loader=FileSystemLoader("."))
        template = env.get_template(template_path)
        today = date.today() + timedelta(
            0
        )  # dont know if this is actually required, but works?
        days_left = max((self.end_date - today).days, 0) + 1
        remaining_sum = sum([s.spendable_amount for s in self.spendable_overviews])
        # --------------------------------------------------
        # calculate overflow percentage based on how much of
        # the overflow pool has been consumed by overspending
        # --------------------------------------------------
        bills_this_period = self.spent_categorized.bills()
        savings_this_period = self.spent_categorized.savings()
        spending_this_period = self.spent_categorized.spending()
        bills_overspent = max(
            0, bills_this_period - self.budget_stats.total_withheld_required_payments
        )
        savings_overspent = max(
            0, savings_this_period - self.budget_stats.total_withheld_savings
        )
        spending_overspent = max(
            0, spending_this_period - self.budget_stats.allocated_spending_budget
        )
        overflow_consumed = bills_overspent + savings_overspent + spending_overspent
        overflow_available = self.budget_stats.budget_after_withheld_and_spending
        overflow_pct = (
            (overflow_consumed / overflow_available * 100)
            if overflow_available > 0
            else 0
        )
        overflow_pct = max(overflow_pct, 0)

        # --------------------------------------------------
        # sort spendable overviews by left_today descending
        # --------------------------------------------------
        spendable_overviews_sorted = sorted(
            self.spendable_overviews, key=lambda x: x.left_today, reverse=True
        )

        # --------------------------------------------------
        # render
        # --------------------------------------------------
        return template.render(
            today=today,
            days_left=days_left,
            meta=self.meta,
            start_date=self.start_date,
            end_date=self.end_date,
            spending_this_period=spending_this_period,
            bills_this_period=bills_this_period,
            savings_this_period=savings_this_period,
            period_size=self.period_size,
            remaining_sum=remaining_sum,
            account_balances=self.account_balances,
            spendable_overviews=spendable_overviews_sorted,
            payments_overviews=self.payments_overviews,
            savings_overviews=self.savings_overviews,
            budgets=self.budgets,
            budget_stats=self.budget_stats,
            transfer_overviews=self.transfer_overviews,
            time=self.time,
            horoscope=self.horoscope,
            horoscope_url=self.horoscope_url,
            overflow_pct=overflow_pct,
            overflow_consumed=overflow_consumed,
            overflow_available=overflow_available,
            custom_alert=self.custom_alert,
        )

    def to_email_subject(self) -> str:
        if self.start_date == date.today():
            return f"NEW BUDGET UNLOCKED FOR {self.meta.name}!!! - Budget Reminder"
        else:
            return f"{self.meta.name} Budget Reminder"
