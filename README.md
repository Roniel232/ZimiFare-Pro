# ZimiFare — Smart fare management

**ZimiFare** is a styled, role-based Python/Streamlit application developed from the 32-page *ZimiFare Integrated Pseudocode* specification. It supports passenger fare cards, driver fare requests, single-settlement ride payments and administrator controls.

![ZimiFare logo](assets/logo.png)

## What is included

| Portal | Available functionality |
| --- | --- |
| Public | Passenger / driver registration, login, safe password storage |
| Passenger | Dashboard, simulated top-up, pay outstanding ride by fare card, ride history, account/profile |
| Driver | Dashboard, create fare request, confirm cash settlement, earnings based on paid rides, history, profile |
| Administrator | Dashboard, list/edit users, disable/block non-admin accounts, inspect/search transactions, run fraud review, profile |

**Business logic:** no duplicate fare payment; only the assigned passenger may make fare-card payments; only the assigned driver can confirm cash; both participants must be active; paid fare-card rides reduce the balance, cash rides do not; earnings include paid rides only; transaction review flags amounts **strictly above JMD 50,000.00**. All top-ups are simulated; **no real payment processor or bank account is connected**.

## Quick start on Windows

You already installed Python and Streamlit. For a fresh copy of this project:

1. Extract `ZimiFare_App.zip` into a folder, e.g. `Documents\ZimiFare_App`.
2. **Fastest option:** double-click **`START_ZIMIFARE.bat`** inside the extracted folder. It checks Streamlit, prompts for initial admin setup if needed, and starts the website. Keep the black command window open.

   If Windows prevents the batch file from running, follow the manual steps below instead:

   Open that folder in File Explorer. Click the **address bar**, type `cmd`, and press Enter. This opens Command Prompt directly in the correct folder (avoids Windows/OneDrive Desktop path errors).

3. If Streamlit is not installed for this Python environment, run:

   ```bat
   python -m pip install -r requirements.txt
   ```

4. Create the trusted initial administrator **once** (do not use public registration for administrator accounts):

   ```bat
   python create_admin.py
   ```

   Enter your administrator name, email, phone, and a strong password. Password characters may not appear while typing; this is normal.

5. Start the application:

   ```bat
   python -m streamlit run app.py
   ```

6. Open **http://localhost:8501** in your browser. Sign in as the administrator, then sign out and register a passenger and a driver for an integrated demonstration.

If `python` is not recognised, try `py` instead (e.g. `py -m pip install -r requirements.txt` and `py -m streamlit run app.py`). Leave the command window running while using the application. Stop with `Ctrl+C`.

### Basic folder layout

```text
ZimiFare_App/
├── app.py                     Streamlit screens and UI styling
├── zimifare/
│   ├── __init__.py
│   └── core.py                Validation, roles, balances, rides, transactions
├── assets/
│   ├── icon.png / icon.svg    App icon
│   └── logo.png / logo.svg    Original ZimiFare brand/logo
├── create_admin.py            Trusted one-time admin setup CLI
├── START_ZIMIFARE.bat         Windows one-click starter
├── tests/test_core.py         Automated business-rule tests
├── .streamlit/config.toml     Application colour theme
├── .streamlit/secrets.toml.example
└── requirements.txt
```

**Data is stored in `data/zimifare.db` (SQLite).** It is created automatically on first run. Local records survive sign-out and application restarts. This data file is intentionally excluded from the ZIP/GitHub project.

## Demonstrate the integrated workflow

Read `DEMO_WALKTHROUGH.md` for a guided role-by-role example corresponding to the pseudocode's 1,000.00 top-up / 250.00 payment trace. `PSEUDOCODE_MAPPING.md` maps every original procedure to its implemented Python code and screen, which is especially useful for the assignment write-up.

## Deploy for classmates and lecturer (Streamlit Community Cloud)

