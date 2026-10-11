# ETMS System Diagnostic Toolkit & Emergency Repair Manual
**Everest Textile Manufacturing System (ETMS)**  
*Engineered for National Hackathon Finals — High-Reliability Operations*

---

## 1. System Health & Sanity Checklist

Run this one-liner in PowerShell from the project root to inspect the entire stack:
```powershell
# 1. Health Probe
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health"

# 2. Strict RBAC Auth Profiles Probe
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/profile" -Headers @{ "X-User-Role" = "owner" }
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/profile" -Headers @{ "X-User-Role" = "floor_supervisor" }
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/profile" -Headers @{ "X-User-Role" = "customer" }

# 3. Machine Telemetry Probe
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/machines" | Select-Object -First 3
```

---

## 2. Automated Invariant Test Suite

Verify that all double-dispatch guards, ASTM quality score rules, and financial ledger calculations are strictly passing:
```powershell
.\.venv\Scripts\python.exe -m pytest backend/test_invariants.py -v
```
**Expected Outcome:** `6 passed in ~5s` (100% green).

---

## 3. Fast Service Relaunch & Port Collision Fix

If either server stops responding or you get `EADDRINUSE / Port 8000 / Port 3000 busy`:

### A. Kill Existing Processes
```powershell
# Find and terminate port 8000 (Python FastAPI)
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess -ErrorAction SilentlyContinue | Stop-Process -Force

# Find and terminate port 3000 (Next.js)
Get-Process -Id (Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue).OwningProcess -ErrorAction SilentlyContinue | Stop-Process -Force
```

### B. Clean Relaunch (Two Separate Terminals)
- **Terminal 1 (Backend):**
  ```powershell
  cd "c:\Users\chinm\OneDrive\Desktop\Textile Manufacturing System"
  .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8000
  ```
- **Terminal 2 (Frontend):**
  ```powershell
  cd "c:\Users\chinm\OneDrive\Desktop\Textile Manufacturing System\frontend"
  npm run dev -- -p 3000
  ```

---

## 4. Database Reset / Re-Seed

If test transactions have altered the demo data and you want a pristine factory floor for the judges:
```powershell
cd "c:\Users\chinm\OneDrive\Desktop\Textile Manufacturing System"
Remove-Item "everest_manufacturing.db" -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -c "import asyncio; from backend.app.database import engine, Base, AsyncSessionLocal; from backend.app.seed_data import seed_initial_mill_data; asyncio.run((lambda: [engine.begin(), seed_initial_mill_data])())"
# Alternatively: Simply restart the backend server; its lifespan event auto-creates and seeds any missing database tables!
```

---

## 5. Adding More Custom Media (Images, GIFs, Videos)

To seamlessly add logos, GIFs, or factory loop videos:
1. Copy your media files into `frontend/public/`:
   - `frontend/public/factory-loop.mp4` (Ambient machinery video)
   - `frontend/public/inspection-scan.gif` (Optical yarn scanner animation)
   - `frontend/public/brand-logo.png` (Company emblem)
2. Use them directly in any JSX element with standard Next.js path resolution:
   ```jsx
   <img src="/brand-logo.png" alt="Everest Logo" />
   <video autoPlay loop muted playsInline src="/factory-loop.mp4" />
   ```
3. Run `npm run build` inside `frontend/` to ensure zero compilation or bundle errors.
