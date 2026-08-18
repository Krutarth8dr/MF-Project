import Image from 'next/image';
import Link from 'next/link';
import { notFound } from 'next/navigation';

export const REPORT_DESCRIPTIONS = {
  '1': {
    id: 1,
    tag: 'REPORT 1',
    title: 'Mutual Fund Quantity Trend',
    description:
      'The foundation report for reconstructing institutional holding history of any security. Filter by security, AMC, fund, and industry to analyze long-term accumulation, distribution, and turning points.',
    image: '/report-previews/report-1.png',
    imageAlt: 'Mutual Fund Quantity Trend Report UI Screenshot',
    reportHref: '/report1',
    metaTitle: 'Wealthyneers | Report 1: Mutual Fund Quantity Trend',
    metaDesc:
      'Track total institutional holding quantities for any security across all AMCs and funds month-by-month.',
  },
  '2': {
    id: 2,
    tag: 'REPORT 2',
    title: 'Monthly Institutional Activity Monitor',
    description:
      'Compares the latest mutual-fund portfolio snapshot with the previous month to identify securities experiencing the largest institutional accumulation, reduction, new entries, and total exits.',
    image: '/report-previews/report-2.png',
    imageAlt: 'Monthly Institutional Activity Monitor Report UI Screenshot',
    reportHref: '/report2',
    metaTitle: 'Wealthyneers | Report 2: Monthly Institutional Activity Monitor',
    metaDesc:
      'Compare mutual fund portfolio snapshots and identify largest institutional accumulation, reductions, new positions, and exits.',
  },
  '3': {
    id: 3,
    tag: 'REPORT 3',
    title: 'AMC-wise Stock Intelligence',
    description:
      'Isolate any security and track how individual mutual-fund AMCs have scaled, maintained, or liquidated their holdings over time. Compare accumulation timing, conviction levels, and institutional agreement.',
    image: '/report-previews/report-3.png',
    imageAlt: 'AMC-wise Stock Intelligence Report UI Screenshot',
    reportHref: '/report3',
    metaTitle: 'Wealthyneers | Report 3: AMC-wise Stock Intelligence',
    metaDesc:
      'Isolate any security and track how individual AMCs scaled, maintained, or liquidated holdings over time.',
  },
  '4': {
    id: 4,
    tag: 'REPORT 4',
    title: 'AMC Direction Matrix',
    description:
      'A cross-sectional directional matrix compressing individual AMC month-over-month quantity changes into clear signals (🟢 Buying, 🔴 Selling, ⚪ Neutral) across every security in the universe.',
    image: '/report-previews/report-4.png',
    imageAlt: 'AMC Direction Matrix Report UI Screenshot',
    reportHref: '/report4',
    metaTitle: 'Wealthyneers | Report 4: AMC Direction Matrix',
    metaDesc:
      'Cross-sectional directional matrix compressing individual AMC month-over-month quantity changes across every security.',
  },
  '5': {
    id: 5,
    tag: 'REPORT 5',
    title: 'AMC Buying Breadth Ranking',
    description:
      'Ranks securities by institutional consensus—identifying stocks where multiple AMCs are actively accumulating while experiencing minimal to zero selling pressure.',
    image: '/report-previews/report-5.png',
    imageAlt: 'AMC Buying Breadth Ranking Report UI Screenshot',
    reportHref: '/report5',
    metaTitle: 'Wealthyneers | Report 5: AMC Buying Breadth Ranking',
    metaDesc:
      'Ranks securities by institutional consensus and conviction breadth with zero selling pressure filters.',
  },
  '6': {
    id: 6,
    tag: 'REPORT 6',
    title: '7-Month Institutional Holding Direction',
    description:
      'Tracks the monthly quantity-change direction (increase / decrease / flat) of total institutional holdings for each security across all AMCs — over the latest 7 consecutive months.',
    image: '/report-previews/report-6.png',
    imageAlt: '7-Month Institutional Holding Direction Report UI Screenshot',
    reportHref: '/report6',
    metaTitle: 'Wealthyneers | Report 6: 7-Month Institutional Holding Direction',
    metaDesc:
      'Track 7-month consecutive institutional holding directions and identify long-term accumulation trends across the equity universe.',
  },
};

export async function generateStaticParams() {
  return Object.keys(REPORT_DESCRIPTIONS).map((id) => ({
    id,
  }));
}

