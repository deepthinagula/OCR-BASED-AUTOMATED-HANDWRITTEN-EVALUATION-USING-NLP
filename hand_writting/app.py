import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session, flash
import requests
import os
import nltk
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from PIL import Image
from io import BytesIO
from sentence_transformers import SentenceTransformer
import string
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from sklearn.feature_extraction.text import CountVectorizer

# Download NLTK stopwords if not done yet
nltk.download('stopwords')

app = Flask(__name__)
app.config.from_object('config.Config')

# Initialize Sentence-BERT model for conceptual similarity
model = SentenceTransformer('all-MiniLM-L6-v2')

# Helper function for text content similarity (Cosine Similarity)
def text_similarity(text1, text2):
    from sklearn.feature_extraction.text import CountVectorizer
    vectorizer = CountVectorizer().fit_transform([text1, text2])
    vectors = vectorizer.toarray()
    return cosine_similarity(vectors)[0, 1]

# Text preprocessing helper function
def preprocess_text(text):
    text = text.lower()
    text = ''.join([char for char in text if char not in string.punctuation])
    words = text.split()
    stop_words = set(stopwords.words('english'))
    words = [word for word in words if word not in stop_words]
    stemmer = PorterStemmer()
    words = [stemmer.stem(word) for word in words]
    return ' '.join(words)

# Enhanced text similarity function
def enhanced_text_similarity(text1, text2):
    processed_text1 = preprocess_text(text1)
    processed_text2 = preprocess_text(text2)
    vectorizer = CountVectorizer().fit_transform([processed_text1, processed_text2])
    vectors = vectorizer.toarray()
    return cosine_similarity(vectors)[0, 1]
    

# Conceptual similarity using a pre-trained model (Sentence-BERT)
def concept_similarity(text1, text2):
    embeddings1 = model.encode(text1, convert_to_tensor=True)
    embeddings2 = model.encode(text2, convert_to_tensor=True)
    similarity = np.inner(embeddings1, embeddings2) / (np.linalg.norm(embeddings1) * np.linalg.norm(embeddings2))
    return similarity

# Calculate final score based on both content similarity and conceptual similarity
def calculate_final_score(extracted_text, stored_answer):
    content_similarity = enhanced_text_similarity(extracted_text, stored_answer)
    concept_similarity_score = concept_similarity(extracted_text, stored_answer)
    score = (content_similarity + concept_similarity_score) / 2 * 10
    return score

# OCR API function
def extract_text_from_image(image_path):
    api_key = 'K83224048788957'  # Your API key
    url = 'https://api.ocr.space/parse/image'

    with open(image_path, 'rb') as image_file:
        payload = {
            'apikey': api_key,
            'language': 'eng',
            'isOverlayRequired': 'false',
            'OCREngine': '2'  # Use OCR Engine 2 for handwriting
        }
        response = requests.post(url, files={'file': image_file}, data=payload)

    result = response.json()
    text = result.get('ParsedResults')[0].get('ParsedText', '')
    return text

# MySQL connection function
def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='',  # Your MySQL password
        database='flask_db'
    )

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
        user = cur.fetchone()
        conn.close()
        if user:
            session['username'] = username
            session['role'] = user[3]  # assuming role is stored in the 4th column
            return redirect(url_for('admin_dashboard' if user[3] == 'admin' else 'faculty_dashboard'))
        else:
            flash('Invalid credentials, please try again')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", (username, password, role))
        conn.commit()
        conn.close()
        flash('Registration successful! You can now login.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        question_id = request.form['question_id']
        subject = request.form['subject']
        answer = request.form['answer']
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO answers (question_id, subject, answer) VALUES (%s, %s, %s)", (question_id, subject, answer))
        conn.commit()
        conn.close()
        flash('Answer added successfully!')
    
    return render_template('admin_dashboard.html')

@app.route('/faculty_dashboard', methods=['GET', 'POST'])
def faculty_dashboard():
    if 'username' not in session or session['role'] != 'faculty':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT question_id, subject FROM answers")
    questions = cur.fetchall()
    conn.close()
    
    if request.method == 'POST':
        question_id = request.form['question_id']
        subject = request.form['subject']
        image = request.files['image']
        
        # Save the uploaded image
        image_path = os.path.join('static/uploads', image.filename)
        image.save(image_path)
        
        # Extract text from the image
        extracted_text = extract_text_from_image(image_path)
        
        if extracted_text:
            # Retrieve the stored answer from the database
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT answer FROM answers WHERE question_id=%s AND subject=%s", (question_id, subject))
            stored_answer = cur.fetchone()[0]
            conn.close()
            
            # Calculate the final score using both content and conceptual similarity
            score = calculate_final_score(extracted_text, stored_answer)
            score = round(score)
            
            # Render the result with the score and extracted text
            return render_template('faculty_dashboard.html', score=score, extracted_text=extracted_text)
    
    return render_template('faculty_dashboard.html', questions=questions)

if __name__ == '__main__':
    app.run(debug=True)
