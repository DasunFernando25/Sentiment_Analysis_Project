from flask import Flask, render_template



app = Flask(__name__)

data = dict()
reviews = []
positive = 0
negative = 0

@app.route('/')
def index():
    data['reviews'] = reviews
    data['positive'] = positive
    data['negative'] = negative

    return render_template('index.html', data=data)