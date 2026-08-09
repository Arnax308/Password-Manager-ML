const { app, BrowserWindow, Tray, Menu, ipcMain, globalShortcut, shell } = require('electron');
const path = require('path');
const http = require('http');
const { spawn, execSync } = require('child_process');

let mainWindow = null;
let popupWindow = null;
let tray = null;
let pythonProcess = null;

const BACKEND_URL = 'http://127.0.0.1:5000';
const STARTUP_REG_KEY = 'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run';
const STARTUP_REG_NAME = 'Valtr';

function checkBackendReady(callback) {
  http.get(`${BACKEND_URL}/api/status`, (res) => {
    if (res.statusCode === 200) {
      callback(true);
    } else {
      callback(false);
    }
  }).on('error', () => {
    callback(false);
  });
}

function startBackendServer() {
  checkBackendReady((isReady) => {
    if (isReady) {
      console.log('Python FastAPI backend already running on 127.0.0.1:5000');
      return;
    }
    console.log('Starting Python FastAPI backend process...');
    const pythonExe = 'C:\\Users\\arnav\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe';
    const scriptPath = path.join(__dirname, 'app.py');
    pythonProcess = spawn(pythonExe, [scriptPath], {
      cwd: __dirname,
      detached: false,
      stdio: 'ignore'
    });
    pythonProcess.on('error', (err) => {
      console.error('Failed to start Python backend:', err);
    });
  });
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 820,
    minWidth: 1000,
    minHeight: 700,
    title: 'Valtr',
    backgroundColor: '#0b1221',
    icon: path.join(__dirname, 'logo.png'),
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: false
    },
    frame: true,
    show: false
  });

  mainWindow.loadFile(path.join(__dirname, 'web_ui', 'index.html'));

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
    return false;
  });
}

function initPopupWindow() {
  if (popupWindow && !popupWindow.isDestroyed()) return;

  popupWindow = new BrowserWindow({
    width: 420,
    height: 520,
    frame: false,
    transparent: false,
    resizable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    backgroundColor: '#0a0f18',
    icon: path.join(__dirname, 'logo.png'),
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: false
    },
    show: false
  });

  popupWindow.loadFile(path.join(__dirname, 'web_ui', 'popup.html'));

  // Hide on blur instead of destroying window for instant re-opening
  popupWindow.on('blur', () => {
    if (popupWindow && !popupWindow.isDestroyed() && !popupWindow.webContents.isDevToolsOpened()) {
      popupWindow.hide();
    }
  });

  popupWindow.on('closed', () => {
    popupWindow = null;
  });
}

function showPopupWindow() {
  if (!popupWindow || popupWindow.isDestroyed()) {
    initPopupWindow();
  }

  // Get cursor position to place popup near it
  const { screen } = require('electron');
  const cursorPoint = screen.getCursorScreenPoint();
  const display = screen.getDisplayNearestPoint(cursorPoint);
  const { workArea } = display;

  let x = cursorPoint.x - 180;
  let y = cursorPoint.y - 50;
  const popupWidth = 420;
  const popupHeight = 520;

  if (x + popupWidth > workArea.x + workArea.width) x = workArea.x + workArea.width - popupWidth - 10;
  if (y + popupHeight > workArea.y + workArea.height) y = workArea.y + workArea.height - popupHeight - 10;
  if (x < workArea.x) x = workArea.x + 10;
  if (y < workArea.y) y = workArea.y + 10;

  popupWindow.setPosition(Math.round(x), Math.round(y));

  // SHOW INSTANTLY (0ms latency!)
  popupWindow.show();
  popupWindow.focus();

  // Non-blocking background call to Python context capture
  http.get(`${BACKEND_URL}/api/popup/prepare`, () => {}).on('error', () => {});

  // Notify renderer popup view to focus search input and refresh
  if (popupWindow.webContents) {
    popupWindow.webContents.send('popup-shown');
  }
}

