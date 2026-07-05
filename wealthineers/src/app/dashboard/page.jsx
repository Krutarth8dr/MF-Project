/**
 * Interactive Dashboard with Slicers
 * Path: wealthineers/src/app/dashboard/page.jsx
 * 
 * Features:
 * - 3 dynamic slicers (Security, Fund, AMC)
 * - Line chart showing quantity trends
 * - Real-time filtering
 * - Responsive design
 */

'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { createClient } from '@supabase/supabase-js';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

// Initialize Supabase
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
);

// ============================================
// COMPONENT: Slicer (Dropdown Filter)
// ============================================
function Slicer({ label, options, value, onChange, isLoading }) {
  return (
    <div className="flex flex-col gap-2">
      <label className="text-sm font-semibold text-gray-700">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={isLoading}
        className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
      >
        <option value="">-- All {label} --</option>
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    </div>
  );
}

// ============================================
// COMPONENT: Line Chart
// ============================================
function FundChart({ data, isLoading }) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96 bg-gray-50 rounded-lg">
        <p className="text-gray-500">Loading chart...</p>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-96 bg-gray-50 rounded-lg">
        <p className="text-gray-500">No data available for selected filters</p>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={400}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="portfolio_date"
          label={{ value: 'Date', position: 'insideBottom', offset: -5 }}
        />
        <YAxis
          label={{ value: 'Quantity', angle: -90, position: 'insideLeft' }}
        />
        <Tooltip
          formatter={(value) => value.toLocaleString()}
          labelFormatter={(label) => `Date: ${label}`}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="quantity"
          stroke="#3b82f6"
          dot={false}
          strokeWidth={2}
          name="Holdings Quantity"
          isAnimationActive={true}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ============================================
// MAIN COMPONENT: Dashboard
// ============================================
export default function DashboardPage() {
  const router = useRouter();
  // State: Filters
  const [selectedSecurity, setSelectedSecurity] = useState('');
  const [selectedFund, setSelectedFund] = useState('');
  const [selectedAMC, setSelectedAMC] = useState('');

  // State: Data
  const [chartData, setChartData] = useState([]);
  const [securities, setSecurities] = useState([]);
  const [funds, setFunds] = useState([]);
  const [amcs, setAMCs] = useState([]);

  // State: UI
  const [isLoading, setIsLoading] = useState(false);
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => {
  const checkSubscription = async () => {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    console.log('Session:', session);

    if (!session) {
      router.push('/login');
      return;
    }

    const { data: userData, error } = await supabase
      .from('users')
      .select('subscription_status')
      .eq('id', session.user.id)
      .single();

    console.log('User Data:', userData);
    console.log('Error:', error);

    if (userData?.subscription_status === 'active') {
      setIsSubscribed(true);
    }
  };

  checkSubscription();
}, [router]);

  // ============================================
  // EFFECT: Load filter options
  // ============================================
  useEffect(() => {
    const loadFilterOptions = async () => {
      try {
        setIsLoading(true);

        // Fetch unique securities
        const { data: secData } = await supabase
          .from('fund_holdings')
          .select('security_name')
          

        if (secData) {
          const uniqueSec = [...new Set(secData.map((d) => d.security_name))].sort();
          setSecurities(uniqueSec);
        }

        // Fetch unique funds
        const { data: fundData } = await supabase
          .from('fund_holdings')
          .select('fund_name')
          

        if (fundData) {
          const uniqueFund = [...new Set(fundData.map((d) => d.fund_name))].sort();
          setFunds(uniqueFund);
        }

        // Fetch unique AMCs
        const { data: amcData } = await supabase
          .from('fund_holdings')
          .select('amc')
          

        if (amcData) {
          const uniqueAMC = [...new Set(amcData.map((d) => d.amc))].sort();
          setAMCs(uniqueAMC);
        }

        setIsLoading(false);
      } catch (err) {
        console.error('Error loading filters:', err);
        setError('Failed to load filters');
        setIsLoading(false);
      }
    };

    loadFilterOptions();
  }, []);

  // ============================================
  // EFFECT: Load chart data based on filters
  // ============================================
  useEffect(() => {
    const loadChartData = async () => {
      try {
        setIsLoading(true);
        setError(null);

        // Build query
        let query = supabase.from('fund_holdings').select('*');

        // Apply filters
        if (selectedSecurity) {
          query = query.eq('security_name', selectedSecurity);
        }
        if (selectedFund) {
          query = query.eq('fund_name', selectedFund);
        }
        if (selectedAMC) {
          query = query.eq('amc', selectedAMC);
        }

        // Execute query
        const { data, error: supabaseError } = await query.order('portfolio_date', {
          ascending: true,
        });

        if (supabaseError) {
          throw supabaseError;
        }

        // Format data for chart
        const formattedData = (data || []).map((d) => ({
          ...d,
          portfolio_date: new Date(d.portfolio_date).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
          }),
        }));

        setChartData(formattedData);
        setIsLoading(false);
      } catch (err) {
        console.error('Error loading chart data:', err);
        setError('Failed to load data');
        setChartData([]);
        setIsLoading(false);
      }
    };

    loadChartData();
  }, [selectedSecurity, selectedFund, selectedAMC]);

