# Dashboard Implementation Checklist

## Phase 1: Supabase Setup
- [ ] Create free Supabase account at https://supabase.com
- [ ] Create new project
- [ ] Copy Project URL
- [ ] Copy Anon Public Key
- [ ] Go to SQL Editor
- [ ] Run all SQL from: `MF Analysis/SUPABASE_SCHEMA.sql`
- [ ] Verify `fund_holdings` table created
- [ ] Verify views created

**Estimated time: 15 minutes**

---

## Phase 2: Python Configuration
- [ ] Install Python packages:
  ```powershell
  cd "d:\MF Project\MF Analysis"
  pip install supabase python-dotenv openpyxl pandas
  ```
- [ ] Create `.env` file in `MF Analysis/` folder with:
  ```
  SUPABASE_URL=your-project-id.supabase.co
  SUPABASE_KEY=your-anon-key
  ```
- [ ] Verify `.env` file is created

**Estimated time: 5 minutes**

---

## Phase 3: Data Upload Test
- [ ] Run upload script:
  ```powershell
  python "02_scripts/upload_to_supabase.py"
  ```
- [ ] Check for success message: `✓ All data uploaded successfully!`
- [ ] Log into Supabase dashboard
- [ ] Go to `fund_holdings` table
- [ ] Verify data appears (~5000+ rows)
- [ ] Check a few rows: security_name, fund_name, quantity values look correct

**Estimated time: 5 minutes**

---

## Phase 4: Next.js Setup
- [ ] Install Recharts library:
  ```powershell
  cd "d:\MF Project\wealthineers"
  npm install recharts
  ```
- [ ] Update `.env.local`:
  ```
  NEXT_PUBLIC_SUPABASE_URL=your-project-id.supabase.co
  NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
  ```
- [ ] Verify file exists:
  `wealthineers/src/app/dashboard/page.jsx`
- [ ] Save all changes

**Estimated time: 5 minutes**

---

## Phase 5: Dashboard Testing
- [ ] Start dev server:
  ```powershell
  npm run dev
  ```
- [ ] Open browser: http://localhost:3000/dashboard
- [ ] Wait for dashboard to load (slicers should populate)
- [ ] Test Slicer 1 (Security Name):
  - [ ] Click dropdown
  - [ ] Select any security (e.g., "ONGC")
  - [ ] Verify chart updates
  - [ ] Check line chart shows data
- [ ] Test Slicer 2 (Fund Name):
  - [ ] Select any fund
  - [ ] Verify chart filters further
  - [ ] Chart should show fewer data points
- [ ] Test Slicer 3 (AMC):
  - [ ] Select any AMC (HDFC or ICICI)
  - [ ] Verify all 3 filters work together
- [ ] Test "-- All --" option:
  - [ ] Click any slicer
  - [ ] Select "-- All --"
  - [ ] Verify filter is removed
- [ ] Test summary stats below chart:
  - [ ] Check "Total Records"
  - [ ] Check "Avg Quantity"
  - [ ] Change filters - stats should update

**Estimated time: 10 minutes**

---

## Phase 6: Automation (Optional)
- [ ] Edit `run_full_mf_refresh.bat`
- [ ] Add these lines before the final `pause`:
  ```batch
  echo.
  echo ============================================================
  echo STEP 6: Upload to Supabase
  echo ============================================================
  
  %PYTHON_EXE% "%~dp002_scripts\upload_to_supabase.py"
  
  IF %ERRORLEVEL% NEQ 0 (
      echo.
      echo ERROR: Supabase upload failed.
      pause
      exit /b %ERRORLEVEL%
  )
  ```
- [ ] Test running entire script:
  ```powershell
  .\run_full_mf_refresh.bat
  ```
- [ ] Verify all steps complete including upload
- [ ] Verify new data appears in Supabase

**Estimated time: 10 minutes**

---

## Troubleshooting Checklist

If slicers don't populate:
- [ ] Check browser console (F12) for errors
- [ ] Verify `.env.local` has correct SUPABASE_URL and SUPABASE_ANON_KEY
- [ ] Check Supabase dashboard - is data in `fund_holdings` table?
- [ ] Restart dev server: `Ctrl+C` then `npm run dev`

If chart shows "No data available":
- [ ] Try selecting "-- All --" for all slicers
- [ ] Check Supabase table has data
- [ ] Check browser console for errors
- [ ] Run upload script again

If upload script fails:
- [ ] Verify `.env` has SUPABASE_URL and SUPABASE_KEY
- [ ] Check matrix file exists: `05_matrix\MASTER\matrix_all_amc_funds_quantity_long.xlsx`
- [ ] Verify Supabase credentials are correct
- [ ] Check internet connection

---

## Success Criteria ✅

Dashboard is working when:
1. ✅ Slicers populate with real data
2. ✅ Selecting filters updates chart instantly
3. ✅ Line chart displays quantity trends
4. ✅ Summary stats update with filters
5. ✅ No console errors
6. ✅ Can filter by: Security → Fund → AMC
7. ✅ Chart animates smoothly when filters change

---

## Total Setup Time Estimate
- Supabase: 15 min
- Python config: 5 min
- Data upload: 5 min
- Next.js setup: 5 min
- Testing: 10 min
- Automation: 10 min
- **Total: ~50 minutes**

---

## Documentation References
- Setup guide: `DASHBOARD_SETUP.md`
- Summary: `DASHBOARD_SUMMARY.md`
- Implementation plan: `plan.md`

---

## Ready to Start? 🚀
Follow phases in order and refer to `DASHBOARD_SETUP.md` for detailed instructions!
