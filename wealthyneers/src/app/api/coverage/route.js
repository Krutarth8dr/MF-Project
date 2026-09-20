import { NextResponse } from 'next/server';
import fallbackCoverage from '@/lib/coverageData.json';

export const maxDuration = 60;
export const revalidate = 21600; // 6 hours edge / ISR revalidation

// In-memory server-side cache for high performance
let memoryCache = {
  data: fallbackCoverage,
  lastFetched: Date.now(),
};

const CACHE_TTL_MS = 6 * 60 * 60 * 1000; // 6 hours

export async function GET(request) {
  const now = Date.now();
  let forceRefresh = false;

  if (request?.url) {
    try {
      const { searchParams } = new URL(request.url);
      forceRefresh = searchParams.get('refresh') === 'true';
    } catch {
      // Ignore URL parsing errors
    }
  }

  // If cache is fresh and refresh is not requested, return immediately (0ms)
  if (!forceRefresh && memoryCache.data && (now - memoryCache.lastFetched < CACHE_TTL_MS)) {
    return NextResponse.json(memoryCache.data, {
      headers: {
        'Cache-Control': 'public, s-maxage=21600, stale-while-revalidate=86400',
        'CDN-Cache-Control': 'public, s-maxage=21600',
      },
    });
  }

  try {
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

    if (!supabaseUrl || !supabaseKey) {
      return NextResponse.json(memoryCache.data || fallbackCoverage, {
        headers: {
          'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=300',
        },
      });
    }

    // 1. Fetch initial AMCs from get_report2_filter_options
    const res = await fetch(`${supabaseUrl}/rest/v1/rpc/get_report2_filter_options`, {
      method: 'POST',
      headers: {
        apikey: supabaseKey,
        Authorization: `Bearer ${supabaseKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
      next: { revalidate: 21600 },
    });

    if (!res.ok) {
      // Return cached/fallback data if Supabase is busy
      return NextResponse.json(memoryCache.data || fallbackCoverage, {
        headers: {
          'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=300',
        },
      });
    }

    const initData = await res.json();
    const amcs = Array.isArray(initData.amcs) ? initData.amcs.sort((a, b) => a.localeCompare(b)) : [];

    if (amcs.length === 0) {
      return NextResponse.json(memoryCache.data || fallbackCoverage, {
        headers: {
          'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=300',
        },
      });
    }

    // 2. Fetch fund lists for each AMC in parallel
    const mappingPromises = amcs.map(async (amc) => {
      try {
        const amcRes = await fetch(`${supabaseUrl}/rest/v1/rpc/get_report2_filter_options`, {
          method: 'POST',
          headers: {
            apikey: supabaseKey,
            Authorization: `Bearer ${supabaseKey}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ p_amcs: [amc] }),
        });
        if (amcRes.ok) {
          const amcData = await amcRes.json();
          const funds = Array.isArray(amcData.funds) ? amcData.funds.sort((a, b) => a.localeCompare(b)) : [];
          return [amc, funds];
        }
      } catch {
        // Fallback for this individual AMC
      }
      return [
        amc,
        (memoryCache.data?.amcFundsMap && memoryCache.data.amcFundsMap[amc]) ||
          (fallbackCoverage.amcFundsMap && fallbackCoverage.amcFundsMap[amc]) ||
          [],
      ];
    });

    const entries = await Promise.all(mappingPromises);
    const amcFundsMap = Object.fromEntries(entries);

    const allUniqueFundsSet = new Set();
    Object.values(amcFundsMap).forEach((list) => {
      if (Array.isArray(list)) {
        list.forEach((f) => allUniqueFundsSet.add(f));
      }
    });
    if (allUniqueFundsSet.size === 0 && Array.isArray(initData.funds)) {
      initData.funds.forEach((f) => allUniqueFundsSet.add(f));
    }
    const fundsList = Array.from(allUniqueFundsSet).sort((a, b) => a.localeCompare(b));

    const responsePayload = {
      amcCount: Object.keys(amcFundsMap).length,
      fundCount: fundsList.length,
      amcs: Object.keys(amcFundsMap).sort((a, b) => a.localeCompare(b)),
      funds: fundsList,
      amcFundsMap,
    };

    // Update memory cache
    memoryCache = {
      data: responsePayload,
      lastFetched: now,
    };

    return NextResponse.json(responsePayload, {
      headers: {
        'Cache-Control': 'public, s-maxage=21600, stale-while-revalidate=86400',
        'CDN-Cache-Control': 'public, s-maxage=21600',
      },
    });
  } catch {
    // If any error occurs, return fallback coverage without failing the user experience
    return NextResponse.json(memoryCache.data || fallbackCoverage, {
      headers: {
        'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=300',
      },
    });
  }
}