1. Create a **GitHub** repository, e.g. `zimifare-university-app`, and upload the *contents* of this project directory, including `app.py`, `requirements.txt`, `assets/`, `zimifare/` and `.streamlit/config.toml`. Do **not** upload `.venv`, `data/`, or `.streamlit/secrets.toml`.
2. Go to <https://share.streamlit.io/> and select **Create app** from your GitHub repository; main file path is `app.py`.
3. **Before opening your first hosted deployment**, set a private secret on Streamlit Community Cloud, using your app's **Settings > Secrets**:

   ```toml
   ZIMIFARE_ADMIN_SETUP_KEY = "YOUR-LONG-UNPREDICTABLE-SETUP-PHRASE"
   ```

   Use a new, strong setup phrase, not this example. This is **not** your administrator password. Never commit it to GitHub. Let the app restart so the secret loads.
4. Open the deployed app. When the one-time administrator setup form appears, enter the same setup phrase and create an admin account. Then open passenger and driver registration.
5. Share the deployment's `.streamlit.app` address with your class. Each visitor can sign in from their own device. Admin actions require the administrator account.

### Critical hosting limitation

The included SQLite database is **persistent on your own computer**, but Streamlit Community Cloud does **not guarantee persistence of files written on its server**. Hosted demo records may disappear after restart, app sleep, redeploy or environment replacement. Visitors can use the same active app while it is running, with SQLite write locking for payment safety, but this is **an academic demonstration, not durable online storage**.

For a live service or a classroom project requiring records to survive cloud restarts, migrate to a managed database such as PostgreSQL, configure backups, add proper operational monitoring, session security and authentication hardening, and test that deployment before assessment. The current project does **not** implement PostgreSQL. The project uses no real money and is not production banking/payment software.

## Implementation decisions and differences from pseudocode

- **Original design:** one process, one session, in-memory arrays; logs and records persist only while its process runs. **This application:** SQLite so multiple Streamlit sessions can read and share the same records and local data survives a restart. `BEGIN IMMEDIATE` encloses sensitive writes and a unique payment-per-ride index adds a second double-payment safeguard.
- **Original unspecified currency:** this demonstration selects **Jamaican dollars (JMD)**. Amounts are represented by **integer cents** throughout; decimal input is parsed with `Decimal`.
- **Trusted administrator:** initial administrator is created locally via `create_admin.py`, or by a secret-protected browser setup on a hosted deployment. Public self-registration cannot create administrators.
- **Security:** stored passwords are salted PBKDF2-HMAC-SHA256 hashes; login verifies hashes; backend methods enforce role and owner checks. The app asks for the existing password when changing a password as an extra precaution.
- **User caps:** 1,000 users, 100 rides, 10,000 transactions, matching source constants. Deleting/resetting is intentionally **not** exposed in the UI.
- **Ride transaction ID:** the pseudocode uses `0` for an unpaid ride; the SQLite implementation uses `NULL` to indicate no linked transaction, preserving the same practical meaning.
- **Review threshold:** `5,000,000` cents equals **JMD 50,000.00**; *strictly greater* amounts are flagged. Neither transaction monitoring nor fraud detection creates payments or blocks users automatically.
- **Passwords and sessions:** Streamlit's browser session holds only the active account ID, never the password or hash. Local persistent records are shared through SQLite, not browser session state.
- **Scope:** top-ups simulate confirmed funds, no actual financial transfers, notifications, maps, GPS, live dispatch, fare calculations, booking marketplace, password-reset emails or third-party integrations are included because the pseudocode did not define them.

## Run automated tests

From the project folder:

```bat
python -m unittest discover -s tests -v
```

The tests exercise integrated fare payment, non-duplication, concurrency, insufficient balance, cash, fraud flags, registration, password protection, access controls, date/money validation and profile updates. They use isolated temporary databases and do not modify your actual ZimiFare data.

## Troubleshooting

