(() => {
  const main = document.querySelector('[data-recipe-id]');
  if (main) {
    const key = `ryce-ingredients:${main.dataset.recipeId}`;
    const boxes = [...main.querySelectorAll('.ingredients input')];
    const reset = main.querySelector('.reset-ingredients');
    let checked = [];
    try { checked = JSON.parse(sessionStorage.getItem(key) || '[]'); } catch {}
    if (!Array.isArray(checked)) checked = [];
    boxes.forEach((box, i) => { box.checked = checked.includes(i); });
    const update = () => {
      const selected = boxes.flatMap((box, i) => box.checked ? [i] : []);
      reset.hidden = selected.length === 0;
      try { sessionStorage.setItem(key, JSON.stringify(selected)); } catch {}
    };
    boxes.forEach(box => box.addEventListener('change', update));
    reset.addEventListener('click', () => { boxes.forEach(box => { box.checked = false; }); update(); });
    update();
    document.querySelector('.share-button').addEventListener('click', async () => {
      const url = document.querySelector('link[rel="canonical"]').href;
      try {
        if (navigator.share) await navigator.share({title: document.title, url});
        else {
          await navigator.clipboard.writeText(url);
          const toast = document.querySelector('.toast');
          toast.textContent = 'Recipe link copied';
          toast.classList.add('show');
          setTimeout(() => toast.classList.remove('show'), 2500);
        }
      } catch (error) {
        if (error.name !== 'AbortError') {
          const toast = document.querySelector('.toast');
          toast.textContent = 'Copy the page address to share this recipe.';
          toast.classList.add('show');
          setTimeout(() => toast.classList.remove('show'), 4000);
        }
      }
    });
  }
  const grid = document.querySelector('#recipe-grid');
  if (!grid) return;
  const cards = [...grid.querySelectorAll('.recipe-card')];
  const search = document.querySelector('#recipe-search');
  const sort = document.querySelector('#recipe-sort');
  const filters = [...document.querySelectorAll('[data-filter]')];
  let group = 'all';
  const normalize = s => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const filter = () => {
    const words = normalize(search.value.trim()).split(/\s+/).filter(Boolean);
    let count = 0;
    cards.forEach(card => {
      const visible = (group === 'all' || card.dataset.groups.split(' ').includes(group)) && words.every(word => normalize(card.dataset.search).includes(word));
      card.hidden = !visible;
      if (visible) count++;
    });
    document.querySelector('#recipe-count').textContent = `${count} recipe${count === 1 ? '' : 's'} to make your own`;
    document.querySelector('.empty-state').hidden = count !== 0;
  };
  filters.forEach(button => button.addEventListener('click', () => {
    group = button.dataset.filter;
    filters.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    filter();
  }));
  search.addEventListener('input', filter);
  sort.addEventListener('change', () => {
    const ordered = [...cards].sort((a, b) => sort.value === 'quick' ? Number(a.dataset.minutes) - Number(b.dataset.minutes) : a.querySelector('h2').textContent.localeCompare(b.querySelector('h2').textContent));
    ordered.forEach(card => grid.appendChild(card));
  });
  document.querySelector('#clear-search').addEventListener('click', () => { search.value = ''; filters[0].click(); search.focus(); });
})();
