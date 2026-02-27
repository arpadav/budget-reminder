# Budget Reminder Email

This takes a Google Spreadsheet of a unique format, and populates all numbers into a tightly-formatted HTML page which can be sent as a reminder every morning to an individual about their spending habits.

This is not meant to be used by others, since the spreadsheet format is extremely unique considering circumstances. It is only made public for my own record-keeping and project-showcasing.

## Usage

```bash
# for debugging
python3 send_budget_reminder.py --for <user> --at 7:00AM --using accounts/accounts.toml --birthday MM-DD --debug --port 9000

# for dry-run
python3 send_budget_reminder.py --for <user> --at 7:00AM --using accounts/accounts.toml --birthday MM-DD --dry-run > output.html

# for actual sending
python3 send_budget_reminder.py --for <user> --at 7:00AM --using accounts/accounts.toml --birthday MM-DD
```

## Accounts

See `accounts/README.md` on how to configure Gmail and Google Drive API keys
