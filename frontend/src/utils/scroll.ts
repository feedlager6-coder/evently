export const resetScrollContainerInstant = (containerId = 'app-scroll-container') => {
  const el = document.getElementById(containerId);
  if (!el) return;
  // Временное отключение overflowY в iOS WebKit мгновенно убивает активную физику momentum scroll
  el.style.overflowY = 'hidden';
  el.scrollTop = 0;
  void el.offsetHeight; // force reflow
  requestAnimationFrame(() => {
    el.style.overflowY = 'auto';
  });
};