// ============================================
// LOCKED DASHBOARD FOR FREE USERS
// ============================================

  if (!isSubscribed) {
  return (
    <div className="min-h-screen flex flex-col justify-center items-center bg-gray-50">

      <div className="text-8xl mb-6">
        🔒
      </div>

      <h1 className="text-4xl font-bold mb-4">
        Dashboard Locked
      </h1>

      <p className="text-gray-600 text-lg text-center max-w-xl mb-8">
        Subscribe to Wealthineers Premium to unlock
        fund holdings analytics, filters and premium reports.
      </p>

      <button
        className="px-8 py-4 bg-blue-600 text-white rounded-lg text-lg hover:bg-blue-700"
        onClick={() => {
          window.location.href = '/#pricing';
        }}
      >
        Subscribe Now
      </button>

    </div>
  );
}

  // ============================================
  // RENDER
  // ============================================
  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Fund Holdings Dashboard
          </h1>
          <p className="text-gray-600">
            Analyze mutual fund portfolio holdings with interactive filters
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
          </div>
        )}

        {/* Slicers */}
        <div className="mb-8 grid grid-cols-1 md:grid-cols-3 gap-6 bg-white p-6 rounded-lg shadow">
          <Slicer
            label="Security Name"
            options={securities}
            value={selectedSecurity}
            onChange={setSelectedSecurity}
            isLoading={isLoading}
          />
          <Slicer
            label="Fund Name"
            options={funds}
            value={selectedFund}
            onChange={setSelectedFund}
            isLoading={isLoading}
          />
          <Slicer
            label="AMC"
            options={amcs}
            value={selectedAMC}
            onChange={setSelectedAMC}
            isLoading={isLoading}
          />
        </div>

        {/* Chart */}
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Holdings Quantity Over Time
          </h2>
          <FundChart data={chartData} isLoading={isLoading} />

          {/* Data Summary */}
          {chartData.length > 0 && (
            <div className="mt-6 pt-6 border-t border-gray-200">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <p className="text-gray-500">Total Records</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {chartData.length}
                  </p>
                </div>
                <div>
                  <p className="text-gray-500">Avg Quantity</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {(
                      chartData.reduce((sum, d) => sum + (d.quantity || 0), 0) /
                      chartData.length
                    ).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </p>
                </div>
                <div>
                  <p className="text-gray-500">Max Quantity</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {Math.max(...chartData.map((d) => d.quantity || 0)).toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-gray-500">Min Quantity</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {Math.min(...chartData.map((d) => d.quantity || 0)).toLocaleString()}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
