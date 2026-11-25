# BullishBrief AI — Mobile starter

This project contains:
- FastAPI online backend using Yahoo Finance data
- Mobile-first web interface
- Capacitor Android wrapper configuration

## Important limitations
This is a starter project, not a finished signed APK. It has not been deployed or tested against your hosting account or Android device. Yahoo Finance coverage, freshness, news, analyst data and NSE symbols can vary. Scores are transparent heuristic research metrics, not investment advice. The overall score is shown only when all five categories have data. NSE public holidays are not yet included in the basic market-status clock.

## 1. Deploy online (Render example)
1. Create a GitHub repository and upload the complete contents of this folder.
2. Create a Render account and connect the repository.
3. Render should detect `render.yaml`; deploy the `bullishbrief-ai` web service.
4. Wait for deployment and open `https://YOUR-SERVICE.onrender.com/api/health`.
5. If health returns `{"ok":true,...}`, the backend is online.
6. Replace `YOUR-DEPLOYED-SERVICE.onrender.com` in `mobile/capacitor.config.json` with your real Render hostname.

Free hosting may sleep when idle and take time to wake. For reliable always-on usage, choose a paid hosting plan. Keep API access protected before public launch; CORS is permissive in this starter.

## 2. Build Android APK (requires a computer)
Install:
- Node.js LTS
- Android Studio and Android SDK
- Java JDK supported by your Android Studio version

In a terminal:
```bash
cd mobile
npm install
npx cap add android
npx cap sync android
npx cap open android
```
In Android Studio:
- Wait for Gradle sync.
- Choose Build > Build Bundle(s) / APK(s) > Build APK(s).
- For personal testing, install the debug APK on your Android phone.
- For distribution, create a signed release APK/AAB and keep the signing key private.

## 3. Test backend locally
From the project root:
```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```
Open `http://127.0.0.1:8000`.

## Before real-world use
- Add authentication and rate limiting.
- Restrict CORS to the deployed app origin.
- Add a proper NSE holiday calendar.
- Validate financial metrics against company filings.
- Add data freshness labels and automated tests.
- Do not treat the heuristic verdict as a trading signal.
