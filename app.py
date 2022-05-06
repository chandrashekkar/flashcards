#python -m gunicorn --bind 0.0.0.0:5000 app:app --> for production environment
from flask import Flask,abort, redirect, url_for,Blueprint, render_template, request, flash
from flask_sqlalchemy import SQLAlchemy
from os import path
from flask_login import LoginManager, login_manager
from flask_restful import Api,Resource, Api,fields, marshal_with,reqparse
from flask import current_app as app
from werkzeug.security import generate_password_hash, check_password_hash
import random
import sys
from flask_login import login_user, logout_user, current_user, UserMixin
from flask_login.utils import login_required
from werkzeug.utils import redirect
import requests
from datetime import datetime
from sqlalchemy.sql import func
#from waitress import serve

app = Flask(__name__)
api = Api(app)
db = SQLAlchemy(app)
DB_NAME = "project.sqlite3"
app.config['SECRET_KEY'] = 'incredible@india'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)



user_post_args = reqparse.RequestParser()
user_post_args.add_argument('username')
user_post_args.add_argument('password')

card_put_args = reqparse.RequestParser()
card_put_args.add_argument('score')

deck_post_args = reqparse.RequestParser()
deck_post_args.add_argument('deck_name')

card_post_args = reqparse.RequestParser()
card_post_args.add_argument('front')
card_post_args.add_argument('back')


class User_api(Resource):
    def post(self):
        args = user_post_args.parse_args()
        usr = User.query.filter_by(username=args['username']).first()
        if usr:
            flash('Username is already in use.', category='error')
            return redirect('/register')
        elif len(args['username']) < 6:
            flash('Username is too short.', category='error')
            return redirect('/register')
        elif len(args['password']) < 6:
            flash('Password is too short.', category='error')
            return redirect('/register')
        
        new_user = User(username=args['username'], password = generate_password_hash(args['password'], method='sha256'))
        try:
            db.session.add(new_user)
            db.session.commit()
            return redirect('/login')
        except:
            return redirect('/register')
    def get(self, username):
        usr = User.query.filter_by(username=username).first()
        dck = Deck.query.filter_by(user=username)
        dck_cnt = dck.count()
        score=[deck.score for deck in dck]
        return{
            "username": usr.username,
            "deck_count": dck_cnt,
            "score": score
        }







class Deck_api(Resource):
    def post(self, username):
        args = deck_post_args.parse_args()
        deck_query = Deck.query.filter_by(user=username)
        deck_list=[]
        for dq in deck_query:
            deck_list.append(dq.deck_name)

        if args['deck_name'] in deck_list:
            raise AlreadyExists(status_code=409, error_code="DECK069", error_message="Deck Already exists")
        dek = Deck(deck_name=args['deck_name'], user=username)
        db.session.add(dek)
        db.session.commit()
        return redirect('/dashboard')

    def get(self, username):
        decks = Deck.query.filter_by(user=username)

        r=[]
        for deck in decks:
            r.append({'deck_name':deck.deck_name, 'score':deck.score, 'last_rev':str(deck.last_rev)})
        print(r)
            
        return r
        
    




class   Card_api(Resource):
    def post(self, deck):
        args = card_post_args.parse_args()
        new_card = Card(front=args['front'], back = args['back'], deck=deck)
        db.session.add(new_card)
        db.session.commit()
        return redirect(f'/review/{deck}')
    def get(self, deck, username):
        
        decks = Deck.query.filter_by(user=username, deck_name = deck)
        decknames=[d.deck_name for d in decks]
        if deck in decknames:
            cards = Card.query.filter_by(deck=deck)
            card_list=[]
            if cards:
                for card in cards:
                    card_list.append(card)
                random.shuffle(card_list)
                rc = card_list.pop()
                return {
                    "card_id": rc.card_id,
                    "deck": rc.deck,
                    "front": rc.front,
                    "back": rc.back
                }
            return {}
        return None
    def put(self, card_id):
        c=Card.query.filter_by(card_id=int(card_id)).first()
        args=card_put_args.parse_args()
        c.score = args['score']
        db.session.commit()