- **`No module named streamlit`**: run `python -m pip install -r requirements.txt` using the same Python interpreter as you use to launch the app.
- **`Can't open file 'app.py'`**: navigate to the extracted project folder before running the command. File Explorer address bar → `cmd` is the easiest method.
- **App shows initial admin setup**: run `python create_admin.py` locally, or configure `ZIMIFARE_ADMIN_SETUP_KEY` in Streamlit secrets when deployed.
- **Port 8501 already in use**: stop an earlier Streamlit session with `Ctrl+C`, or run `python -m streamlit run app.py --server.port 8502`.
- **School Wi-Fi / Windows Firewall**: `localhost:8501` runs on the same laptop and typically requires no inbound public network permission. To share the app across devices, deploy on Streamlit Community Cloud and share its HTTPS link.
- **Data missing after hosted restart**: expected limitation of local SQLite on ephemeral cloud storage (see above).

---
**ZimiFare · Move smart. Pay easy.** Academic application based on the supplied *ZimiFare Integrated Pseudocode* document. 

## Additional administrator accounts
After the first administrator has been created, sign in as an active admin and open **Manage users → Create administrator**. Enter the second admin’s details, give them their own strong password, confirm the privilege grant, and re-enter **your** admin password to authorise it. The new admin can immediately sign in separately. This is an extension of the original pseudocode, which only specified the first trusted admin. Public users still cannot register as admins. Keep each administrator’s login separate and secure. Existing records stay in `data/zimifare.db`.

## ZimiFare Pro upgrade: structured references, reports and motion

This is an additive upgrade to the existing application, **including multiple
administrators**. It does not change the existing SQLite schema or primary keys.
You can safely apply it over the older ZimiFare or the multi-admin version after
backing up your existing project folder. See **UPGRADE_INSTRUCTIONS.txt** for
copy/paste Windows commands and a complete checklist.

### Human-readable IDs

Public-facing references replace unclear integer-only labels. Examples:

| Record | Example public reference | Internal storage remains |
| --- | --- | --- |
| Administrator | `ZF-ADM-000001` | user_id `1` |
| Passenger | `ZF-PSG-000002` | user_id `2` |
| Driver | `ZF-DRV-000003` | user_id `3` |
| Ride | `ZF-RID-000001` | ride_id `1` |
| Transaction | `ZF-TXN-000001` | transaction_id `1` |

The `PSG`, `DRV`, and `ADM` codes indicate each account's role, not a separate
per-role numeric counter. **This preserves all original relationships**, even
on a live database with existing payment records. Transaction searches also
support legacy `TX-00001` and numeric references for backward compatibility.

### Administrator analytics

The administrator menu now includes **Analytics & reports**, powered by actual
stored transactions with no fictional sample entries. It features:

- Interactive period, type, method, review-status and text filters.
- Transaction value per day and transaction count per day.
- Card-versus-cash fare value, and top driver fare totals.
- Separate totals for **simulated top-ups** and **paid fare amounts** — top-ups
  are not counted as earnings/revenue.
- CSV export of filtered transactions, plus a detailed admin-only ride ledger.
- Date grouping and labels in **UTC**; JMD amounts use cents internally.

The **administrator Overview** also shows charts, and the dashboard retains
all existing user-management and fraud-detection functionality.

### Interface motion and accessibility

The existing ZimiFare logo and navy/teal/gold brand remain. Decorative animated
SVG taxi illustrations, hover transitions, responsive layout and analytics
visuals add polish without external image downloads. CSS honours the system's
**Reduce motion** preference, and animations do not perform financial actions.

### Additional dependencies

Charts use **Altair** and **Pandas**, both commonly installed as dependencies
of Streamlit but listed explicitly in `requirements.txt` for clarity.
Install with `python -m pip install -r requirements.txt` in your chosen virtual
environment, or use the updated Windows starter. To check all Python logic:
`python -m unittest discover -s tests -v`.

### Implementation note

The provided pseudocode defined permanent integer identifiers and explicitly
specified in-memory shared state. Formatted reference IDs, SQLite persistence,
an added read-only administrator ride ledger, multiple-administrator creation,
reporting and dashboard animations are **implementation extensions**; the
original payment, account authorization and fraud-threshold rules are preserved.
