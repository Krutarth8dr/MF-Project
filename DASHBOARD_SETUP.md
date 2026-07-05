# Wealthineers Dashboard Setup Guide

## Overview
This guide walks you through setting up the interactive dashboard with slicers for viewing mutual fund holdings.

---

## Step 1: Supabase Setup

### 1.1 Create Supabase Account
- Go to https://supabase.com
- Sign up for free account
- Create a new project (region: closest to you)

### 1.2 Get Your Credentials
In Supabase Dashboard:
- Go to **Settings → API**
- Copy:
  - `Project URL` → Store as `SUPABASE_URL`
  - `anon public` key → Store as `SUPABASE_KEY`

### 1.3 Create Database Schema
- Go to **SQL Editor** in Supabase
- Run all SQL from: `MF Analysis/SUPABASE_SCHEMA.sql`
- This creates:
  - `fund_holdings` table
  - Indexes for fast queries
  - Helper views

---

## Step 2: Python Data Upload

### 2.1 Install Dependencies
```powershell
cd "d:\MF Project\MF Analysis"
pip install supabase python-dotenv openpyxl pandas
```

### 2.2 Set Environment Variables
Create `.env` file in `d:\MF Project\MF Analysis`:
```
SUPABASE_URL=your-project-id.supabase.co
SUPABASE_KEY=your-anon-key
```

OR set PowerShell environment variables:
```powershell
$env:SUPABASE_URL = "your-project-id.supabase.co"
$env:SUPABASE_KEY = "your-anon-key"
```

### 2.3 Run Upload Script
After running your matrix generation scripts:
```powershell
cd "d:\MF Project\MF Analysis"
python "02_scripts/upload_to_supabase.py"
```

**Expected Output:**
```
Loading matrix file: ...matrix_all_amc_funds_quantity_long.xlsx
Loaded 5000 rows
Uploading to Supabase...
Batch 1/5 (1000 records)...
✓ Batch 1 uploaded successfully
...
✓ All data uploaded successfully!
```

---

## Step 3: Next.js Frontend Setup

### 3.1 Add Recharts Library
```powershell
cd "d:\MF Project\wealthineers"
npm install recharts
```

### 3.2 Update Environment Variables
Edit `.env.local`:
```
NEXT_PUBLIC_SUPABASE_URL=your-project-id.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

### 3.3 Verify File Structure
Ensure this file exists:
```
wealthineers/
  src/
    app/
      dashboard/
        page.jsx  ← Created by setup
```

### 3.4 Start Development Server
```powershell
npm run dev
```

Navigate to: **http://localhost:3000/dashboard**

---

## Step 4: Test Dashboard

### Test Scenarios:
1. **No filters** → Should show all data
2. **Select Security (e.g., ONGC)** → Chart updates to ONGC data
3. **Select Fund (e.g., HDFC Flexi Cap)** → Further filters data
4. **Select AMC (e.g., HDFC)** → All 3 filters combined
5. **Change filters** → Chart animates smoothly

### Expected Behavior:
- Slicers populate from database ✓
- Chart displays quantity trends over time ✓
- Filters combine (AND logic) ✓
- Line animates when filters change ✓
- Summary stats show below chart ✓

---

## Step 5: Integrate with Matrix Generation

### Option A: Manual Upload
After running `run_full_mf_refresh.bat`:
```powershell
python "02_scripts/upload_to_supabase.py"
```

### Option B: Automatic Upload (Recommended)
Edit `run_full_mf_refresh.bat` to add:
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

---

## Troubleshooting

### Issue: "SUPABASE_URL not configured"
**Solution:** Set environment variables (see Step 2.2)

### Issue: "Table already exists" in SQL
**Solution:** Drop existing table first:
```sql
DROP TABLE IF EXISTS fund_holdings CASCADE;
```
Then re-run schema SQL.

### Issue: Chart shows "No data available"
**Solution:**
- Verify data uploaded: Check Supabase `fund_holdings` table
- Check filters: Try "-- All --" option
- Check browser console for errors

### Issue: Slicers not populating
**Solution:**
- Verify Supabase credentials in `.env.local`
- Check network tab in browser DevTools
- Run upload script again

### Issue: Slow dashboard load
**Solution:**
- Dashboard queries all securities first (slow for large datasets)
- Add pagination in future versions
- For now, filtering should be fast once loaded

---

## File Structure Reference

```
wealthineers/
├── .env.local                 ← Add SUPABASE credentials
├── src/
│   └── app/
│       └── dashboard/
│           └── page.jsx       ← Dashboard component
└── package.json

MF Analysis/
├── .env                       ← Add SUPABASE credentials
├── SUPABASE_SCHEMA.sql        ← Database schema
└── 02_scripts/
    └── upload_to_supabase.py  ← Upload script
```

---

## Next Steps (Future Enhancements)

- [ ] Add more chart types (bar, pie, area)
- [ ] Export filtered data to CSV/Excel
- [ ] Add date range filter
- [ ] Performance dashboard (fund rankings)
- [ ] Comparison view (multiple securities side-by-side)
- [ ] Mobile app version

---

## Support

For issues:
1. Check browser console (F12)
2. Check Supabase logs
3. Verify file paths are correct
4. Ensure all environment variables are set