api.add_resource(User_api, '/api/user', '/api/user/<string:username>')
api.add_resource(Deck_api, '/api/deck/<string:username>')
api.add_resource(Card_api, '/api/<string:username>/<string:deck>/card', '/api/card/<string:card_id>','/api/<string:deck>')

views = Blueprint("views", __name__)

BASE = 'http://127.0.0.1:5000'

@views.route('/dashboard', methods = ['GET', 'POST'])
@login_required
def home():
    data = requests.get(BASE+f'/api/deck/{current_user.username}')
    
    return render_template('dashboard.html', decks=data.json(), user=current_user.username)

@views.route('/', methods=['GET'])
def landing():
    return render_template('index.html')


@views.route('/review/<string:deck>', methods = ['GET', 'POST'])
@login_required
def review(deck):
    t = datetime.now()
    d=Deck.query.filter_by(deck_name=deck).first()
    d.last_rev=t
    db.session.commit()
    data=requests.get(BASE+ f'/api/{current_user.username}/{deck}/card')
    

    if data:
        return render_template('review.html', front = data.json()['front'], back = data.json()['back'], deck=data.json()['deck'], card_id=data.json()['card_id'])
    else:
        return render_template('review.html', deck=deck, data=True)

@views.route('/review/<string:deck>/<int:card_id>', methods = ['GET', 'POST'])
def score(deck,card_id):
    if request.method == 'POST':
        c = Card.query.filter_by(card_id=card_id).first()
        s = int(request.form.get('score'))
        c.score = s
        db.session.commit()
        d= Deck.query.filter_by(deck_name=deck, user=current_user.username).first()
        cn = Card.query.filter_by(deck=deck).count()
        d.score = d.score + (c.score/cn)
        db.session.commit()
        return redirect(f'/review/{deck}')




@views.route('/login', methods = ['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()
        if user:
            if check_password_hash(user.password, password):
                login_user(user, remember=True)
                return redirect('/dashboard')
            else:
                flash('Password is incorrect.', category='error')
        else:
            flash('Username does not exist.', category='error')

    return render_template('login.html')




@views.route('/register', methods = ['GET', 'POST'])
def register():
    return render_template('register.html')


@views.route('/<string:deck>/addcard', methods=['GET', 'POST'])
def addcard(deck):
    return render_template('addcard.html')


@views.route('/<string:user>/deck/<string:deck>/delete', methods=['GET','POST'])
def deletedeck(deck, user):
    d= Deck.query.filter_by(deck_name=deck, user=user).first()
    db.session.delete(d)
    db.session.commit()
    return redirect('/dashboard')



@views.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')

app.register_blueprint(views, url_prefix="/")

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(30), unique=True, nullable = False)
    password = db.Column(db.String(300), nullable=False)
    date_created = db.Column(db.DateTime(timezone=True), default=func.now())
    score = db.Column(db.Integer, default = 0)
    udeck = db.relationship('Deck', cascade='all, delete-orphan', backref='deck')



class Deck(db.Model):
    __tablename__ = 'deck'
    id = db.Column(db.Integer, primary_key=True)
    deck_name = db.Column(db.String(30))
    user = db.Column(db.String, db.ForeignKey('user.username'), nullable=False)
    date_created = db.Column(db.DateTime(timezone=True), default=func.now())
    score = db.Column(db.Integer, default=0)
    is_public = db.Column(db.Boolean, default = False)
    last_rev = db.Column(db.DateTime(timezone=True), default=func.now())
    dcard = db.relationship('Card', cascade='all, delete-orphan', backref='card')

class Card(db.Model):
    __tablename__ = 'card'
    card_id = db.Column(db.Integer, primary_key=True)
    front = db.Column(db.String(512), nullable = False)
    back = db.Column(db.String(512), nullable = False)
    score = db.Column(db.Integer, default = 0)
    deck = db.Column(db.String, db.ForeignKey('deck.deck_name'), nullable = False)

login_manager = LoginManager()
login_manager.login_view = "views.login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

if not path.exists("flashkard/"+ DB_NAME):
    db.create_all(app=app)
print('DATABASE ALREADY EXISTS')

if __name__=='__main__':
    app.run(debug=True,
            host = '0.0.0.0',
            port=5000
            )
    #serve(app, host='0.0.0.0', port=5000)