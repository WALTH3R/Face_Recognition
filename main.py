import cv2
import face_recognition
import numpy as np
import os
import pickle
import pandas as pd
from datetime import datetime
from security import SecurityManager
import getpass

def run_recognition(password):
    security = SecurityManager(password)
    
    # Load and decrypt encodings
    known_face_encodings = []
    known_face_names = []
    
    students = security.list_encrypted_students()
    if not students:
        print("No secured encodings found. Please run encode_faces.py first.")
        return

    print("Loading and decrypting student encodings...")
    for student_name in students:
        try:
            decrypted_data = security.decrypt_data(student_name)
            encodings = pickle.loads(decrypted_data)
            # Use the average encoding for better accuracy, or just use all
            # Here we use all encodings for matching
            for encoding in encodings:
                known_face_encodings.append(encoding)
                known_face_names.append(student_name)
        except Exception as e:
            print(f"Error loading {student_name}: {e}")

    # Initialize CSV log
    log_file = "logs/attendance.csv"
    if not os.path.exists("logs"):
        os.makedirs("logs")
    if not os.path.exists(log_file):
        df = pd.DataFrame(columns=["Name", "Timestamp", "Confidence"])
        df.to_csv(log_file, index=False)

    # Initialize webcam
    video_capture = cv2.VideoCapture(0)

    print("Starting real-time recognition. Press 'q' to quit.")
    
    logged_today = set()

    while True:
        ret, frame = video_capture.read()
        if not ret:
            break

        # Resize frame for faster processing
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        # Find all the faces and face encodings in the current frame
        face_locations = face_recognition.face_locations(rgb_small_frame)
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            # Scale back up face locations since the frame we detected in was scaled to 1/4 size
            top *= 4
            right *= 4
            bottom *= 4
            left *= 4

            # Compare faces
            matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
            name = "Unknown"
            confidence = 0

            # Use face distances to get confidence
            face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
            if len(face_distances) > 0:
                best_match_index = np.argmin(face_distances)
                if matches[best_match_index]:
                    name = known_face_names[best_match_index]
                    # Simple confidence formula: 1 - distance (threshold is usually 0.6)
                    confidence = max(0, 1 - face_distances[best_match_index]) * 100

            # Draw box and label
            color = (0, 0, 255) if name == "Unknown" else (0, 255, 0)
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
            font = cv2.FONT_HERSHEY_DUPLEX
            label = f"{name} ({confidence:.1f}%)" if name != "Unknown" else name
            cv2.putText(frame, label, (left + 6, bottom - 6), font, 1.0, (255, 255, 255), 1)

            # Log to CSV if recognized and not already logged in this session
            if name != "Unknown" and name not in logged_today:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                new_log = pd.DataFrame([[name, timestamp, f"{confidence:.1f}%"]], columns=["Name", "Timestamp", "Confidence"])
                new_log.to_csv(log_file, mode='a', header=False, index=False)
                logged_today.add(name)
                print(f"Logged attendance for {name}")

        # Display the resulting image
        cv2.imshow('Face Recognition System', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    video_capture.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    pwd = getpass.getpass("Enter master password for decryption: ")
    run_recognition(pwd)
