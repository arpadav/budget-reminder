# Files needed for `accounts`

1. `accounts.toml`

_Note that this file is not required to be in this directory, since it is used in the CLI for the script._

Format:

```toml
# --------------------------------------------------
# the sender of the email
# --------------------------------------------------
from-gmail = "example@gmail.com"
from-gmail-app-pwd-file = "accounts/pwd.secret" # Gmail App Password

[accounts.user1]
# --------------------------------------------------
# budget account: user1
# --------------------------------------------------
name = "User One"
email = "user.one@gmail.com"
spreadsheet-id = "<spreadsheet-id>"
service-account-file = "accounts/service_account.json"

[accounts.userN]
# --------------------------------------------------
# budget account: userN
# --------------------------------------------------
name = "User En"
email = "user.n@gmail.com"
spreadsheet-id = "<spreadsheet-id>"
service-account-file = "accounts/service_account.json"
```

1. `pwd.secret`

_Note that this file is not required to be in this directory, since it is defined from `accounts.toml`._

It is a file  which contains the 16 character Gmail API "password" to allow for the sender of the email to be used / authenticated.

1. `service_account.json`

_Note that this file is not required to be in this directory, since it is defined from `accounts.toml`._

This is the `service_account.json` file produced by Google API services for private keys, to access Google Drive. See: [https://docs.cloud.google.com/iam/docs/keys-create-delete](https://docs.cloud.google.com/iam/docs/keys-create-delete)
