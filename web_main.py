import os
import socket as _socket
from web_app import socketio, app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))

    try:
        local_ip = _socket.gethostbyname(_socket.gethostname())
    except Exception:
        local_ip = '127.0.0.1'

    print('\n  Dice Auction — web server starting')
    print(f'  Local:   http://localhost:{port}')
    print(f'  Network: http://{local_ip}:{port}')
    print('\n  Share the network link with players on the same Wi-Fi.\n')

    socketio.run(app, host='0.0.0.0', port=port, debug=False, use_reloader=False,
                 allow_unsafe_werkzeug=True)
