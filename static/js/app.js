document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector(".menu-toggle");
  const nav = document.querySelector(".main-nav");
  if (toggle) toggle.addEventListener("click", () => nav.classList.toggle("open"));

  document.querySelectorAll(".quantity").forEach(box => {
    const input = box.querySelector("input[name=quantity]");
    box.querySelectorAll("[data-step]").forEach(button => button.addEventListener("click", () => {
      const next = Math.max(Number(input.min || 1), Math.min(Number(input.max || 99), Number(input.value || 1) + Number(button.dataset.step)));
      input.value = next;
    }));
  });

  const input = document.querySelector("#search-input");
  const suggestions = document.querySelector("#suggestions");
  let timer;
  if (input && suggestions) input.addEventListener("input", () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (!q) { suggestions.innerHTML = ""; return; }
    timer = setTimeout(async () => {
      const response = await fetch(`/api/products/suggestions?q=${encodeURIComponent(q)}`);
      const products = await response.json();
      suggestions.innerHTML = products.map(p => `<a href="${p.url}">${p.name} <span>↗</span></a>`).join("");
    }, 180);
  });

  const filterButton = document.querySelector(".mobile-filter");
  const filters = document.querySelector(".filters");
  const close = document.querySelector(".filter-close");
  if (filterButton && filters) filterButton.addEventListener("click", () => filters.classList.add("show"));
  if (close && filters) close.addEventListener("click", () => filters.classList.remove("show"));

  document.querySelectorAll(".flash").forEach(flash => setTimeout(() => flash.remove(), 4500));
});