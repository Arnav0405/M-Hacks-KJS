from flask import Flask, redirect, url_for

app = Flask(__name__)

# Route to display after successful OAuth sign-in
@app.route('/')
def home():
    return "Welcome! You’ve successfully signed in with your Somaiya.edu account."

if __name__ == '__main__':
    app.run(port=8000)
