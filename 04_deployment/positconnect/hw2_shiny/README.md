# HW2 Shiny — Posit Connect / Posit Connect Cloud

This folder is the **deployment bundle** for the Homework 2 Python Shiny app. It contains a small **`app.py`** entrypoint that imports `app` from `HOMEWORK_2/HW2_app.py` after putting `HOMEWORK_1/` and `HOMEWORK_2/` on `sys.path`, with the same directory layout as your Git repo (so path logic in `HW2_app.py` stays correct).

## Contents

| File | Purpose |
|------|--------|
| `app.py` | Connect entrypoint: `app:app` |
| `requirements.txt` | Python dependencies (Shiny, RAG, HW1 helpers) |
| `manifestme.sh` | `rsync` copies `HOMEWORK_1/` and `HOMEWORK_2/` here, then writes `manifest.json` |
| `testme.sh` | Same sync + run Shiny locally |
| `.gitignore` | Ignores the copied `HOMEWORK_1/` / `HOMEWORK_2/` folders (see below) |

## 1. Generate `manifest.json`

**Always run this on your machine before publishing** so the bundle includes the latest homework code and a complete `manifest.json`.

From the **repository root** (recommended):

```bash
chmod +x 04_deployment/positconnect/hw2_shiny/manifestme.sh
./04_deployment/positconnect/hw2_shiny/manifestme.sh
```

Or:

```bash
cd 04_deployment/positconnect/hw2_shiny && ./manifestme.sh
```

Install [`rsconnect-python`](https://docs.posit.co/rsconnect-python/) first if needed: `pip install rsconnect-python`.

**Why rsync?** Posit’s manifest step needs real files under `HOMEWORK_1/` and `HOMEWORK_2/` next to `app.py`. Those directories are **gitignored here** to avoid duplicating the repo; they appear only after you run `manifestme.sh` or `testme.sh`.

## 2. Publish to Posit Connect / Posit Connect Cloud

- **CLI (typical):** from `04_deployment/positconnect/hw2_shiny` **after** `manifestme.sh` (so `HOMEWORK_1/` and `HOMEWORK_2/` exist next to `app.py`):

  ```bash
  rsconnect deploy shiny . --server https://YOUR-CONNECT-SERVER --api-key YOUR_API_KEY
  ```

- **Important:** The copied `HOMEWORK_1/` and `HOMEWORK_2/` trees are **not** stored in Git (see `.gitignore`). A fresh clone does **not** contain them until you run `manifestme.sh`. Deploy by pointing `rsconnect deploy` (or the Connect “Upload” / desktop publisher flow) at this folder **after** `manifestme.sh` has run, so the bundle includes those directories. If your school uses a **pure Git** pipeline with no local rsync step, add a CI job that runs `manifestme.sh` before publishing, or remove the `HOMEWORK_*` lines from `.gitignore` and commit the synced copies (larger repo).

## 3. Environment variables (Connect → Content → **Vars**)

Set at least:

| Name | Purpose |
|------|--------|
| `OPENAI_API_KEY` | Agents 2–4 and optional reporting |
| `NYT_API_KEY` | If the app must refresh or build the NYT cache |

Do not commit secrets; add them in the Connect **Vars** UI.

## 4. First run note (RAG)

The app may build the local SQLite + embedding index under `HOMEWORK_2/data/` on first use. That can take several minutes and needs CPU/RAM; if the request times out, pre-build the index locally, commit the `.db` if your course allows, or raise Connect’s process timeout.

## 5. Local test

```bash
chmod +x 04_deployment/positconnect/hw2_shiny/testme.sh
./04_deployment/positconnect/hw2_shiny/testme.sh 8001
```

Then open `http://127.0.0.1:8001`.
