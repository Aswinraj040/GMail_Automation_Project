# 📧 Gmail Automation Project

A Python-based Gmail automation tool that fetches emails from your inbox and processes them based on custom rules defined in a `rules.json` file. It supports actions like marking as read/unread, labeling, and deleting — all handled securely via the Gmail API and OAuth2 authentication.

---

## 🚀 Features

- ✅ Secure Gmail API integration using OAuth2  
- 📥 Automatically fetch emails and store them in a local SQLite database  
- 📜 Define custom email filtering and action rules via `rules.json`  
- 🧪 Includes unit and integration tests  
- 🔐 Uses `.env` and `.gitignore` for secure config management  
- 📂 Organized project structure with virtual environment support  

---

## 🛠️ Setup Instructions

### 📌 Step 1: Create a Google Cloud Project and Enable Gmail API

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click on **"Select Project"** → **"New Project"**.
3. Enter a project name and click **"Create"**.
4. In the left sidebar, navigate to **"APIs & Services" > "Library"**.
5. Search for **Gmail API**, click it, and then click **"Enable"**.

---

### 🔐 Step 2: Set Up OAuth 2.0 Consent Screen and Credentials

1. Go to **"APIs & Services" > "OAuth consent screen"**.
2. Choose **External** and click **Create**.
3. Fill in the **App name**, **support email**, and **developer contact**.
4. Skip scopes (or add if required) and complete the form.
5. Go to **"Credentials" > "Create Credentials" > "OAuth client ID"**:
   - Choose **Desktop App** as the application type.
   - Click **Create**, then **Download** the `credentials.json`.

> ⚠️ **Important:** Place `credentials.json` in the project root. Never commit it to GitHub.

---

### 🧱 Step 3: Clone the GitHub Repository

```bash
git clone https://github.com/Aswinraj040/GMail_Automation_Project
cd GMail_Automation_Project
```

#### 💡 Step 3A: Set Up a Python Virtual Environment (Recommended)

Create the virtual environment:

```bash
python -m venv venv
```

Activate the environment:

- **macOS/Linux**:

  ```bash
  source venv/bin/activate
  ```

- **Windows (CMD)**:

  ```bash
  venv\Scripts\activate
  ```

- **Windows (PowerShell)**:

  ```powershell
  .\venv\Scripts\Activate.ps1
  ```

Install project dependencies:

```bash
pip install -r requirements.txt
```

---

### 📂 Project Structure

```
<project-root>/
├── src/
│   ├── fetch_emails.py
│   └── process_emails.py
│
├── tests/
│   ├── unit_tests.py
│   └── integration_tests.py
│
├── .env
├── .gitignore
├── credentials.json          # 🔒 OAuth credentials
├── token.json                # 🔐 Auto-generated on first login
├── EmailDatabase.db          # 🗃️ Auto-generated local database
├── requirements.txt
├── rules.json                # 📜 Email processing rules
```

> 📌 The database `EmailDatabase.db` is created automatically when `fetch_emails.py` is run.

---

### 📥 Step 4: Fetch Emails Using Gmail API

To fetch the latest emails (default: 50):

```bash
python src/fetch_emails.py
```

You can configure the number of emails to fetch by setting the value in your `.env` file:

```ini
MAX_RESULTS=100
```

This script will:

- Authenticate via Gmail API and create `token.json`
- Fetch emails from the inbox
- Store data in `EmailDatabase.db`

---

### ✏️ Step 5: Configure Rules

Customize `rules.json` to define your filtering and automation logic.

**Example:**

```json
{
  "all_rules": [
    {
      "predicate": "all",
      "rules": [
        { "field": "sender", "predicate": "contains", "value": "@domain.com" },
        { "field": "subject", "predicate": "contains", "value": "Invoice" },
        { "field": "date", "predicate": "less_than", "value": "7_days" }
      ],
      "actions": ["mark_as_read", "move_to:Invoices"]
    }
  ]
}
```

✅ **Supported Options:**

- **Fields**: `sender`, `recipient`, `subject`, `message`, `date`  
- **Predicates**: `contains`, `does_not_contain`, `equals`, `does_not_equal`  
- **Overall Predicate**: `all`, `any`  
- **Actions**:
  - `mark_as_read`
  - `mark_as_unread`
  - `move_to:starred`
  - `move_to:important`
  - `move_to:trash`
  - `move_to:<LabelName>`

**📅 Date format for rules:**  
Use strings like `"2_days"`, `"1_months"`, `"5_days"` etc.

---

### ⚙️ Step 6: Process Emails Based on Rules

Once rules are defined, apply them to your inbox:

```bash
python src/process_emails.py
```

This will:

- Load emails from the SQLite DB
- Match each against defined rules
- Execute actions using Gmail API

---

### 🧪 Step 7: Run Tests

#### Run Unit Tests

```bash
python -m unittest discover -s tests/unit
```

#### Run Integration Tests

```bash
python -m unittest discover -s tests/integration
```

✅ Ensure all tests pass before deploying or using in production.

---

## 🛡️ Security Notes

- Never upload `credentials.json`, `token.json`, or `EmailDatabase.db` to GitHub.
- Use `.gitignore` to safely exclude sensitive and environment-specific files.
