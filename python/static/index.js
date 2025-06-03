import { APPS } from './apps.js';

// build nav bar & landing-page cards from the same source of truth
function buildNav() {
  const nav = document.getElementById('nav');
  APPS.forEach(a => {
    const link = document.createElement('a');
    link.href = a.href;
    link.textContent = a.name;
    nav.appendChild(link);
  });
}

function buildGrid() {
  const grid = document.getElementById('grid');
  APPS.forEach(a => {
    const card = document.createElement('div');
    card.className = 'card';
    card.onclick = () => (location.href = a.href);
    card.innerHTML = `
      <div style="font-size:3rem">${a.icon}</div>
      <h2>${a.name}</h2>
      <p>${a.desc}</p>`;
    grid.appendChild(card);
  });
}

buildNav();
buildGrid();
