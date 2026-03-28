import os
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from dice_auction.game_state import GameManager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'web', 'templates'),
    static_folder=os.path.join(BASE_DIR, 'web', 'static'),
)
app.secret_key = 'dice-auction-secret'
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins='*')

gm = GameManager(socketio)


# ── HTTP routes ───────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('game.html')


# ── SocketIO events ───────────────────────────────────────────────────────────

@socketio.on('connect')
def on_connect():
    snap = gm.get_state_for(request.sid)
    emit('public_state', snap['pub'])
    name = snap['sids'].get(request.sid)
    if name:
        dice = snap['priv'].get(name, [])
        emit('private_dice', {'name': name, 'dice': dice})


@socketio.on('disconnect')
def on_disconnect():
    gm.disconnect(request.sid)


@socketio.on('register')
def on_register(data):
    name = (data or {}).get('name', '')
    success, error = gm.register(request.sid, name)
    emit('register_result', {'success': success, 'error': error, 'name': name if success else ''})


@socketio.on('request_rejoin')
def on_rejoin(data):
    name = (data or {}).get('name', '')
    success = gm.reconnect(request.sid, name)
    emit('rejoin_result', {'success': success, 'name': name if success else ''})


@socketio.on('start_game')
def on_start(data):
    total = int((data or {}).get('total_rounds', 0))
    success, error = gm.start_game(request.sid, total)
    if not success:
        emit('error_msg', {'message': error})


@socketio.on('mark_ready')
def on_ready():
    gm.mark_ready(request.sid)


@socketio.on('choose_auction_die')
def on_choose_die(data):
    idx = int((data or {}).get('index', -1))
    success, error = gm.choose_auction_die(request.sid, idx)
    if not success:
        emit('error_msg', {'message': error})


@socketio.on('bid')
def on_bid(data):
    amount = (data or {}).get('amount')
    success, error = gm.place_bid(request.sid, amount)
    if not success:
        emit('bid_error', {'message': error})


@socketio.on('choose_exchange_die')
def on_exchange(data):
    idx = int((data or {}).get('index', -1))
    success, error = gm.choose_exchange_die(request.sid, idx)
    if not success:
        emit('error_msg', {'message': error})


@socketio.on('next_round')
def on_next_round():
    gm.next_round(request.sid)