export async function generateMetadata({ params }) {
  const { id } = await params;
  const report = REPORT_DESCRIPTIONS[id];
  if (!report) return {};

  return {
    title: report.metaTitle,
    description: report.metaDesc,
  };
}

export default async function ReportDescriptionPage({ params }) {
  const { id } = await params;
  const report = REPORT_DESCRIPTIONS[id];

  if (!report) {
    notFound();
  }

  return (
    <div className="report-preview-page" style={{ minHeight: '80vh', padding: '2.5rem 1rem 4rem' }}>
      <div className="container" style={{ maxWidth: '1200px', margin: '0 auto' }}>
        {/* Navigation Breadcrumb */}
        <div style={{ marginBottom: '1.5rem' }}>
          <Link
            href="/dashboard"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              color: 'var(--primary, #0284c7)',
              textDecoration: 'none',
              fontSize: '0.925rem',
              fontWeight: 600,
            }}
          >
            ← Back to Reports
          </Link>
        </div>

        {/* Report Header Card */}
        <div
          style={{
            background: 'var(--card-bg, #0b132b)',
            border: '1px solid var(--border, #1c2541)',
            borderRadius: '1rem',
            padding: '2rem',
            marginBottom: '2rem',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.25)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
            <span
              style={{
                display: 'inline-block',
                padding: '0.3rem 0.85rem',
                borderRadius: '9999px',
                background: 'rgba(56, 189, 248, 0.12)',
                border: '1px solid rgba(56, 189, 248, 0.3)',
                color: '#38bdf8',
                fontSize: '0.8rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              {report.tag}
            </span>
            <span style={{ color: 'var(--muted, #64748b)', fontSize: '0.85rem' }}>
              Report Description &amp; Visual Preview
            </span>
          </div>

          <h1
            style={{
              fontSize: '2rem',
              fontWeight: 700,
              color: 'var(--foreground, #f8fafc)',
              margin: '0 0 1rem 0',
              lineHeight: 1.25,
            }}
          >
            {report.title}
          </h1>

          <p
            style={{
              fontSize: '1.05rem',
              color: 'var(--muted, #cbd5e1)',
              lineHeight: 1.65,
              margin: 0,
              maxWidth: '960px',
            }}
          >
            {report.description}
          </p>
        </div>

        {/* Section Heading */}
        <div style={{ marginBottom: '1rem' }}>
          <h2
            style={{
              fontSize: '1.15rem',
              fontWeight: 600,
              color: 'var(--foreground, #f8fafc)',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              margin: 0,
            }}
          >
            Report Preview
          </h2>
        </div>

        {/* Actual Static Screenshot Preview Display */}
        <div
          style={{
            background: '#0a1124',
            border: '1px solid var(--border, #1c2541)',
            borderRadius: '1rem',
            padding: '0.75rem',
            marginBottom: '1rem',
            boxShadow: '0 8px 30px rgba(0, 0, 0, 0.35)',
            overflow: 'hidden',
          }}
        >
          <div style={{ position: 'relative', width: '100%' }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={report.image}
              alt={report.imageAlt}
              style={{
                width: '100%',
                height: 'auto',
                display: 'block',
                borderRadius: '0.5rem',
              }}
            />
          </div>
        </div>

        {/* Sample / Illustrative Note */}
        <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          <p
            style={{
              fontSize: '0.875rem',
              color: 'var(--muted, #94a3b8)',
              fontStyle: 'italic',
              margin: 0,
              lineHeight: 1.5,
            }}
          >
            Illustrative preview — sample data shown for demonstration purposes.<br />
            The actual report contains live data and may differ from this preview.
          </p>
        </div>

        {/* Bottom Actions */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '1rem',
            paddingTop: '1rem',
            borderTop: '1px solid var(--border, #1c2541)',
          }}
        >
          <Link
            href="/dashboard"
            className="btn btn-outline"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              textDecoration: 'none',
              padding: '0.75rem 1.5rem',
              fontSize: '0.95rem',
            }}
          >
            ← Back to Reports
          </Link>

          <Link
            href={report.reportHref}
            className="btn btn-primary"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              textDecoration: 'none',
              padding: '0.75rem 1.75rem',
              fontSize: '0.95rem',
              fontWeight: 600,
            }}
          >
            Open Live {report.tag} →
          </Link>
        </div>
      </div>
    </div>
  );
}
