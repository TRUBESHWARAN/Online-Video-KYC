from flask import Flask, render_template, redirect, request, flash, session
from flask_sqlalchemy import SQLAlchemy
import os
import cv2
import dlib
import time
from sqlalchemy import func
import face_recognition

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'  # Folder to store uploaded files
app.secret_key = 'your_secret_key'

db = SQLAlchemy(app)
detector = dlib.get_frontal_face_detector()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class UserResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    response = db.Column(db.String(200), nullable=False)

def extract_faces(image_path):
    # Load the image
    frame = cv2.imread(image_path)
    # Convert the image to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # Detect faces in the grayscale image
    faces = detector(gray)
    # Loop through each detected face
    for i, face in enumerate(faces):
        # Extract the face region
        x1, y1, x2, y2 = face.left(), face.top(), face.right(), face.bottom()
        face_image = frame[y1:y2, x1:x2]
        # Save the extracted face to the faces folder
        face_filename = os.path.join('faces', f'face_{os.path.basename(image_path)}_{i}.jpg')
        cv2.imwrite(face_filename, face_image)

def capture_snapshots():
    # Initialize the video capture device
    cap = cv2.VideoCapture(0)
    # Create a folder for storing snapshots
    os.makedirs('vidsnap', exist_ok=True)
    count = 0
    while count < 4:
        # Capture frame-by-frame
        ret, frame = cap.read()
        if ret:
            # Save the frame as an image file
            snapshot_filename = os.path.join('vidsnap', f'snapshot_{count}.jpg')
            cv2.imwrite(snapshot_filename, frame)
            count += 1
        # Wait for 5 seconds before capturing the next snapshot
        time.sleep(3)
    # Release the capture device
    cap.release()
    cv2.destroyAllWindows()

def extract_faces_from_vidsnap():
    # Create a folder for storing extracted faces
    os.makedirs('vidfaces', exist_ok=True)
    # Load the face detector
    detector = dlib.get_frontal_face_detector()

    # Loop through all snapshot files in vidsnap folder
    for filename in os.listdir('vidsnap'):
        if filename.endswith('.jpg'):
            # Read the snapshot image
            image_path = os.path.join('vidsnap', filename)
            frame = cv2.imread(image_path)
            # Convert the image to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Detect faces in the grayscale image
            faces = detector(gray)
            # Loop through each detected face
            for i, face in enumerate(faces):
                # Extract the face region
                x1, y1, x2, y2 = face.left(), face.top(), face.right(), face.bottom()
                face_image = frame[y1:y2, x1:x2]
                # Save the extracted face to the vidfaces folder
                face_filename = os.path.join('vidfaces', f'face_{os.path.splitext(filename)[0]}_{i}.jpg')
                cv2.imwrite(face_filename, face_image)

@app.route('/')
def home():
    return render_template('index.html', title='Automated Video KYC')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        username = request.form['username']
        password = request.form['password']

        user = User(first_name=first_name, last_name=last_name, username=username, password=password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful!')
        return redirect('/')

    return render_template('register.html', title='Register')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username, password=password).first()

        if user:
            session['user_id'] = user.id
            flash('Login successful!')
            return redirect('/docupload')
        else:
            flash('Invalid username or password')

    return render_template('login.html', title='Login')

@app.route('/docupload')
def docupload():
    if 'user_id' in session:
        return render_template('docupload.html', title='Document Upload')
    else:
        return redirect('/login')
    
@app.route('/success', methods=['GET', 'POST'])
def success():
    return render_template('success.html', title='Success')

@app.route('/upload_docs', methods=['POST'])
def upload_docs():
    if 'user_id' in session:
        # Get user ID from session
        user_id = session.get('user_id')

        # Check if the POST request has the file part
        if 'aadhaar' not in request.files or 'pan' not in request.files:
            flash('No file part')
            return redirect(request.url)

        aadhaar_file = request.files['aadhaar']
        pan_file = request.files['pan']

        # If user does not select file, browser also submits an empty part without filename
        if aadhaar_file.filename == '' or pan_file.filename == '':
            flash('No selected file')
            return redirect(request.url)

        # Save the uploaded files to the UPLOAD_FOLDER directory
        aadhaar_filename = os.path.join(app.config['UPLOAD_FOLDER'], 'aadhaar_' + str(user_id) + '.jpg')
        pan_filename = os.path.join(app.config['UPLOAD_FOLDER'], 'pan_' + str(user_id) + '.jpg')

        aadhaar_file.save(aadhaar_filename)
        pan_file.save(pan_filename)

        # Extract faces from the uploaded images
        extract_faces(aadhaar_filename)
        extract_faces(pan_filename)

        # Capture snapshots from live video feed
        capture_snapshots()

        # Extract faces from the snapshots in vidsnap folder
        extract_faces_from_vidsnap()

        flash('Documents uploaded successfully')
        return redirect('/main')

    else:
        return redirect('/login')

@app.route('/main')
def main():
    if 'user_id' in session:
        return render_template('main.html', title='Main Page')
    else:
        return redirect('/login')

@app.route('/save_response', methods=['POST'])
def save_response():
    if request.method == 'POST':
        response = request.json.get('response')
        user_id = session.get('user_id')

        if response and user_id:
            user_response = UserResponse(user_id=user_id, response=response)
            db.session.add(user_response)
            db.session.commit()
            return {'message': 'Response saved successfully'}
        else:
            return {'error': 'Invalid request'}, 400
        
@app.route('/compare_faces')
def compare_faces():
    # Fetch the user's responses from the database
    user_id = session.get('user_id')
    user_responses = UserResponse.query.filter_by(user_id=user_id).all()
    max_response_id = db.session.query(func.max(UserResponse.id)).scalar()

    # Check if 4 responses are recorded
    if max_response_id is not None and max_response_id >= 4:
        # Define paths to face images
        vidfaces_path = 'vidfaces'
        faces_path = 'faces'

        # Load the known faces
        known_face_encodings = []
        known_face_names = []
        for face_image in os.listdir(faces_path):
            face_name = os.path.splitext(face_image)[0]
            face_image_path = os.path.join(faces_path, face_image)
            known_face_image = face_recognition.load_image_file(face_image_path)
            known_face_encoding = face_recognition.face_encodings(known_face_image)[0]
            known_face_encodings.append(known_face_encoding)
            known_face_names.append(face_name)

        # Get the list of face images in the vidfaces folder
        vidfaces_images = [os.path.join(vidfaces_path, image) for image in os.listdir(vidfaces_path) if image.endswith('.jpg')]

        # Load each unknown face and compare it with known faces
        for vidface_image in vidfaces_images:
            # Load the unknown face
            unknown_face_image = face_recognition.load_image_file(vidface_image)
            unknown_face_encoding = face_recognition.face_encodings(unknown_face_image)[0]

            # Compare the unknown face with known faces
            matches = face_recognition.compare_faces(known_face_encodings, unknown_face_encoding)

            # Check if any match is found
            if True in matches:
                # Get the index of the matched known face
                match_index = matches.index(True)
                matched_face_name = known_face_names[match_index]

                # If face is recognized, redirect to success.html
                return redirect('/success')


        # If none of the face images match, redirect to failure.html
        return redirect('/failure.html')

    else:
        # If 4 responses are not recorded yet, redirect to main page
        return redirect('/main')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        db.session.commit()  # Committing the session here
    app.run(debug=True)
