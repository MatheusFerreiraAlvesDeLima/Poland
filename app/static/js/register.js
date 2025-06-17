// Tooltip de senha
const passwordField = document.getElementById('password');
const tooltip = document.getElementById('password-tooltip');

passwordField.addEventListener('focus', () => {
  tooltip.style.display = 'block';
  setTimeout(() => { tooltip.style.display = 'none'; }, 4000);
});

passwordField.addEventListener('blur', () => {
  tooltip.style.display = 'none';
});

// Fechar erros
document.querySelectorAll('.close-error').forEach(btn => {
  btn.addEventListener('click', (e) => {
    e.target.closest('.error-message').style.display = 'none';
  });
});

// Validação em tempo real
document.querySelectorAll('input, select').forEach(field => {
  field.addEventListener('input', () => validateField(field));
});

function validateField(field) {
  const errorElement = field.closest('.form-group').querySelector('.error-message');
  const iconElement = field.nextElementSibling;
  
  if (field.checkValidity()) {
    field.classList.add('valid');
    field.classList.remove('invalid');
    if (iconElement) iconElement.style.display = 'block';
    errorElement.style.display = 'none';
  } else {
    field.classList.add('invalid');
    field.classList.remove('valid');
    if (iconElement) iconElement.style.display = 'block';
  }
}

// Feedback de envio
const submitBtn = document.getElementById('submitBtn');
const spinner = submitBtn.querySelector('.spinner');
const buttonText = submitBtn.querySelector('.button-text');

submitBtn.addEventListener('click', function(e) {
  if (this.classList.contains('disabled')) {
    e.preventDefault();
    return;
  }
  
  buttonText.textContent = 'Sending...';
  spinner.style.display = 'inline-block';
  this.classList.add('disabled');
  
  setTimeout(() => {
    // Simulação de sucesso
    buttonText.textContent = 'Success!';
    spinner.style.display = 'none';
    
    setTimeout(() => {
      // Redirecionar ou resetar
      buttonText.textContent = 'Create Account';
      this.classList.remove('disabled');
    }, 2000);
  }, 1500);
});

// Animações do dashboard
document.querySelectorAll('.metric-value').forEach(el => {
  const target = parseInt(el.dataset.target);
  animateValue(el, 0, target, 1500);
});

function animateValue(el, start, end, duration) {
  let startTimestamp = null;
  const step = (timestamp) => {
    if (!startTimestamp) startTimestamp = timestamp;
    const progress = Math.min((timestamp - startTimestamp) / duration, 1);
    const value = Math.floor(progress * (end - start) + start);
    el.textContent = value;
    if (progress < 1) window.requestAnimationFrame(step);
  };
  window.requestAnimationFrame(step);
}