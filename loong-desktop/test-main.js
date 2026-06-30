console.log('process.type:', process.type);
console.log('Electron version:', process.versions.electron);

const { app, BrowserWindow } = require('electron');

app.whenReady().then(() => {
  const win = new BrowserWindow({ width: 800, height: 600 });
  win.loadURL('data:text/html,<h1>Hello COGU Loong!</h1>');
});
