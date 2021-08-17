from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import redirect
import hashlib
import requests
import os
from dotenv import load_dotenv

import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from logging import FileHandler, WARNING
import datetime


load_dotenv()  # load .env

app = Flask(__name__)

# logging in the txt file 
file_handler = FileHandler('errorlog.txt')
file_handler.setLevel(WARNING)
app.logger.addHandler(file_handler)

# logging with sentry.io
sentry_sdk.init(
    dsn=os.getenv('SENTRY_DSN'),
    integrations=[FlaskIntegration()],
    )

# user:password@host/database
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class Order(db.Model):
    # payment model
    id = db.Column(db.Integer, primary_key=True)
    currency = db.Column(db.String, nullable=False)
    amount= db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=False)
    created_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __init__(self, currency, amount, description):
        self.currency = currency
        self.amount = amount
        self.description = description

    def __repr__(self) -> str:
        return self.id


payway= os.getenv('PAYWAY')
shop_id = os.getenv('SHOP_ID')
SecretKey=os.getenv('SECRETKEY')


@app.route('/order', methods=['POST', 'GET'])
def create():
    def save_data(order):
        # save information ubout order in db
        try:
            db.session.add(order)
            db.session.commit()
        except:
            return 'Error'
    
    if request.method == 'POST':  
        # create order
        currency = request.form['currency']
        amount = request.form['amount']
        description = request.form['description']
        order = Order(currency=currency, amount=amount, description=description)
        
        if currency=='EUR': # Pay
            save_data(order)
            sha256_data = str(amount)+':978:'+shop_id+':'+str(order.id)+SecretKey
            sha256 = hashlib.sha256(sha256_data.encode('utf-8')).hexdigest()

            return render_template('pay_piastrix.html', amount=amount, sha256=sha256, order_id = order.id, shop_id=shop_id)

        elif currency=='USD':  # Bill
            save_data(order)

            sha256_data = '840:'+str(amount)+':840:'+str(shop_id)+':'+str(order.id)+SecretKey
            sha256 = hashlib.sha256(sha256_data.encode('utf-8')).hexdigest()

            req_dict = {
            "payer_currency": "840",
            "shop_amount": str(amount),
            "shop_currency": "840",
            "shop_id": shop_id,
            "shop_order_id": str(order.id),
            "sign": sha256
            }

            response = requests.post('https://core.piastrix.com/bill/create', json=req_dict)

            if response.ok:
                return redirect (response.json()["data"]["url"])

        elif currency=='RUB':  # Invoice
            save_data(order)

            sha256_data = str(amount)+':643:'+payway+':'+str(shop_id)+':'+str(order.id)+SecretKey
            sha256 = hashlib.sha256(sha256_data.encode('utf-8')).hexdigest()

            # data for piastrix 
            dic_form = {
                "amount": str(amount),
                "currency": "643",
                "payway": payway,
                "shop_id": shop_id,
                "shop_order_id": str(order.id),
                "sign": sha256                
                }

            # post data for piastrix 
            response_1 = requests.post("https://core.piastrix.com/invoice/create", json =dic_form)

            if response_1.ok:
                # data for advcash
                ac_data = response_1.json()['data']['data']
                general_data = response_1.json()['data']

                return render_template('invoice.html', data=ac_data, general_data=general_data)

    else:
        return render_template('order.html')


if __name__=='__main__':
    app.run(debug=int(os.getenv('FLASK_DEBUG')))
