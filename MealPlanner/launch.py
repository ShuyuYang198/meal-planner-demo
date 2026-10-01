"""Double-click Start.command to run and open the local demo."""
import threading, webbrowser, urllib.request
URL='http://127.0.0.1:8111/'
try:
    with urllib.request.urlopen(URL,timeout=1) as response:
        active=b'Local demo' in response.read()
except Exception:
    active=False
if active:
    webbrowser.open(URL)
else:
    from server import app
    threading.Timer(1.0,lambda:webbrowser.open(URL)).start()
    print('Meal Planner: '+URL+'\nLogin: demo (no password).\nKeep this window open. Press Control+C to stop.')
    app.run(host='127.0.0.1',port=8111,debug=False)
