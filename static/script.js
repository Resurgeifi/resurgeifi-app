// Grab carousel and its components
const carousel = document.querySelector('.carousel');
const cards = document.querySelectorAll('.card');
const dots = document.querySelectorAll('.dot');

// Function to update active card styling
function updateCarousel() {
  const scrollPosition = carousel.scrollLeft;
  const cardWidth = carousel.offsetWidth;
  const index = Math.round(scrollPosition / cardWidth);

  console.log("Active card index:", index); // This will show in the DevTools console

  // Update nav dots
  dots.forEach((dot, i) => {
    dot.classList.toggle('active', i === index);
  });

  // Update card appearance
  cards.forEach((card, i) => {
    card.classList.toggle('active', i === index);
  });
}

// When user scrolls, run updateCarousel
carousel.addEventListener('scroll', () => {
  updateCarousel();
});

// Run once when page loads
window.onload = () => {
  updateCarousel();
};

