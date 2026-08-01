const packager = require('electron-packager');
async function main() {
  try {
    const paths = await packager({
      dir: '.',
      name: 'CongTyTuTien',
      platform: 'win32',
      arch: 'x64',
      out: 'release3',
      overwrite: true,
    });
    console.log('SUCCESS:', paths);
  } catch (err) {
    console.error('FAILED:', err.message);
  }
}
main();
