module.exports = {
  apps: [{
    name: 'tcgp',
    script: 'bot.py',
    interpreter: '/home/tcgphelper/venv/bin/python',
    cwd: '/home/tcgphelper',
    env: {
      PYTHONUNBUFFERED: '1'
    }
  }]
}
