import electron from 'electron';
const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain } = electron;
import * as path from 'path';
import { spawn } from 'child_process';

type BrowserWindowType = InstanceType<typeof BrowserWindow>;
type TrayType = InstanceType<typeof Tray>;
type ChildProcessType = import('child_process').ChildProcess;

let mainWindow: BrowserWindowType | null = null;
let tray: TrayType | null = null;
let pythonProcess: ChildProcessType | null = null;
const API_PORT = 8198;

function getPythonPath(): string {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'cogu', 'desktop', 'loong.py');
  }
  return path.join(__dirname, '..', '..', '..', 'cogu', 'desktop', 'loong.py');
}

function getPythonExe(): string {
  return process.platform === 'win32' ? 'python' : 'python3';
}

function startPythonBackend() {
  const pythonPath = getPythonPath();
  const pythonExe = getPythonExe();

  pythonProcess = spawn(pythonExe, [pythonPath], {
    env: { ...process.env, COGU_DESKTOP: '1', COGU_API_PORT: String(API_PORT) },
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  pythonProcess.stdout?.on('data', (data: Buffer) => {
    console.log(`[Python] ${data.toString().trim()}`);
  });

  pythonProcess.stderr?.on('data', (data: Buffer) => {
    console.error(`[Python] ${data.toString().trim()}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`[Python] Process exited with code ${code}`);
    pythonProcess = null;
  });
}

function stopPythonBackend() {
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 960,
    minHeight: 600,
    frame: false,
    titleBarStyle: 'hidden',
    backgroundColor: '#050506',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
  });

  if (app.isPackaged) {
    mainWindow.loadFile(path.join(__dirname, '..', 'renderer', 'dist', 'index.html'));
  } else {
    const rendererDist = path.join(__dirname, '..', '..', 'src', 'renderer', 'dist', 'index.html');
    mainWindow.loadFile(rendererDist);
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function createTray() {
  const iconPath = path.join(__dirname, '..', '..', 'assets', 'logo.ico');
  let icon: Electron.NativeImage;
  try {
    icon = nativeImage.createFromPath(iconPath);
    if (icon.isEmpty()) icon = nativeImage.createEmpty();
  } catch {
    icon = nativeImage.createEmpty();
  }

  tray = new Tray(icon);
  const contextMenu = Menu.buildFromTemplate([
    { label: '显示主窗口', click: () => mainWindow?.show() },
    { label: '新对话', click: () => mainWindow?.webContents.send('new-chat') },
    { type: 'separator' },
    { label: '重启后端', click: () => { stopPythonBackend(); startPythonBackend(); } },
    { type: 'separator' },
    { label: '退出', click: () => { stopPythonBackend(); app.quit(); } },
  ]);

  tray.setToolTip('COGU Loong - AI Agent');
  tray.setContextMenu(contextMenu);
  tray.on('double-click', () => mainWindow?.show());
}

ipcMain.handle('get-api-port', () => API_PORT);
ipcMain.handle('get-app-version', () => app.getVersion());
ipcMain.handle('get-app-path', () => app.getAppPath());
ipcMain.handle('is-packaged', () => app.isPackaged);

ipcMain.on('window-minimize', () => mainWindow?.minimize());
ipcMain.on('window-maximize', () => {
  if (mainWindow?.isMaximized()) mainWindow.unmaximize();
  else mainWindow?.maximize();
});
ipcMain.on('window-close', () => mainWindow?.close());

app.whenReady().then(() => {
  startPythonBackend();
  createMainWindow();
  createTray();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    stopPythonBackend();
    app.quit();
  }
});

app.on('before-quit', () => {
  stopPythonBackend();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createMainWindow();
  }
});