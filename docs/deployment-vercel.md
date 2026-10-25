# Deploy LineSight on Vercel

Owner: **Kumar Waibhav Akshat** · **kwa.waibhav@gmail.com**

This update adapts the existing FastAPI dashboard and frozen Isolation Forest to Vercel's Python runtime. It does not retrain or replace the model. The live deployment remains to be verified on your Vercel account.

## 1. Apply this ZIP on Windows

Download `LineSight_Vercel_Update.zip` to your Downloads folder. Open **Windows PowerShell** and run:

```powershell
Set-Location -LiteralPath "C:\Users\kumar\Desktop\LineSight_Complete_Project\LineSight"
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\LineSight_Vercel_Update.zip" -DestinationPath . -Force
Test-Path .\app.py
Test-Path .\vercel.json
Test-Path .\artifacts\linesight.joblib
```

All three checks must return `True`. The ZIP contains deployment changes, not a second copy of the model. It must be extracted into the existing project folder.

## 2. Commit and push

Use the same PowerShell window, in the same folder:

```powershell
git config --local user.name "Kumar Waibhav Akshat"
git config --local user.email "kwa.waibhav@gmail.com"
gh auth switch --hostname github.com --user kumarwaibhav
gh auth setup-git --hostname github.com
gh api user --jq ".login"
git add app.py vercel.json .python-version .vercelignore requirements.txt pyproject.toml scripts/vercel_build.py scripts/verify_vercel.py src/linesight/api.py web/app.js web/index.html tests/test_vercel.py docs/deployment-vercel.md "reports/vercel-*"
git --no-pager diff --cached --stat
git commit -m "Add Vercel deployment for LineSight"
git log -1 --format="%an <%ae>"
git remote -v
```

The account must be `kumarwaibhav`, the author must be `Kumar Waibhav Akshat <kwa.waibhav@gmail.com>`, and the remote must be your LineSight repository. If `main` is your project branch and `origin` already exists:

```powershell
git push origin main
```

If the GitHub repository has not been created yet, finish committing the project files and create it once:

```powershell
git branch -M main
gh repo create kumarwaibhav/linesight --public --source=. --remote=origin --push
```

## 3. Import the repository on Vercel

1. Open https://vercel.com/new and sign in with GitHub.
2. Use your personal **Hobby** account for this noncommercial portfolio demo.
3. Import your LineSight repository.
4. Set **Framework Preset** to **FastAPI**.
5. Set **Root Directory** to the repository root, where `app.py` and `vercel.json` are located.
6. Leave the Install Command and Output Directory overrides disabled.
7. The included `vercel.json` supplies the Build Command: `python scripts/vercel_build.py`. If the dashboard shows an older override such as `npm run build`, remove that override.
8. No port, start command, API base URL or Railway-specific environment variables are needed. The entrypoint derives the correct root and writable temporary database location.
9. Click **Deploy**.

The Python dependencies are installed before the build command runs. The build downloads and verifies the pinned MVTec bottle archive, keeps the 83 held-out test images for replay, and removes training images, masks and the downloaded archive from the deployment. No training runs in a request or during this deployment build.

## 4. Verify the live deployment

Open the actual Vercel domain shown on your dashboard:

| Path | Expected result |
|---|---|
| `/` | LineSight dashboard |
| `/api/health` | `status: ready`, `model_loaded: true` |
| `/api/model` | Original model version, 4 MiB upload cap, temporary history mode |
| `/api/samples` | `count: 83` when sample inclusion is enabled |
| `/docs` | API reference |

Inspect a normal and a defective replay sample, then upload a PNG/JPEG/WebP no larger than **4 MiB** and **4 megapixels**. Use the deployed HTTPS URL and browser camera permission to try sampled camera inspection. There is no continuously running camera process on the server.

PowerShell health check:

```powershell
$lineSightUrl = (Read-Host "Paste the Vercel URL shown on your dashboard").Trim().TrimEnd('/')
Invoke-RestMethod -Uri "$lineSightUrl/api/health"
```

## Hosting behavior and limits

- Vercel currently supports FastAPI on its Python runtime. Hobby is a free plan with usage quotas for personal, noncommercial projects; it does not promise unlimited compute.
- The standard Python function bundle limit is 500 MB uncompressed. Large Functions are a separate public beta; this configuration does not rely on beta availability.
- Vercel has a 4.5 MB request/response payload limit. LineSight restricts file contents to 4 MiB, leaving room for multipart overhead. The dashboard reads the actual cap from the API.
- SQLite is stored in `/tmp/linesight/events.sqlite3`. It is temporary and instance-local. Records can reset when an instance is recycled and are not shared between instances. A refresh can reach a different instance. The dashboard labels this behavior.
- Use an external database if you require permanent, shared inspection history. This update does not configure one or claim durable logging.
- First requests to a new instance may be slower because Python dependencies and the model must load.
- Keep the existing MVTec attribution and CC BY-NC-SA 4.0 terms. Original project code remains under its existing license.

## Troubleshooting

| Symptom | Check |
|---|---|
| Vercel detects a Node application | Select the FastAPI framework preset; remove old Node build/output overrides. |
| Model not loaded | Verify `artifacts/linesight.joblib` is committed. Check function logs and the `model_error` field in `/api/health`. |
| Dataset download fails | Check build logs and retry when the pinned mirror is reachable. For an upload-only deployment, set `LINESIGHT_INCLUDE_SAMPLES=0` and redeploy; the replay list will then be empty. |
| Upload returns 413 | Use an image no larger than 4 MiB and 4 MP. |
| Bundle exceeds 500 MB | Check that local environments, archives, raw training data and generated build outputs are excluded. Report the build's actual bundle-size error; do not change the model silently. |
| History disappears | This is expected for temporary per-instance storage. Permanent shared history requires an external database. |

## Official references

- https://vercel.com/docs/frameworks/backend/fastapi
- https://vercel.com/docs/functions/runtimes/python
- https://vercel.com/docs/functions/limitations
- https://vercel.com/docs/functions/runtimes
- https://vercel.com/docs/plans/hobby

Configuration and documentation checked on **25 October 2026**. Local verification is recorded in `reports/vercel-validation.json` in the prepared project. A real Vercel build and live-domain checks are still required before calling the cloud deployment verified.
