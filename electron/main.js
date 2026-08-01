const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow;
let serverProcess;

function startServer() {
  return new Promise((resolve) => {
    // Check if server already running
    http.get('http://localhost:8080/api/system', (res) => {
      res.resume();
      resolve(); // Server already running
    }).on('error', () => {
      // Start server
      const serverPath = path.join(__dirname, '..', 'dashboard', 'server.py');
      const pythonPath = path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe');
      serverProcess = spawn(pythonPath, [serverPath], {
        stdio: 'ignore',
        detached: false,
      });
      serverProcess.on('error', () => {});
      // Wait for server to start
      setTimeout(resolve, 2000);
    });
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    title: 'Cong Ty Tu Tien - Giam Sat He Thong',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false,
    },
  });

  mainWindow.loadURL('http://localhost:8080');

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(async () => {
  await startServer();
  createWindow();
});

app.on('window-all-closed', () => {
  if (serverProcess) {
    serverProcess.kill();
  }
  app.quit();
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});
