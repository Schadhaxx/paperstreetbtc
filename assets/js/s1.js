
document.querySelectorAll('.read-toggle').forEach(btn => {
  btn.addEventListener('click', () => {
    const article = btn.closest('.article');
    const title = article.querySelector('h3').textContent;
    const date = article.querySelector('.article-date').textContent;
    const fullHtml = article.querySelector('.article-full').innerHTML;
    const xLink = article.querySelector('.article-link').href;
    const coverEl = article.querySelector('.article-cover');
    const coverHtml = coverEl ? `<figure class="modal-cover"><img src="${coverEl.getAttribute('src')}" alt="${coverEl.alt}"></figure>` : '';

    const modal = document.createElement('div');
    modal.className = 'article-modal article-modal--x';
    modal.innerHTML = `
      ${coverHtml}
      <div class="modal-hero">
        <div class="modal-brand">
          <img src="assets/img/owl-220.png" alt="" class="modal-logo">
          <div>
            <p class="modal-date">${date}</p>
            <h2>${title}</h2>
          </div>
        </div>
        <div class="modal-actions">
          <a class="download-pdf" href="assets/pdf/${title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.pdf" download target="_blank" rel="noreferrer noopener">Download PDF</a>
          <button class="close-modal">Close</button>
        </div>
      </div>
      <div class="modal-body">
        ${fullHtml}
      </div>
    `;
    document.body.appendChild(modal);
    document.body.style.overflow = 'hidden';

    modal.querySelector('.close-modal').addEventListener('click', () => {
      modal.remove();
      document.body.style.overflow = '';
    });

  });
});
