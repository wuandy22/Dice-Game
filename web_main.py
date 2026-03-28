import socket as _socket
from web_app import socketio, app

if __name__ == '__main__':
    try:
        local_ip = _socket.gethostbyname(_socket.gethostname())
    except Exception:
        local_ip = '127.0.0.1'

    print('\n  Dice Auction — web server starting')
    print(f'  Local:   http://localhost:5000')
    print(f'  Network: http://{local_ip}:5000')
    print('\n  Share the network link with players on the same Wi-Fi.\n')

    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)
