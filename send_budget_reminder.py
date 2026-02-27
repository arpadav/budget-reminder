# --------------------------------------------------
# external
# --------------------------------------------------
import sys
import toml
import logging
import argparse
from pathlib import Path
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional, List
from google.oauth2 import service_account
from googleapiclient.discovery import build  # type: ignore

# --------------------------------------------------
# local
# --------------------------------------------------
import primitives
import email_client
from helpers import LogTimer
from debug_server import debug_mode
from fetch_horoscope import get_horoscope_for_birthday

# --------------------------------------------------
# configure logging
# --------------------------------------------------
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
DEFAULT_LOG_FILE = "history.log"
logging.basicConfig(
    level=DEFAULT_LOG_LEVEL,
    format=DEFAULT_LOG_FORMAT,
    handlers=[
        logging.FileHandler(DEFAULT_LOG_FILE, mode="a"),  # always append
    ],
)


@dataclass
class GoogleSpreadsheet:
    spreadsheet_id: str
    spreadsheet_url: str
    service: Any
    sheet_credentials: service_account.Credentials
    sheet: Optional[Any]

    def query(self, range: str) -> Any:
        if isinstance(self.sheet, type(None)):
            with LogTimer("initializing Google Sheets API client"):
                self.sheet = self.service.spreadsheets()
        with LogTimer(f"querying range '{range}'"):
            result = self.sheet.values().get(spreadsheetId=self.spreadsheet_id, range=range).execute()  # type: ignore
        return result.get("values", [])


@dataclass
class BudgetRecipientAccount:
    name: str
    email: str
    full_name: str
    sheet: GoogleSpreadsheet

    def __init__(self, name: str, email: str, full_name: str, sheet: GoogleSpreadsheet):
        # --------------------------------------------------
        # return
        # --------------------------------------------------
        self.name = name
        self.email = email
        self.full_name = full_name
        self.sheet = sheet

    def query(self, range: str) -> Any:
        return self.sheet.query(range)


@dataclass
class GoogleAccount:
    email: str
    app_password: str
    recipient: BudgetRecipientAccount

    def __init__(self, cfg: dict[str, Any], name: str):
        # --------------------------------------------------
        # check to see if email
        # --------------------------------------------------
        FROM_EMAIL_KEY = "from-gmail"
        if FROM_EMAIL_KEY in cfg:
            from_email = cfg[FROM_EMAIL_KEY]
        else:
            raise ValueError(
                "No email provided in configuration file: {}".format(FROM_EMAIL_KEY)
            )

        # --------------------------------------------------
        # check to see if app-main-pwd exists
        # --------------------------------------------------
        APP_PWD_PATH_KEY = "from-gmail-app-pwd-file"
        if APP_PWD_PATH_KEY in cfg:
            app_pwd_path = Path(cfg[APP_PWD_PATH_KEY])
            if not app_pwd_path.is_file():
                raise FileNotFoundError(
                    f"App main password file not found: {app_pwd_path}"
                )
            else:
                app_password = app_pwd_path.read_text()
        else:
            raise ValueError(
                "No app main password provided in configuration file: {}".format(
                    APP_PWD_PATH_KEY
                )
            )

        # --------------------------------------------------
        # loop through accounts
        # --------------------------------------------------
        NAME_KEY = "name"
        EMAIL_KEY = "email"
        SPREADSHEET_ID_KEY = "spreadsheet-id"
        SERVICE_ACCOUNT_FILE_KEY = "service-account-file"
        recipient_account = None
        for account_name in cfg["accounts"]:
            if name == account_name:
                full_name = cfg["accounts"][account_name][NAME_KEY]
                recipient_email = cfg["accounts"][account_name][EMAIL_KEY]
                spreadsheet_id = cfg["accounts"][account_name][SPREADSHEET_ID_KEY]
                service_account_path = cfg["accounts"][account_name][
                    SERVICE_ACCOUNT_FILE_KEY
                ]
                sheet_credentials = service_account.Credentials.from_service_account_file(  # type: ignore
                    service_account_path,
                    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
                )
                service = build("sheets", "v4", credentials=sheet_credentials)  # type: ignore
                recipient_account = BudgetRecipientAccount(
                    name=name,
                    email=recipient_email,
                    full_name=full_name,
                    sheet=GoogleSpreadsheet(
                        spreadsheet_id=spreadsheet_id,
                        spreadsheet_url=f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
                        service=service,
                        sheet_credentials=sheet_credentials,
                        sheet=None,
                    ),
                )
                break
        if recipient_account is None:
            raise ValueError("No account found with name: {}".format(name))

        # --------------------------------------------------
        # return
        # --------------------------------------------------
        self.email = from_email
        self.app_password = app_password
        self.recipient = recipient_account

    def query(self, range: str) -> List[Any]:
        return self.recipient.query(range)


