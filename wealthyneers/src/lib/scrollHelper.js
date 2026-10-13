/**
 * Helper utilities for consistent smooth-scrolling to landing page sections
 * taking into account sticky header offset, prefers-reduced-motion, and browser history.
 */

export function scrollToSection(sectionId) {
  if (typeof window === 'undefined') return;
  const el = document.getElementById(sectionId);
  if (!el) return;

  const header = document.querySelector('.header');
  const headerHeight = header ? header.offsetHeight : 80;
  const currentScrollY = window.scrollY || window.pageYOffset || 0;
  const targetTop = el.getBoundingClientRect().top + currentScrollY - headerHeight - 16;
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  window.scrollTo({
    top: Math.max(0, targetTop),
    behavior: prefersReduced ? 'auto' : 'smooth',
  });
}

export function handleSectionClick(e, sectionId, pathname, onNavigate) {
  // Allow opening in new tabs via modifier keys or non-primary mouse clicks
  if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) {
    return;
  }

  if (pathname === '/') {
    e.preventDefault();
    if (typeof onNavigate === 'function') {
      onNavigate();
    }

    scrollToSection(sectionId);

    // Keep URL hash updated without cluttering history on repeated clicks
    if (window.location.hash !== `#${sectionId}`) {
      window.history.pushState(null, '', `/#${sectionId}`);
    }
  } else {
    if (typeof onNavigate === 'function') {
      onNavigate();
    }
  }
}
