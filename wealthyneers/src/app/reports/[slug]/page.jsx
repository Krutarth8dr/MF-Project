import Image from 'next/image';
import Link from 'next/link';
import { notFound } from 'next/navigation';

export const REPORT_PREVIEWS = {
  'report-1': {
    id: 1,
    tag: 'Report 1',
    title: 'Mutual Fund Quantity Trend',
    description:
      'The foundation report for reconstructing the institutional holding history of any security. Filter by security, AMC, fund, and industry to analyze long-term accumulation, distribution, turning points, and total share quantities held across asset managers over time.',
    previewImage: '/previews/report-1-preview.svg',
    imageAlt: 'Mutual Fund Quantity Trend Report UI Preview',
    metaTitle: 'Wealthyneers | Mutual Fund Quantity Trend',
    metaDesc:
      'Explore the Mutual Fund Quantity Trend report and understand how institutional holdings change across securities, AMCs, and funds.',
    reportHref: '/report1',
  },
  'report-2': {
    id: 2,
    tag: 'Report 2',
    title: 'Monthly Institutional Activity Monitor',
    description:
      'Compares the latest portfolio snapshot with previous months. A practical buying and selling scanner tracking largest increases, decreases, new positions, and total exits across the Indian equity mutual fund universe.',
    previewImage: '/previews/report-2-preview.svg',
    imageAlt: 'Monthly Institutional Activity Monitor Report UI Preview',
    metaTitle: 'Wealthyneers | Monthly Institutional Activity Monitor',
    metaDesc:
      'Scan monthly institutional activity to identify large mutual fund additions, reductions, new positions, and total exits.',
    reportHref: '/report2',
  },
  'report-3': {
    id: 3,
    tag: 'Report 3',
    title: 'AMC-wise Stock Intelligence',
    description:
      'Isolates a single security and compares how different AMCs have changed positions over time. See which AMC accumulated first, comparative exposure levels, and institutional agreement across fund houses.',
    previewImage: '/previews/report-3-preview.svg',
    imageAlt: 'AMC-wise Stock Intelligence Report UI Preview',
    metaTitle: 'Wealthyneers | AMC-wise Stock Intelligence',
    metaDesc:
      'Compare AMC-wise mutual fund holding trends for individual securities to uncover early accumulators and institutional divergence.',
    reportHref: '/report3',
  },
  'report-4': {
    id: 4,
    tag: 'Report 4',
    title: 'AMC Direction Matrix',
    description:
      'A cross-sectional matrix compressing AMC-level behaviour into directional indicators (🟢 Buying, 🔴 Selling, ⚪ Neutral) across the equity universe, making institutional alignment or disagreement easy to scan at a glance.',
    previewImage: '/previews/report-4-preview.svg',
    imageAlt: 'AMC Direction Matrix Report UI Preview',
    metaTitle: 'Wealthyneers | AMC Direction Matrix',
    metaDesc:
      'A cross-sectional matrix displaying mutual fund buying and selling directions across major Indian asset management companies.',
    reportHref: '/report4',
  },
  'report-5': {
    id: 5,
    tag: 'Report 5',
    title: 'Institutional Buying & Selling Rankings',
    description:
      'The ranking engine converting AMC activity into actionable shortlists using Total Buying/Selling AMC Counts, Net Buying Scores, and conviction breadth to highlight stocks with broad institutional consensus.',
    previewImage: '/previews/report-5-preview.svg',
    imageAlt: 'Institutional Buying & Selling Rankings Report UI Preview',
    metaTitle: 'Wealthyneers | Institutional Buying & Selling Rankings',
    metaDesc:
      'Institutional buying and selling leaderboards ranking stocks by net institutional consensus and conviction breadth.',
    reportHref: '/report5',
  },
  'report-6': {
    id: 6,
    tag: 'Report 6',
    title: '7-Month Institutional Holding Direction',
    description:
      'A universe-level view highlighting how widely an institutional thesis is shared across asset managers over a 7-month horizon. Identify broad high-consensus names with unbroken accumulation and divergent debate candidates.',
    previewImage: '/previews/report-6-preview.svg',
    imageAlt: '7-Month Institutional Holding Direction Report UI Preview',
    metaTitle: 'Wealthyneers | 7-Month Institutional Holding Direction',
    metaDesc:
      'Analyze 7-month consecutive institutional holding trajectories and identify long-term accumulation trends across the equity universe.',
    reportHref: '/report6',
  },
};

export async function generateStaticParams() {
  return Object.keys(REPORT_PREVIEWS).map((slug) => ({
    slug,
  }));
}

export async function generateMetadata({ params }) {
  const { slug } = await params;
  const report = REPORT_PREVIEWS[slug];
  if (!report) return {};

  return {
    title: report.metaTitle,
    description: report.metaDesc,
  };
}

export default async function ReportDescriptionPage({ params }) {
  const { slug } = await params;
  const report = REPORT_PREVIEWS[slug];

  if (!report) {
    notFound();
  }

  return (
    <div className="report-preview-page" style={{ minHeight: '80vh', padding: '2.5rem 1rem 4rem' }}>
      <div className="container" style={{ maxWidth: '1140px', margin: '0 auto' }}>
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
              Public Report Overview
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

        {/* Large Static Illustrative Preview Image */}
        <div
          style={{
            background: '#0a1124',
            border: '1px solid var(--border, #1c2541)',
            borderRadius: '1rem',
            padding: '1rem',
            marginBottom: '1.25rem',
            boxShadow: '0 8px 30px rgba(0, 0, 0, 0.35)',
            overflow: 'hidden',
          }}
        >
          <div style={{ position: 'relative', width: '100%', aspectRatio: '1200 / 680' }}>
            <Image
              src={report.previewImage}
              alt={report.imageAlt}
              fill
              sizes="(max-width: 1200px) 100vw, 1140px"
              style={{ objectFit: 'contain', borderRadius: '0.5rem' }}
              priority
            />
          </div>
        </div>

        {/* Disclaimer Note */}
        <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          <p
            style={{
              fontSize: '0.875rem',
              color: 'var(--muted, #94a3b8)',
              fontStyle: 'italic',
              margin: 0,
            }}
          >
            Illustrative preview — example data shown for demonstration purposes only.
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
