let installPrompt = null;
const button = document.getElementById('install');
const status = document.getElementById('status');
const standalone = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone;
if (standalone) status.textContent = 'You’re already using KP Sales OS as an app.';
window.addEventListener('beforeinstallprompt', event => {
  event.preventDefault();
  installPrompt = event;
  if (!standalone) button.hidden = false;
});
window.addEventListener('appinstalled', () => {
  installPrompt = null;
  button.hidden = true;
  status.textContent = 'KP Sales OS is installed. Open it from your app icon.';
});
button.addEventListener('click', async () => {
  if (!installPrompt) return;
  const prompt = installPrompt;
  installPrompt = null;
  button.hidden = true;
  try {
    await prompt.prompt();
    const choice = await prompt.userChoice;
    status.textContent = choice.outcome === 'accepted'
      ? 'Installation requested. Your browser will finish adding the app.'
      : 'You can install later using your browser’s app menu.';
  } catch {
    status.textContent = 'Use the installation steps for your device below.';
  }
});
