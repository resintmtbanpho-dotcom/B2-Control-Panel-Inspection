# B2 Control Panel Inspection — Web Preview

Responsive Streamlit prototype for RSB and PTB. The RSB 67-panel register is **illustrative data**, not verified panel records. PTB is initially empty.

## Run locally

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.port 8502
```

## Publish on Streamlit Community Cloud

1. Create a **private GitHub repository** and upload `app.py`, `requirements.txt`, `.streamlit/config.toml`, and `.gitignore` (do not upload real secrets or employee photos).
2. At https://share.streamlit.io/ choose **Create app** > **Deploy a public app from GitHub** (or the corresponding deploy flow available in your account).
3. Choose the repo, branch `main`, main file path `app.py`; deploy.
4. In app settings > Secrets add `APP_BASE_URL = "https://YOUR-APP.streamlit.app"` using the actual assigned address, then reboot the app.
5. Test the URL `https://YOUR-APP.streamlit.app/?panel=CP-RSB-001` and test the QR in Panel Profile. QR is a demo entry point, not proof of physical inspection.

## Important limitations

- **Not production-ready**: data is in `st.session_state` only, disappears on refresh/restart, and is not shared between users. There is no user authentication, role authorization, or Supabase connection.
- **Do not upload real employee photographs, contact numbers, inspection results, or confidential facility layouts to a public demo**. Restrict access before real deployment.
- The 35 checklist entries are placeholders, not the final approved standard text. Use an approved checklist and safe-work procedures before real use.
- `APP_BASE_URL` enables a working QR deep link for **demo registered panels**. Public Streamlit URLs can be accessible to anyone; QR links do not grant authorization.
- No need for pandas. This package is suitable for cloud deployment but depends on Streamlit's service availability.


Checklist: เพิ่มข้อความรายการตรวจภาษาไทย 35 ข้อ แบ่ง 7 หมวด (ต้นแบบ โปรดทวนคำกับเอกสารมาตรฐานก่อนใช้งานจริง)
