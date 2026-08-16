const cards = [...document.querySelectorAll('.report-card')];
const filters = [...document.querySelectorAll('.filter')];
const search = document.querySelector('#research-search');
const count = document.querySelector('#result-count');
const noResults = document.querySelector('#no-results');

let activeFilter = 'all';

function updateResults() {
  const query = search.value.trim().toLowerCase();
  let visible = 0;

  for (const card of cards) {
    const text = `${card.textContent} ${card.dataset.topics}`.toLowerCase();
    const matchesQuery = !query || text.includes(query);
    const matchesFilter = activeFilter === 'all' || card.dataset.topics.includes(activeFilter);
    const show = matchesQuery && matchesFilter;

    card.hidden = !show;
    if (show) visible += 1;
  }

  count.textContent = visible === cards.length
    ? `Showing all ${cards.length} research summaries`
    : `Showing ${visible} of ${cards.length} research summaries`;
  noResults.hidden = visible !== 0;
}

for (const filter of filters) {
  filter.addEventListener('click', () => {
    activeFilter = filter.dataset.filter;
    for (const item of filters) {
      const selected = item === filter;
      item.classList.toggle('is-active', selected);
      item.setAttribute('aria-pressed', String(selected));
    }
    updateResults();
  });
}

search.addEventListener('input', updateResults);
