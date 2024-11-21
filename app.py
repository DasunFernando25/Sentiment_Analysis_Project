from flask import Flask, render_template, request, redirect, url_for, session
from prediction_pipeline import preprocessing, vectorizer, get_prediction
from logger import logging
from pymongo import MongoClient
import bcrypt
import os
from dotenv import load_dotenv
import matplotlib.pyplot as plt


app = Flask(__name__)


load_dotenv()


# MongoDB connection
mongodbURI = os.getenv('MONGO_URI')

try:
    # Attempt to connect to MongoDB
    client = MongoClient(mongodbURI, serverSelectionTimeoutMS=5000)  # 5-second timeout
    # Check if the connection is successful
    client.server_info()  # This raises an exception if the connection fails
    print("MongoDB connected successfully.")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")

db = client['user_data']
collection = db['sentiment_analysis_project_admin_data']
review_collection = db['sentiment_analysis_project_review_data']



# Secret key for session
app.secret_key = os.getenv('SESSION_SECRET_KEY')


@app.route('/admin')
def admin():
    if 'username' in session:
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html')


@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if user exists in database
        user = collection.find_one({'username': username})

        if user:
            # Check if password matches the hashed password
            if bcrypt.checkpw(password.encode('utf-8'), user['password']):
                session['username'] = username
                return redirect(url_for('admin_dashboard'))
            else:
                return "Incorrect username or password"
        else:
            return "User does not exist"
    
    return render_template('admin_login.html')


@app.route('/admin_dashboard')
def admin_dashboard():
    if 'username' in session:

        username = session.get('username')

        # Fetch all reviews from MongoDB
        try:
            reviews = list(review_collection.find())
        except Exception as e:
            logging.error(f"Error retrieving reviews: {e}")
            reviews = []

        # Calculate stats
        try:
            total_reviews = len(reviews)
            positive_reviews = sum(1 for r in reviews if r.get("prediction") == "positive")
            negative_reviews = sum(1 for r in reviews if r.get("prediction") == "negative")
        except Exception as e:
            logging.error(f"Error calculating stats: {e}")
            total_reviews = 0
            positive_reviews = 0
            negative_reviews = 0

        # Calculate percestages
        if total_reviews > 0:
            positive_percentage = (positive_reviews / total_reviews) * 100
            negative_percentage = (negative_reviews / total_reviews) * 100
        else:
            positive_percentage = 0
            negative_percentage = 0

        try:
            # Generate Pie Chart
            labels = ['Positive', 'Negative']
            sizes = [positive_reviews, negative_reviews]
            colors = ['#4CAF50', '#FF5733']
            explode = (0.1, 0)  # Highlight the first slice (Positive)

            plt.figure(figsize=(6, 6))
            plt.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
            plt.title('Review Sentiment Distribution')

            # Save pie chart to static directory
            plot_path = os.path.join("static", "products/review_pie_chart.png")
            plt.savefig(plot_path)
            plt.close()  # Close the figure to release memory
        except Exception as e:
            plot_path = None


        return render_template('admin.html',
                               username=username, 
                               reviews=reviews,
                               total_reviews=total_reviews,
                               positive_reviews=positive_reviews,
                               negative_reviews=negative_reviews,
                               positive_percentage=positive_percentage,
                               negative_percentage=negative_percentage,
                               plot_path=plot_path)
    
    else:
        return redirect(url_for('admin_login'))


@app.route('/admin_logout')
def admin_logout():
    session.pop('username', None)
    return redirect(url_for('admin_login'))


@app.route('/admin_register', methods=['GET', 'POST'])
def admin_register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Check if username already exists
        if collection.find_one({'username': username}):
            return "Username already taken!"

        # Insert user into MongoDB
        collection.insert_one({'username': username, 'password': hashed_pw})
        return redirect(url_for('admin_login'))

    return render_template('admin_register.html')



logging.info('Flask server started')

data = dict()
reviews = []
positive = 0
negative = 0


@app.route("/")
def index():
    data['reviews'] = reviews
    data['positive'] = positive
    data['negative'] = negative

    logging.info('========== Open home page ============')

    return render_template('index.html', data=data)


@app.route("/", methods = ['post'])
def my_post():
    text = request.form['text']
    logging.info(f'Text : {text}')

    preprocessed_txt = preprocessing(text)
    logging.info(f'Preprocessed Text : {preprocessed_txt}')

    vectorized_txt = vectorizer(preprocessed_txt)
    logging.info(f'Vectorized Text : {vectorized_txt}')

    prediction = get_prediction(vectorized_txt)
    logging.info(f'Prediction : {prediction}')

    if prediction == 'negative':
        global negative
        negative += 1
    else:
        global positive
        positive += 1

    try:
        review_collection.insert_one({
            "review": str(text),
            "prediction": prediction
        })
        logging.info("Review and prediction saved to the database")
    except Exception as e:
        logging.error(f"Error saving review and prediction to the database: {e}")
    
    reviews.insert(0, text)
    return redirect(request.url)




if __name__ == "__main__":
    app.run()