function createTray() {
  try {
    const iconPath = path.join(__dirname, 'logo.png');
    tray = new Tray(iconPath);
    const contextMenu = Menu.buildFromTemplate([
      {
        label: 'Open Valtr',
        click: () => {
          if (mainWindow) {
            mainWindow.show();
            mainWindow.focus();
          }
        }
      },
      {
        label: 'Quick Access Popup',
        click: () => {
          showPopupWindow();
        }
      },
      { type: 'separator' },
      {
        label: 'Quit',
        click: () => {
          app.isQuitting = true;
          if (pythonProcess) {
            pythonProcess.kill();
          }
          app.quit();
        }
      }
    ]);
    tray.setToolTip('Valtr - ML Password Manager');
    tray.setContextMenu(contextMenu);
    tray.on('double-click', () => {
      if (mainWindow) {
        mainWindow.show();
        mainWindow.focus();
      }
    });
  } catch (err) {
    console.error('Tray creation failed:', err);
  }
}

function formatShortcutForElectron(str) {
  if (!str) return 'CommandOrControl+Shift+L';
  return str.split('+')
    .map(part => {
      const p = part.trim().toLowerCase();
      if (p === 'ctrl' || p === 'control') return 'CommandOrControl';
      if (p === 'alt') return 'Alt';
      if (p === 'shift') return 'Shift';
      if (p === 'meta' || p === 'cmd' || p === 'win') return 'Super';
      return p.toUpperCase();
    })
    .join('+');
}

function registerGlobalHotkey(hotkeyStr = 'ctrl+shift+l') {
  try {
    globalShortcut.unregisterAll();

    // Sentinel: just unregister (used during hotkey recording so modifiers aren't swallowed)
    if (hotkeyStr === '__unregister_all__') {
      console.log('Global shortcuts temporarily unregistered for recording');
      return;
    }

    const accelerator = formatShortcutForElectron(hotkeyStr);
    const success = globalShortcut.register(accelerator, () => {
      console.log('Global hotkey pressed:', accelerator);
      showPopupWindow();
    });
    console.log(`Global hotkey registered [${accelerator}]:`, success);
  } catch (err) {
    console.error('Failed to register global hotkey:', err);
  }
}

// ── STARTUP REGISTRY HELPERS (Issue 6 fix) ──
function getStartupBatPath() {
  return path.join(__dirname, 'Run-Valtr.bat');
}

function isStartupEnabled() {
  try {
    const result = execSync(`reg query "${STARTUP_REG_KEY}" /v "${STARTUP_REG_NAME}"`, {
      encoding: 'utf8',
      windowsHide: true
    });
    return result.includes(STARTUP_REG_NAME);
  } catch (e) {
    // Key doesn't exist
    return false;
  }
}

function setStartupEnabled(enabled) {
  try {
    if (enabled) {
      const batPath = getStartupBatPath();
      execSync(`reg add "${STARTUP_REG_KEY}" /v "${STARTUP_REG_NAME}" /t REG_SZ /d "\\"${batPath}\\"" /f`, {
        encoding: 'utf8',
        windowsHide: true
      });
    } else {
      execSync(`reg delete "${STARTUP_REG_KEY}" /v "${STARTUP_REG_NAME}" /f`, {
        encoding: 'utf8',
        windowsHide: true
      });
    }
    return isStartupEnabled();
  } catch (e) {
    console.error('Failed to update startup registry:', e);
    return isStartupEnabled();
  }
}

app.whenReady().then(() => {
  Menu.setApplicationMenu(null);
  startBackendServer();
  createMainWindow();
  initPopupWindow();
  createTray();
  registerGlobalHotkey('ctrl+shift+l');

  // ── Startup Settings (registry-based) ──
  ipcMain.handle('get-startup-setting', () => {
    return isStartupEnabled();
  });

  ipcMain.handle('set-startup-setting', (event, openAtLogin) => {
    return setStartupEnabled(Boolean(openAtLogin));
  });

  ipcMain.handle('set-global-hotkey', (event, hotkey) => {
    registerGlobalHotkey(hotkey);
    return true;
  });

  // ── Popup IPC ──
  ipcMain.on('close-popup', () => {
    if (popupWindow && !popupWindow.isDestroyed()) {
      popupWindow.hide();
    }
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    // Keep backend alive in tray
  }
});

app.on('before-quit', () => {
  app.isQuitting = true;
  if (pythonProcess) {
    pythonProcess.kill();
  }
});
