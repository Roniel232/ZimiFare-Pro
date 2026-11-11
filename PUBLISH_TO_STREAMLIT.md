# ZimiFare Pro — Publish online for group testing

This is a clean, source-only copy of the ZimiFare Pro application. It contains no existing database, passwords, virtual environments or real user records. **Use it for cloud deployment, but keep your existing local installation as your backup.**

## Step 1: GitHub

1. Create a free account at https://github.com/ or sign in.
2. Select **New repository**, call it `zimifare-pro` (or similar). For the easiest class demo use **Public**, but see privacy notes below. Click **Create repository**.
3. Open this extracted `ZimiFare_Cloud_Ready` folder on your PC. Select all its items, including the `.streamlit` folder. Upload the **contents** to GitHub with **Add file → Upload files**. Do not upload the ZIP as a single file; GitHub must see `app.py` in the repository root.
4. Select **Commit changes**. Confirm that your repository root contains `app.py`, `requirements.txt`, `assets/`, `zimifare/` and `.streamlit/config.toml`.

Never upload a `.venv/` directory, a `data/` database, `.streamlit/secrets.toml`, credentials, personal records or a private admin password.

## Step 2: Deploy

1. Visit https://share.streamlit.io/ and sign in/connect GitHub.
2. Click **Create app** and choose the option for an existing GitHub repository.
3. Select your GitHub repository, branch `main`, and main file path `app.py`.
4. **Before clicking Deploy**, open **Advanced settings → Secrets** and set a randomly chosen strong setup key. This exact snippet is an EXAMPLE ONLY; replace the value with a long secret of your own:

   ```toml
   ZIMIFARE_ADMIN_SETUP_KEY = "REPLACE-WITH-YOUR-OWN-STRONG-RANDOM-SECRET"
   ```

   This setup key is different from the admin password. Never put it in a GitHub file or share it with classmates.
5. Save advanced settings and click **Deploy**.
6. When the first-run admin setup page loads, enter your secret setup key and create your cloud administrator. This account is **separate from the administrator account on your own laptop**, because cloud and local databases are separate.
7. Log in as the cloud administrator. Create additional administrator accounts from **Manage users → Create administrator** if your project needs them.
8. Use the `.streamlit.app` address to share with group members. For a public app, anyone with the URL can visit it. For private access, configure **App settings → Sharing → Only specific people can view this app**, then invite the required email addresses.

If you forget to set the secret at deployment: **App settings → Secrets**, add it, save, restart if requested, then reload the site.

## Suggested test sequence

1. Create one driver and one passenger account using test details. Never use real passwords you use elsewhere.
2. Sign in as passenger, simulate topping up the fare card.
3. Sign in as driver, create a ride for the passenger's formatted ID.
4. Sign in as passenger to pay that unpaid ride by fare card.
5. Attempt to pay again to verify duplicate-payment protection.
6. Sign in as admin to inspect **Analytics & reports**, ride and transaction tables, and fraud review.
7. Repeat in two different browsers to check shared access during the same running session.

## Critical limitation — cloud SQLite storage

The app uses `data/zimifare.db` (SQLite) at runtime. Streamlit Community Cloud does **not guarantee local file persistence**. Users can see and edit shared test records while the app runs, but those records — including cloud admin and user accounts — **can be lost after restarts, sleeping or redeployment**. The cloud is not linked to your Windows database. Do not rely on the hosted version as permanent evidence of activity. Export CSV reports for your submission and keep screenshots of tests.

For durable multi-user storage, ZimiFare must be adapted to a persistent managed database (e.g. PostgreSQL) or a host that provides persistent volumes. Merely creating a PostgreSQL account or adding credentials will **not** make this SQLite version persistent; the application backend must be changed and tested first.

## Help links

- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
- https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app
- https://docs.streamlit.io/develop/concepts/connections/connecting-to-data