def main():
    parser = argparse.ArgumentParser(description="Send budget reminder")
    parser.add_argument(
        "--for",
        dest="account_name",
        type=str,
        required=True,
        help="Name of the account to send reminder for",
    )
    parser.add_argument(
        "--at",
        dest="time",
        type=str,
        required=True,
        help="Time which the reminder is sent out (e.g. 8:00 AM)",
    )
    parser.add_argument(
        "--using", dest="cfg", type=str, required=True, help="Configuration file to use"
    )
    parser.add_argument(
        "--birthday",
        dest="birthday",
        type=str,
        required=False,
        help="Birthday in YYYY-MM-DD or MM-DD format for horoscope (optional)",
    )
    parser.add_argument(
        "--template",
        dest="template",
        type=str,
        default="budget-email.html",
        help="Template file to use (default: budget-email.html)",
    )
    parser.add_argument(
        "--log-file",
        dest="log_file",
        type=str,
        default="history.log",
        help="Log file to write to (default: history.log)",
    )
    # --------------------------------------------------
    # mutually exclusive group for dry-run and debug
    # --------------------------------------------------
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not send email, print out email to stdout.",
    )
    mode_group.add_argument(
        "--debug",
        action="store_true",
        help="Debug mode: watch template for changes, render to output.html, and serve via HTTP. Press Ctrl+C to quit.",
    )
    parser.add_argument(
        "--port",
        dest="port",
        type=int,
        default=8000,
        help="Port for HTTP server in debug mode (default: 8000)",
    )
    args = parser.parse_args()

    # --------------------------------------------------
    # update logger if log file is different from default
    # --------------------------------------------------
    if args.log_file != DEFAULT_LOG_FILE:
        # --------------------------------------------------
        # remove existing handlers to close the file and avoid duplicate logs
        # --------------------------------------------------
        logger = logging.getLogger()
        for h in logger.handlers[:]:
            logger.removeHandler(h)
            h.close()
        # --------------------------------------------------
        # add new file handler
        # --------------------------------------------------
        new_handler = logging.FileHandler(args.log_file, mode="a")
        new_handler.setFormatter(logging.Formatter(DEFAULT_LOG_FORMAT))
        logger.addHandler(new_handler)
        logger.setLevel(DEFAULT_LOG_LEVEL)

    # --------------------------------------------------
    # get config
    # --------------------------------------------------
    cfg_path = Path(args.cfg)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {cfg_path}")
    else:
        cfg = toml.loads(cfg_path.read_text())

    try:
        # --------------------------------------------------
        # connect to google account
        # --------------------------------------------------
        account = GoogleAccount(cfg=cfg, name=args.account_name)

        # --------------------------------------------------
        # get categories
        # --------------------------------------------------
        categories_sheet = account.query("Categories!C:Z")
        keys = categories_sheet[0]
        cat2subcat: dict[str, List[str]] = {key: [] for key in keys}
        for row in categories_sheet[1:]:
            for key, value in zip(keys, row):
                if value:  # skip empty strings
                    cat2subcat[key].append(value)

        # --------------------------------------------------
        # get period size, start, end date
        # --------------------------------------------------
        period_size = float(account.query("Budgeting!$AH$2")[0][0])
        start_date = datetime.strptime(
            account.query("Budgeting!$AG$2")[0][0], "%m/%d/%Y"
        ).date()
        end_date = datetime.strptime(
            account.query("Budgeting!$AG$4")[0][0], "%m/%d/%Y"
        ).date()
        # spent = parse_money(account.query("Overview!$A$6")[0][0])

        # --------------------------------------------------
        # get account balances
        # --------------------------------------------------
        account_balances = primitives.AccountBalance.from_rows(
            account.query("Accounts!A2:D")
        )

        # --------------------------------------------------
        # get spendable overview
        # --------------------------------------------------
        spendable_overviews = primitives.SpendableOverview.from_range(
            account.query("Overview!B2:E")
        )

        # --------------------------------------------------
        # get transfer overview
        # --------------------------------------------------
        transfer_overviews = primitives.TransferOverview.from_range(
            account.query("Overview!G2:I")
        )

        # --------------------------------------------------
        # get payments / savings overviews
        # --------------------------------------------------
        overview = account.query("Budgeting!Y2:AB")
        payments_overviews = primitives.PaymentsOverview.from_range(overview)
        savings_overviews = primitives.SavingsOverview.from_range(overview)

        # --------------------------------------------------
        # get budgets
        # --------------------------------------------------
        budgets: List[primitives.Budget] = []
        budgets += primitives.Budget.from_manual_budget_range(
            period_size=period_size,
            rows=account.query("Budgeting!H2:K"),
        )
        budgets += primitives.Budget.from_recurring_budget_range(
            cat2subcat=cat2subcat,
            rows=account.query("Budgeting!O2:V"),
        )
        budgets.sort(
            key=lambda b: b.next_approx_payment or date.min
        )  # sort by next approx payment date, None goes to the beginning

        # --------------------------------------------------
        # budget stats
        # --------------------------------------------------
        budget_stats = primitives.BudgetStats.from_rows(
            rows=account.query("Accounts!I:I")
        )
        spent_categorized = primitives.Bss.from_rows(
            rows=account.query("Budget Calc!A5:A10")
        )

        # --------------------------------------------------
        # get horoscope if birthday provided
        # --------------------------------------------------
        horoscope = None
        horoscope_url = None
        if args.birthday:
            with LogTimer("fetching horoscope"):
                horoscope_result = get_horoscope_for_birthday(args.birthday)
            if isinstance(horoscope_result, tuple):
                horoscope, horoscope_url = horoscope_result

        # --------------------------------------------------
        # get summary and render html
        # --------------------------------------------------
        budget_summary = primitives.Summary(
            meta=primitives.BudgetMetadata(
                name=account.recipient.full_name,
                spreadsheet_url=account.recipient.sheet.spreadsheet_url,
            ),
            time=str(args.time),
            start_date=start_date,
            end_date=end_date,
            period_size=period_size,
            spent_categorized=spent_categorized,
            account_balances=account_balances,
            spendable_overviews=spendable_overviews,
            payments_overviews=payments_overviews,
            savings_overviews=savings_overviews,
            budgets=budgets,
            budget_stats=budget_stats,
            transfer_overviews=transfer_overviews,
            horoscope=horoscope,
            horoscope_url=horoscope_url,
        )

        if args.debug:
            debug_mode(budget_summary, template_name=args.template, port=args.port)
        elif args.dry_run:
            print(budget_summary.to_email_html(args.template))
        else:
            with LogTimer("render and send email"):
                email_client.EmailClient(
                    account.email, account.app_password
                ).send_email(
                    subject=budget_summary.to_email_subject(),
                    body_html=budget_summary.to_email_html(args.template),
                    to=[account.recipient.email],
                    cc=[],
                    bcc=[account.email],
                )

    except Exception as e:
        logging.exception("Error occurred during budget reminder execution")
        print(f"Error occurred during budget reminder execution: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
