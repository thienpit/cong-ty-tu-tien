const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow;
let serverProcess;

// Start the Python backend server
function startServer() {
  const serverPath = path.join(__dirname, '..', 'dashboard', 'server.py');
  const pythonPath = path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe');
  
  serverProcess = spawn(pythonPath, [serverPath], {
    stdio: 'ignore',
    detached: false,
  });

  serverProcess.on('error', (err) => {
    console.error('Failed to start server:', err);
  });

  // Wait for server to start
  return new Promise((resolve) => setTimeout(resolve, 2000));
}

// Create the browser window
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    title: 'Công Ty Tu Tiên - Giám Sát Hệ Thống',
    icon: path.join(__dirname, '..', 'dashboard', 'icon-512.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // Load the dashboard from local server
  mainWindow.loadURL('http://localhost:8080');

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// App lifecycle
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
