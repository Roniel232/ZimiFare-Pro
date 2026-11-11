# ZimiFare — class demonstration script

Use this guided scenario to show that the three modules share the same ride and transaction records.

## Prepare accounts

1. In Command Prompt, run `python create_admin.py` **once** to create your administrator. Start the web app with `python -m streamlit run app.py`.
2. From the **Create account** tab, register a passenger and note the assigned user ID (for example, ID 2).
3. Register a driver using a different email address (for example, ID 3). Each account has its own login and role-specific workspace.

## Demonstrate one successful fare-card payment

1. **Passenger login:** Open **Top up fare card** and enter `1000.00`. Accept the simulation notice and click confirm. Result: balance **JMD 1,000.00**, with a **TOP_UP** transaction.
2. **Driver login:** Open **Receive a fare → Create fare request**, choose the active passenger, enter pickup and destination, set ride date and `250.00` as the agreed fare, then create the ride. Result: an **UNPAID** ride, with an assigned ride ID.
3. **Passenger login:** Open **Pay a fare**, select the ride, and authorise the fare-card payment. Result: ride status becomes **PAID**, a **FARE_PAYMENT** transaction is recorded, and the fare-card balance becomes **JMD 750.00**.
4. **Driver login:** Open **My earnings**. Result: paid-ride count includes the journey and gross earnings include **JMD 250.00**.
5. **Administrator login:** Open **Transactions**. Result: the same top-up and payment records appear, including their IDs, amounts, methods, timestamps and passenger details.
6. **Duplicate payment test:** The paid ride is no longer displayed in the passenger's unpaid-ride selector or the driver's cash selector. The backend also rejects direct attempts to settle the same ride again.

## Demonstrate cash without card deduction

1. While logged in as a driver, create another ride with a different fare.
2. Open **Receive a fare → Receive cash**, select that ride, tick the confirmation that cash was actually received, and settle it.
3. Show that the passenger's fare-card balance is **unchanged** and that the ride has **CASH** as its payment method.
4. Show that the driver earnings and administrator transaction list both reflect the cash payment.

## Demonstrate administrator controls

1. From **Manage users**, view the user directory and edit a sample account's name or phone number.
2. Restrict a **test account** (not your real demonstration passenger) using **DISABLED** or **BLOCKED**. Its login should fail, while previous ride/payment history remains preserved.
3. From a test passenger account, make a simulated top-up of **JMD 50,000.00** and a second simulated top-up of **JMD 50,000.01**. Only the second transaction should receive a review flag.
4. Return to **Fraud review** as the admin and run detection. Point out that a review flag **does not automatically block any user** and does not prove fraud.

## Discussion points for your lecturer

- Money is handled as integer cents to avoid floating-point rounding errors.
- Secure password hashing is used instead of plaintext passwords.
- The same `settle_ride` service processes both cash and fare-card payments, checking the role, ride ownership, active accounts, status, balance and transaction capacity.
- SQLite transactions (`BEGIN IMMEDIATE`) and a database unique index prevent duplicate payments, including overlapping submissions.
- The application uses JMD as an explicit design choice because the pseudocode did not specify a currency.
- SQLite is suitable for a shared local/classroom demonstration, but Streamlit Community Cloud does **not guarantee persistent local files**; a managed external database is the correct next step for durable hosted deployment.

## Pro upgrade demonstration (new)

1. Show the **formatted references** on the passenger and driver dashboards.
   For example, a database user ID of 2 is displayed as `ZF-PSG-000002`.
   A ride number 1 appears as `ZF-RID-000001`, without changing the internal key.
2. Log in as administrator and open **Overview**. The daily charts are populated
   from the actual completed top-ups and fare payments, not sample values.
3. Open **Analytics & reports** and filter by **Fare payments**; confirm that
   simulated top-ups no longer contribute to the paid-fare total.
4. Try **Last 7 days**, **Cash**, and **Flagged only** filters. Open tooltips on
   the chart bars and pie segments.
5. Search for a transaction reference such as `ZF-TXN-000001`, view the matching
   transaction in the ledger, then export filtered transactions to CSV.
6. Expand the **administrator ride records** ledger and verify that each paid
   ride links to exactly one formatted transaction reference.
7. Under **Manage users → Create administrator**, demonstrate that only an
   authorised existing admin can grant access to an additional admin, with
   their own password confirmation. Use a test account, not your personal login.
8. Point out the subtle animated SVG car in page banners. Turn on the operating
   system's reduced-motion setting to show that movement is disabled.
