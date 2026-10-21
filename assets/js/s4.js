document.getElementById('copyWeights')?.addEventListener('click', () => {
  const text = document.getElementById('weightsText').textContent;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.getElementById('copyWeights');
    btn.textContent = 'Copied';
    setTimeout(() => btn.textContent = 'Copy weights', 1500);
  });
});
